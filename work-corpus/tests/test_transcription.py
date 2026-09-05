from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from work_corpus import cli
from work_corpus import transcription
from work_corpus.config import ConfigurationError, load_config
from work_corpus.db import connect, record_source_version, upsert_source_record
from work_corpus.zoom import scan_zoom

GOOD_VTT = (
    "WEBVTT\n\n"
    "00:00:00.000 --> 00:00:10.000\n"
    "Speaker: a useful local transcript\n"
)
PARTIAL_VTT = (
    "WEBVTT\n\n"
    "00:00:00.000 --> 00:00:01.000\n"
    "A short partial result\n"
)


def _write_config(tmp_path: Path, command: list[str]) -> object:
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "zoom": {
                    "engine": "custom",
                    "model": "local-test-model",
                    "custom_command": command,
                }
            }
        ),
        encoding="utf-8",
    )
    return load_config(tmp_path)


def _engine_script(tmp_path: Path) -> Path:
    script = tmp_path / "local_transcriber.py"
    script.write_text(
        """
import argparse
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--output-vtt', required=True)
parser.add_argument('--mode', default='good')
parser.add_argument('--log', default='')
parser.add_argument('--marker', default='')
parser.add_argument('--input', default='')
parser.add_argument('--input-log', default='')
args = parser.parse_args()

if args.log:
    with Path(args.log).open('a', encoding='utf-8') as handle:
        handle.write('start\\n')

if args.mode == 'fail':
    raise SystemExit(17)
if args.mode == 'flaky' and args.marker and not Path(args.marker).exists():
    Path(args.marker).write_text('first attempt', encoding='utf-8')
    raise SystemExit(17)
if args.input_log:
    Path(args.input_log).write_bytes(Path(args.input).read_bytes())

end_time = '00:00:01.000' if args.mode == 'partial' else '00:00:10.000'
speaker = '' if args.mode == 'partial' else 'Speaker: '
Path(args.output_vtt).write_text(
    f'''WEBVTT\\n\\n00:00:00.000 --> {end_time}\\n{speaker}local result\\n''',
    encoding='utf-8',
)
if args.log:
    with Path(args.log).open('a', encoding='utf-8') as handle:
        handle.write('end\\n')
""".strip()
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def _command(
    script: Path,
    *,
    mode: str = "good",
    log: Path | None = None,
    marker: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(script),
        "--output-vtt",
        "{output_vtt}",
        "--mode",
        mode,
    ]
    if log:
        command.extend(["--log", str(log)])
    if marker:
        command.extend(["--marker", str(marker)])
    return command


def _recording_command(script: Path, input_log: Path) -> list[str]:
    return [
        sys.executable,
        str(script),
        "--output-vtt",
        "{output_vtt}",
        "--input",
        "{input}",
        "--input-log",
        str(input_log),
    ]


def _config_and_db(tmp_path: Path, command: list[str]):
    config = _write_config(tmp_path, command)
    con = connect(config.state_dir / "transcription.sqlite")
    con.execute(
        """
        INSERT INTO source_root (
            root_key, relative_path, source_system, precedence, enabled
        ) VALUES ('zoom', 'data/Zoom', 'zoom', 50, 1)
        """
    )
    con.commit()
    return config, con


def _add_source(
    config,
    con,
    relative_path: str,
    content: bytes,
    *,
    kind: str = "media",
    extraction_status: str = "ready",
    hash_content: bool = True,
):
    path = config.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    source_id = upsert_source_record(
        con,
        root_key="zoom",
        relative_path=relative_path,
        source_system="zoom",
        kind=kind,
        scope="Work",
        sensitivity="internal_review",
    )
    digest = hashlib.sha256(content).hexdigest() if hash_content else None
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, extension=?, size_bytes=?, mtime_ns=?,
            content_sha256=?, classification='Work', scope='Work',
            extraction_status=?, metadata_json='{}'
        WHERE source_id=?
        """,
        (
            str(path),
            path.suffix.lower(),
            len(content),
            path.stat().st_mtime_ns,
            digest,
            extraction_status,
            source_id,
        ),
    )
    version_id = None
    if digest:
        version_id = record_source_version(
            con,
            source_id,
            len(content),
            path.stat().st_mtime_ns,
            digest,
        )
    con.commit()
    return source_id, version_id


def _scan_media(config, con, count: int = 2):
    for index in range(count):
        _add_source(
            config,
            con,
            f"data/Zoom/2026-09-10 Coverage/recording-{index}.mp4",
            f"media-{index}".encode(),
        )
    scan_zoom(config, con)


def test_transcribe_cli_forwards_explicit_approval_without_local_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    calls = []

    monkeypatch.setattr(cli, "scan_zoom", lambda *_args: {})
    monkeypatch.setattr(cli, "build_report", lambda *_args: {})

    def fake_transcribe_jobs(_config, _con, **kwargs):
        calls.append(kwargs)
        return {
            "attempted": 0,
            "pending_approval": 0 if kwargs.get("approve_run", False) else 1,
        }

    monkeypatch.setattr(cli, "transcribe_jobs", fake_transcribe_jobs)

    default_root = tmp_path / "default"
    approved_root = tmp_path / "approved"
    assert cli.main(["--root", str(default_root), "transcribe"]) == 0
    assert (
        cli.main(
            ["--root", str(approved_root), "transcribe", "--approve-run"]
        )
        == 0
    )

    assert [call["approve_run"] for call in calls] == [False, True]
    assert not (default_root / "data").exists()
    assert not (approved_root / "data").exists()


def test_run_approval_and_checkpoint_resume_are_sequential(tmp_path: Path):
    script = _engine_script(tmp_path)
    log = tmp_path / "runner.log"
    config, con = _config_and_db(tmp_path, _command(script, log=log))
    try:
        _scan_media(config, con, count=2)

        waiting = transcription.transcribe_jobs(config, con, requested_engine="custom")
        before_approval = con.execute(
            "SELECT status FROM transcription_job ORDER BY job_id"
        ).fetchall()
        first = transcription.transcribe_jobs(
            config,
            con,
            requested_engine="custom",
            approve_run=True,
            max_files=1,
        )
        after_first = con.execute(
            "SELECT status FROM transcription_job ORDER BY job_id"
        ).fetchall()
        checkpoint = con.execute(
            """
            SELECT provider, cursor, item_count, source_version_id
            FROM ingestion_checkpoint WHERE provider='local_transcription'
            """
        ).fetchone()
        second = transcription.transcribe_jobs(
            config, con, requested_engine="custom"
        )
        final = con.execute(
            "SELECT status FROM transcription_job ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()

    assert waiting["attempted"] == 0
    assert {row["status"] for row in before_approval} == {"pending_approval"}
    assert first["attempted"] == 1
    assert first["succeeded"] == 1
    assert {row["status"] for row in after_first} == {"succeeded", "queued"}
    assert checkpoint["provider"] == "local_transcription"
    assert checkpoint["cursor"]
    assert checkpoint["item_count"] == 1
    assert checkpoint["source_version_id"]
    assert second["attempted"] == 1
    assert second["succeeded"] == 1
    assert [line.strip() for line in log.read_text().splitlines()] == [
        "start",
        "end",
        "start",
        "end",
    ]
    assert {row["status"] for row in final} == {"succeeded"}


def test_approval_queues_the_complete_set_not_a_selected_subset(tmp_path: Path):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        _scan_media(config, con, count=3)
        approved = transcription.approve_transcription_run(con)
        rows = con.execute(
            "SELECT status, approval_status FROM transcription_job"
        ).fetchall()
    finally:
        con.close()

    assert approved == 3
    assert {row["status"] for row in rows} == {"queued"}
    assert {row["approval_status"] for row in rows} == {"approved"}


@pytest.mark.parametrize(
    "zoom_config",
    [
        {"engine": "deepgram"},
        {
            "engine": "custom",
            "custom_command": ["curl", "https://example.invalid/transcribe"],
        },
        {
            "engine": "custom",
            "custom_command": ["local-transcriber", "--api-key", "secret"],
        },
    ],
)
def test_local_engine_rejects_remote_commands_and_cloud_names(
    tmp_path: Path, zoom_config: dict
):
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"zoom": zoom_config}), encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="local transcription"):
        load_config(tmp_path)


def test_job_keys_are_idempotent_and_change_with_source_version(tmp_path: Path):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        relative_path = "data/Zoom/2026-09-11 Versioned/recording.mp4"
        _add_source(config, con, relative_path, b"first")
        scan_zoom(config, con)
        first = con.execute(
            "SELECT job_id, media_version_id FROM transcription_job"
        ).fetchone()
        scan_zoom(config, con)
        repeated = con.execute(
            "SELECT job_id, media_version_id FROM transcription_job"
        ).fetchall()

        _add_source(config, con, relative_path, b"second")
        scan_zoom(config, con)
        versioned = con.execute(
            "SELECT job_id, media_version_id FROM transcription_job ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()

    assert len(repeated) == 1
    assert repeated[0]["job_id"] == first["job_id"]
    assert len(versioned) == 2
    assert len({row["job_id"] for row in versioned}) == 2
    assert len({row["media_version_id"] for row in versioned}) == 2


def test_retry_after_failure_is_recorded_and_does_not_drop_remaining_queue(
    tmp_path: Path,
):
    script = _engine_script(tmp_path)
    marker = tmp_path / "flaky.marker"
    config, con = _config_and_db(
        tmp_path, _command(script, mode="flaky", marker=marker)
    )
    try:
        _scan_media(config, con, count=2)
        first = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        after_failure = con.execute(
            "SELECT status FROM transcription_job ORDER BY job_id"
        ).fetchall()
        second = transcription.transcribe_jobs(
            config,
            con,
            requested_engine="custom",
            retry_errors=True,
        )
        after_retry = con.execute(
            "SELECT status FROM transcription_job ORDER BY job_id"
        ).fetchall()
    finally:
        con.close()

    assert first["failed"] == 1
    assert first["succeeded"] == 1
    assert {row["status"] for row in after_failure} == {"failed", "succeeded"}
    assert second["retried"] == 1
    assert second["succeeded"] == 1
    assert {row["status"] for row in after_retry} == {"succeeded"}


def test_partial_quality_remains_visible_with_coverage_and_speaker_status(
    tmp_path: Path,
):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script, mode="good"))
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-12 Partial/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        con.execute(
            "UPDATE meeting_group SET duration_seconds=10.0"
        )
        con.commit()
        # The engine script is intentionally replaced with a short-result script.
        config.payload["zoom"]["custom_command"] = _command(
            script, mode="partial"
        )
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT * FROM transcription_job").fetchone()
        group = con.execute("SELECT * FROM meeting_group").fetchone()
    finally:
        con.close()

    assert result["partial"] == 1
    assert job["status"] == "partial"
    assert job["quality_status"] == "partial"
    assert job["timestamp_coverage"] == pytest.approx(0.1)
    assert job["speaker_label_status"] == "absent"
    assert Path(job["output_path"]).is_file()
    assert group["status"] == "partial"


def test_artifact_is_terminal_and_not_a_transcription_failure(tmp_path: Path):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-13 Artifact/recording.tmp",
            b"temporary",
            kind="unknown",
        )
        scan_zoom(config, con)
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT * FROM transcription_job").fetchone()
    finally:
        con.close()

    assert result["attempted"] == 0
    assert result["artifact"] == 1
    assert job["status"] == "artifact"
    assert "temporary" in job["error"].casefold()


def test_prior_successful_transcript_survives_failed_retry(tmp_path: Path):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-14 Preserve/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        good_job = con.execute("SELECT * FROM transcription_job").fetchone()
        output_path = Path(good_job["output_path"])
        original = output_path.read_text(encoding="utf-8")
        con.execute(
            "UPDATE transcription_job SET status='failed', approval_status='approved'"
        )
        con.commit()
        config.payload["zoom"]["custom_command"] = _command(script, mode="fail")
        result = transcription.transcribe_jobs(
            config,
            con,
            requested_engine="custom",
            retry_errors=True,
        )
        retried_job = con.execute("SELECT * FROM transcription_job").fetchone()
    finally:
        con.close()

    assert result["failed"] == 1
    assert retried_job["status"] == "failed"
    assert output_path.read_text(encoding="utf-8") == original


def test_missing_local_engine_marks_eligible_items_blocked(tmp_path: Path):
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "zoom": {
                    "engine": "custom",
                    "custom_command": [
                        str(tmp_path / "does-not-exist"),
                        "{input}",
                    ],
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "blocked.sqlite")
    con.execute(
        """
        INSERT INTO source_root (
            root_key, relative_path, source_system, precedence, enabled
        ) VALUES ('zoom', 'data/Zoom', 'zoom', 50, 1)
        """
    )
    con.commit()
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-15 Blocked/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT * FROM transcription_job").fetchone()
    finally:
        con.close()

    assert result["attempted"] == 0
    assert result["blocked"] == 1
    assert job["status"] == "blocked"
    assert "not found" in job["error"].casefold()


def test_historical_job_cannot_send_current_source_bytes_to_engine(tmp_path: Path):
    script = _engine_script(tmp_path)
    input_log = tmp_path / "engine-input.bin"
    config, con = _config_and_db(
        tmp_path, _recording_command(script, input_log)
    )
    relative_path = "data/Zoom/2026-09-16 Historical/recording.mp4"
    try:
        _add_source(config, con, relative_path, b"historical media")
        scan_zoom(config, con)
        transcription.approve_transcription_run(con)
        historical_job = con.execute(
            "SELECT job_id, media_version_id FROM transcription_job"
        ).fetchone()

        _add_source(config, con, relative_path, b"current media")
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom"
        )
        job = con.execute(
            "SELECT status, error FROM transcription_job WHERE job_id=?",
            (historical_job["job_id"],),
        ).fetchone()
    finally:
        con.close()

    assert result["attempted"] == 0
    assert result["blocked"] == 1
    assert job["status"] == "blocked"
    assert "version" in job["error"].casefold()
    assert not input_log.exists()


@pytest.mark.parametrize("requested_engine", ["openai_whisper", "auto"])
def test_openai_whisper_cli_is_not_an_allowed_local_execution_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, requested_engine: str
):
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"zoom": {"engine": "openai_whisper"}}),
        encoding="utf-8",
    )
    config = load_config(tmp_path)

    monkeypatch.setattr(
        transcription,
        "_resolved_executable",
        lambda value: "/synthetic/whisper" if value == "whisper" else None,
    )
    monkeypatch.setattr(transcription.importlib.util, "find_spec", lambda _name: None)

    engine, reason = transcription._engine_available(config, requested_engine)

    assert engine is None
    assert "openai whisper" in reason.casefold()
    assert "download" in reason.casefold()


def test_scope_review_uses_documented_queue_states_and_resumes_after_correction(
    tmp_path: Path,
):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        source_id, _version_id = _add_source(
            config,
            con,
            "data/Zoom/2026-09-17 Scope Review/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        con.execute(
            "UPDATE source_record SET classification='Personal', scope='Personal' "
            "WHERE source_id=?",
            (source_id,),
        )
        con.commit()

        scan_zoom(config, con)
        held = con.execute(
            "SELECT status, approval_status FROM transcription_job"
        ).fetchone()
        group = con.execute("SELECT status FROM meeting_group").fetchone()
        approved_while_review = transcription.approve_transcription_run(con)
        held_run = transcription.transcribe_jobs(
            config, con, requested_engine="custom"
        )
        held_after_run = con.execute(
            "SELECT status, approval_status FROM transcription_job"
        ).fetchone()

        con.execute(
            "UPDATE source_record SET classification='Work', scope='Work' "
            "WHERE source_id=?",
            (source_id,),
        )
        con.commit()
        scan_zoom(config, con)
        resumed = con.execute(
            "SELECT status, approval_status FROM transcription_job"
        ).fetchone()
        approved = transcription.approve_transcription_run(con)
        queued = con.execute(
            "SELECT status, approval_status FROM transcription_job"
        ).fetchone()
    finally:
        con.close()

    assert group["status"] == "needs_review"
    assert held["status"] == "pending_approval"
    assert held["approval_status"] == "pending_approval"
    assert approved_while_review == 1
    assert held_run["skipped"] == 1
    assert held_after_run["status"] == "pending_approval"
    assert held_after_run["approval_status"] == "pending_approval"
    assert resumed["status"] == "pending_approval"
    assert resumed["approval_status"] == "pending_approval"
    assert approved == 1
    assert queued["status"] == "queued"
    assert queued["approval_status"] == "approved"
