from __future__ import annotations

import fcntl
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from work_corpus import cli, db


def _database(root: Path) -> Path:
    database = root / "work-corpus" / "state" / "work_corpus.sqlite"
    lock_path = database.parent / "mcp" / "granola_rest_delta.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch()
    con = db.connect(database)
    con.execute(
        "INSERT INTO source_root (root_key, relative_path, source_system, precedence, enabled) "
        "VALUES ('synthetic', 'data/synthetic', 'synthetic', 10, 1)"
    )
    source_id = db.upsert_source_record(
        con,
        root_key="synthetic",
        relative_path="data/synthetic/atlas.md",
        source_system="synthetic",
        kind="document",
        scope="Work",
        sensitivity="internal",
    )
    path = root / "data" / "synthetic" / "atlas.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "Project Atlas was approved for launch."
    path.write_text(text, encoding="utf-8")
    content = text.encode("utf-8")
    version_id = db.record_source_version(
        con,
        source_id=source_id,
        size_bytes=len(content),
        mtime_ns=1,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )
    con.execute(
        "UPDATE source_record SET absolute_path=?, classification='Work', extraction_status='ready' "
        "WHERE source_id=?",
        (str(path), source_id),
    )
    db.record_evidence(
        con,
        source_version_id=version_id,
        locator="document:1",
        derived_text_path=str(path),
        text_sha256=hashlib.sha256(content).hexdigest(),
        evidence_status="canonical",
        derived_text=text,
    )
    con.commit()
    con.close()
    for suffix in ("-wal", "-shm"):
        database.with_name(database.name + suffix).unlink(missing_ok=True)
    return database


def _git_output_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(
        "work-corpus/state/\nwork-corpus/corpus/\n",
        encoding="utf-8",
    )
    (root / "tracked.txt").write_text("tracked sentinel\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-C", str(root), "add", "--", "tracked.txt"],
        check=True,
    )
    return root


def test_cli_answer_is_read_only_and_emits_json(capsys: pytest.CaptureFixture[str], tmp_path: Path):
    database = _database(tmp_path)
    before = database.read_bytes()
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cli, "bootstrap", lambda _config: pytest.fail("bootstrap called"))
        monkeypatch.setattr(cli, "_record_start", lambda *_args: pytest.fail("pipeline run recorded"))
        assert cli.main(
            [
                "--root",
                str(tmp_path),
                "answer",
                "Project Atlas",
            ]
        ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "evidence_only"
    assert payload["citations"][0]["locator"] == "document:1"
    assert database.read_bytes() == before


def test_cli_answer_holds_delta_reader_lock(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    database = _database(tmp_path)
    lock_path = database.parent / "mcp" / "granola_rest_delta.lock"

    def fake_answer(con: object, question: str, **_kwargs: object) -> dict[str, object]:
        del con, question
        writer_handle = lock_path.open("rb")
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(
                    writer_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
        finally:
            fcntl.flock(writer_handle.fileno(), fcntl.LOCK_UN)
            writer_handle.close()
        return {"status": "evidence_only", "answer": "locked"}

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cli, "answer_question", fake_answer)
        assert cli.main(["--root", str(tmp_path), "answer", "lock probe"]) == 0

    assert json.loads(capsys.readouterr().out)["answer"] == "locked"


def test_granola_delta_cli_enters_dedicated_route_before_database_setup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
):
    seen: dict[str, object] = {}

    def fake_run_delta(config: object, **kwargs: object) -> dict[str, object]:
        seen.update(config=config, **kwargs)
        return {"status": "synthetic"}

    monkeypatch.setattr(cli, "run_delta", fake_run_delta)
    monkeypatch.setattr(
        cli,
        "connect",
        lambda *_args, **_kwargs: pytest.fail("granola-delta opened a common DB connection"),
    )
    monkeypatch.setattr(
        cli,
        "_record_start",
        lambda *_args: pytest.fail("granola-delta recorded a common pipeline run"),
    )

    assert cli.main(["--root", str(tmp_path), "granola-delta"]) == 0

    assert json.loads(capsys.readouterr().out)["status"] == "synthetic"
    assert seen["config"] is not None


def test_cli_sensitive_backend_requires_explicit_opt_in(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    _database(tmp_path)
    assert cli.main(
        [
            "--root",
            str(tmp_path),
            "answer",
            "Project Atlas",
            "--backend",
            "g2k-sensitive",
        ]
    ) == 1
    assert "sensitive" in capsys.readouterr().err.casefold()


def test_cli_answer_compare_requires_sensitive_opt_in(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    database = _database(tmp_path)
    assert cli.main(
        [
            "--root",
            str(tmp_path),
            "answer-compare",
            "What happened to Project Atlas?",
        ]
    ) == 1
    assert "sensitive" in capsys.readouterr().err.casefold()
    assert database.exists()


def test_cli_answer_compare_delegates_to_shared_read_only_orchestration(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    database = _database(tmp_path)
    before = database.read_bytes()
    seen: dict[str, object] = {}

    def fake_compare(con: object, question: str, **kwargs: object) -> dict[str, object]:
        seen.update(con=con, question=question, **kwargs)
        return {
            "status": "compared",
            "answer_kind": "comparison",
            "packet_sha256": "digest",
            "local_packet_sha256": "digest",
            "remote_packet_sha256": "digest",
            "packet_sha256_equal": True,
        }

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cli, "bootstrap", lambda _config: pytest.fail("bootstrap called"))
        monkeypatch.setattr(cli, "_record_start", lambda *_args: pytest.fail("pipeline run recorded"))
        monkeypatch.setattr(cli, "answer_question", lambda *_args, **_kwargs: pytest.fail("answer lane rebuilt"))
        monkeypatch.setattr(cli, "compare_answers", fake_compare)
        assert cli.main(
            [
                "--root",
                str(tmp_path),
                "answer-compare",
                "What happened to Project Atlas?",
                "--allow-sensitive-remote",
            ]
        ) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["packet_sha256_equal"] is True
    assert seen["question"] == "What happened to Project Atlas?"
    assert type(seen["local_backend"]).__name__ == "OllamaBackend"
    assert type(seen["remote_backend"]).__name__ == "GatewaySensitiveBackend"
    assert seen["allow_sensitive_remote"] is True
    assert database.read_bytes() == before


def test_evaluation_output_allows_only_scoped_state_report(tmp_path: Path):
    root = _git_output_root(tmp_path / "repo")
    output = root / "work-corpus" / "state" / "answer-eval-report.json"

    cli._write_evaluation_output(root, output, '{"status":"evaluated"}\n')

    assert output.read_text(encoding="utf-8") == '{"status":"evaluated"}\n'
    with pytest.raises(ValueError, match="new"):
        cli._write_evaluation_output(root, output, '{"status":"replacement"}\n')


def test_evaluation_output_rejects_symlink_target(tmp_path: Path):
    root = _git_output_root(tmp_path / "repo")
    sentinel = root / "sentinel.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    target = root / "work-corpus" / "state" / "answer-eval-link.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(sentinel)

    with pytest.raises(ValueError, match="new"):
        cli._write_evaluation_output(root, target, "replacement\n")

    assert sentinel.read_text(encoding="utf-8") == "preserve\n"


@pytest.mark.parametrize(
    "relative_path",
    (
        "tracked.txt",
        "work-corpus/output/report.json",
        "work-corpus/state/work_corpus.sqlite",
        "work-corpus/corpus/raw/capture.bin",
        "work-corpus/state/arbitrary-ignored.json",
    ),
)
def test_evaluation_output_rejects_non_report_paths(
    tmp_path: Path,
    relative_path: str,
):
    root = _git_output_root(tmp_path / "repo")
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("sentinel\n", encoding="utf-8")

    with pytest.raises(ValueError, match="work-corpus/state/answer-eval"):
        cli._write_evaluation_output(root, target, "replacement\n")

    assert target.read_text(encoding="utf-8") == "sentinel\n"
