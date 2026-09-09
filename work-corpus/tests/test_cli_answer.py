from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from work_corpus import cli, db


def _database(root: Path) -> Path:
    database = root / "work-corpus" / "state" / "work_corpus.sqlite"
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
