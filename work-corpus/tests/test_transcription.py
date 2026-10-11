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


def test_retry_blocked_engine_preflight_jobs_can_resume(tmp_path: Path):
    script = _engine_script(tmp_path)
    missing = tmp_path / "does-not-exist"
    config, con = _config_and_db(
        tmp_path,
        [str(missing), "{input}"],
    )
    try:
        _scan_media(config, con, count=1)
        first = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        assert first["blocked"] == 1

        config.payload["zoom"]["custom_command"] = _command(script)
        resumed = transcription.transcribe_jobs(
            config,
            con,
            requested_engine="custom",
            retry_blocked=True,
        )
        job = con.execute(
            "SELECT status, error, output_path FROM transcription_job"
        ).fetchone()
    finally:
        con.close()

    assert resumed["requeued"] == 1
    assert resumed["attempted"] == 1
    assert resumed["succeeded"] == 1
    assert job["status"] == "succeeded"
    assert job["error"] is None
    assert job["output_path"]


def test_quality_accepts_small_timestamp_rounding_inversion(tmp_path: Path):
    vtt = tmp_path / "rounded.vtt"
    vtt.write_text(
        "WEBVTT\n\n"
        "00:28:43.840 --> 00:28:44.840\nFirst cue\n\n"
        "00:28:43.800 --> 00:28:45.000\nSecond cue\n",
        encoding="utf-8",
    )

    quality = transcription.assess_transcript_quality(
        vtt, tmp_path / "missing.txt", 1800.0
    )

    assert quality["quality_status"] == "good"
    assert quality["timestamp_coverage"] > 0.5


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


# --- Engine resolution and local-only boundary -------------------------------


def _engine_config(tmp_path: Path, zoom: dict):
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.json").write_text(
        json.dumps({"zoom": zoom}), encoding="utf-8"
    )
    return load_config(tmp_path)


def _fake_binary(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_engine_availability_resolves_only_configured_local_engines(tmp_path: Path):
    config = _engine_config(tmp_path, {"engine": "auto", "custom_command": []})

    assert transcription._command_parts("a b 'c d'") == ["a", "b", "c d"]
    assert transcription._command_parts(["a", 1]) == ["a", "1"]
    assert transcription._command_parts(5) == []

    assert transcription._engine_available(config, "custom") == (
        None,
        "zoom.custom_command is empty",
    )
    assert transcription._engine_available(config, "deepgram") == (
        None,
        "unknown transcription engine: deepgram",
    )
    assert transcription._engine_available(config, "whisper_cpp") == (
        None,
        "whisper.cpp command not found",
    )
    assert transcription._engine_available(config, "faster_whisper") == (
        None,
        "Python package faster-whisper is not installed",
    )
    engine, reason = transcription._engine_available(config, "auto")
    assert engine is None
    assert "no configured local transcription engine found" in reason


def test_engine_availability_accepts_verified_whisper_cpp_and_custom(tmp_path: Path):
    binary = _fake_binary(tmp_path, "whisper-cli")
    model = tmp_path / "model.bin"
    model.write_text("model", encoding="utf-8")
    config = _engine_config(
        tmp_path,
        {
            "engine": "whisper_cpp",
            "whisper_cpp_command": str(binary),
            "whisper_cpp_model": str(model),
            "model": "large-v3",
        },
    )

    assert transcription._engine_available(config, "whisper_cpp") == ("whisper_cpp", "")
    assert transcription._engine_details(config, "whisper_cpp") == (str(binary), str(model))
    assert transcription._engine_details(config, "faster_whisper") == (
        "python:faster-whisper",
        "large-v3",
    )
    assert transcription._engine_details(config, "openai_whisper")[1] == "large-v3"
    assert transcription._engine_details(config, "unused")[0] == "unused"

    config.payload["zoom"]["whisper_cpp_model"] = str(tmp_path / "missing.bin")
    assert transcription._engine_available(config, "whisper_cpp") == (
        None,
        "whisper.cpp model path is not configured or does not exist",
    )
    config.payload["zoom"]["whisper_cpp_model"] = str(model)
    config.payload["zoom"]["whisper_cpp_command"] = str(tmp_path / "missing-cli")
    assert transcription._engine_available(config, "whisper_cpp") == (
        None,
        "whisper.cpp command not found",
    )

    config.payload["zoom"] = {
        "engine": "custom",
        "custom_command": [sys.executable, "-c", "pass"],
    }
    assert transcription._engine_available(config, "custom") == ("custom", "")
    assert transcription._engine_available(config, "auto") == ("custom", "")
    engine, model_name = transcription._engine_details(config, "custom")
    assert Path(engine).resolve() == Path(sys.executable).resolve()
    assert model_name


def test_auto_engine_uses_faster_whisper_when_available(tmp_path: Path, monkeypatch):
    config = _engine_config(tmp_path, {"engine": "auto"})
    monkeypatch.setattr(
        transcription.importlib.util, "find_spec", lambda _name: object()
    )

    assert transcription._engine_available(config, "faster_whisper") == (
        "faster_whisper",
        "",
    )
    assert transcription._engine_available(config, "auto") == ("faster_whisper", "")


def test_local_engine_entrypoints_fail_closed_without_verified_binaries(tmp_path: Path):
    config = _engine_config(tmp_path, {"engine": "auto"})
    media = tmp_path / "clip.wav"
    media.write_bytes(b"audio")
    stem = tmp_path / "staging" / "transcript"

    with pytest.raises(RuntimeError, match="whisper.cpp command/model is not configured"):
        transcription._transcribe_whisper_cpp(config, media, stem, tmp_path)
    with pytest.raises(RuntimeError, match="faster-whisper is not installed"):
        transcription._transcribe_faster_whisper(config, media, stem)
    with pytest.raises(RuntimeError, match="OpenAI Whisper CLI not found"):
        transcription._transcribe_openai_whisper(config, media, stem)
    with pytest.raises(RuntimeError, match="not allowed for local-only execution"):
        transcription._run_local_engine(config, "openai_whisper", media, stem, tmp_path)
    with pytest.raises(RuntimeError, match="unsupported local engine: bogus"):
        transcription._run_local_engine(config, "bogus", media, stem, tmp_path)


def test_custom_engine_rejects_empty_command_placeholder_and_missing_output(
    tmp_path: Path,
):
    config = _engine_config(tmp_path, {"engine": "auto", "custom_command": []})
    media = tmp_path / "clip.wav"
    media.write_bytes(b"audio")
    stem = tmp_path / "staging" / "transcript"

    with pytest.raises(RuntimeError, match="zoom.custom_command is empty"):
        transcription._transcribe_custom(config, media, stem)

    config.payload["zoom"]["custom_command"] = [
        sys.executable,
        "-c",
        "pass",
        "{unknown_placeholder}",
    ]
    with pytest.raises(RuntimeError, match="unsupported custom command placeholder"):
        transcription._transcribe_custom(config, media, stem)

    config.payload["zoom"]["custom_command"] = [sys.executable, "-c", "pass"]
    with pytest.raises(RuntimeError, match="did not create"):
        transcription._transcribe_custom(config, media, stem)


def test_prepare_wav_passes_through_existing_wav_input(tmp_path: Path):
    config = _engine_config(tmp_path, {"engine": "auto"})
    media = tmp_path / "clip.wav"
    media.write_bytes(b"audio")

    assert transcription._prepare_wav(config, media, tmp_path) == media


# --- Quality and speaker assessment -----------------------------------------


def test_quality_assessment_requires_output_and_flags_invalid_cues(tmp_path: Path):
    config = _engine_config(tmp_path, {"engine": "auto"})
    missing = tmp_path / "missing.vtt"
    txt_only = tmp_path / "plain.txt"
    txt_only.write_text("no timestamps here", encoding="utf-8")

    txt_quality = transcription.assess_transcript_quality(missing, txt_only, 60.0)
    assert txt_quality["quality_status"] == "partial"
    assert txt_quality["timestamp_coverage"] == 0.0
    assert "no valid ordered timestamp cues" in txt_quality["error"]

    out_of_order = tmp_path / "unordered.vtt"
    out_of_order.write_text(
        "WEBVTT\n\n"
        "00:00:10.000 --> 00:00:11.000\nsecond\n\n"
        "00:00:01.000 --> 00:00:02.000\nfirst\n",
        encoding="utf-8",
    )
    ordered_quality = transcription.assess_transcript_quality(out_of_order, missing, 60.0)
    assert ordered_quality["quality_status"] == "partial"

    empty = tmp_path / "empty.vtt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="output is empty"):
        transcription.assess_transcript_quality(empty, missing, None)


def test_speaker_label_status_distinguishes_resolved_unresolved_and_absent():
    assert transcription._speaker_label_status("<v Alice>hello</v>") == "present"
    assert transcription._speaker_label_status("<v>hello</v>") == "unresolved"
    assert transcription._speaker_label_status("Alice: hello") == "present"
    assert transcription._speaker_label_status("plain narration") == "absent"


def test_timestamp_helpers_reject_malformed_values():
    assert transcription._timestamp_seconds("1:02.500") == 62.5
    assert transcription._timestamp_seconds("00:01:02.500") == 62.5
    with pytest.raises(ValueError, match="invalid timestamp"):
        transcription._timestamp_seconds("1:2:3:4")


def test_path_is_within_rejects_paths_outside_the_parent(tmp_path: Path):
    parent = tmp_path / "data"
    parent.mkdir()

    assert transcription._path_is_within(parent / "nested" / "file.mp4", parent) is True
    assert transcription._path_is_within(tmp_path / "elsewhere.mp4", parent) is False


# --- Job version guard -------------------------------------------------------


def _guard_row(con, **overrides):
    values = {
        "media_version_id": "version-1",
        "version_exists": "version-1",
        "version_source_id": "source-1",
        "media_source_id": "source-1",
        "current_source_version_id": "version-1",
        "version_content_sha256": "digest",
        "current_content_sha256": "digest",
    }
    values.update(overrides)
    query = "SELECT " + ", ".join(f":{key} AS {key}" for key in values)
    return con.execute(query, values).fetchone()


def test_job_version_guard_rejects_missing_binding_and_mismatched_bytes(tmp_path: Path):
    con = connect(tmp_path / "guard.sqlite")
    media = tmp_path / "media.mp4"
    media.write_bytes(b"current bytes")
    digest = hashlib.sha256(b"current bytes").hexdigest()
    try:
        good = _guard_row(
            con, version_content_sha256=digest, current_content_sha256=digest
        )
        assert transcription._job_version_matches_current_source(good, media) == (True, "")

        missing = _guard_row(con, media_version_id="", version_exists=None)
        ok, reason = transcription._job_version_matches_current_source(missing, media)
        assert ok is False
        assert "missing from provenance state" in reason

        other_source = _guard_row(con, version_source_id="source-2")
        ok, reason = transcription._job_version_matches_current_source(other_source, media)
        assert ok is False
        assert "bound to another source" in reason

        provenance_mismatch = _guard_row(
            con, version_content_sha256="digest", current_content_sha256="other"
        )
        ok, reason = transcription._job_version_matches_current_source(
            provenance_mismatch, media
        )
        assert ok is False
        assert "provenance does not match" in reason

        stale_metadata = _guard_row(
            con, version_content_sha256="stale", current_content_sha256="stale"
        )
        ok, reason = transcription._job_version_matches_current_source(stale_metadata, media)
        assert ok is False
        assert "do not match the job version" in reason

        unreadable = _guard_row(
            con,
            version_content_sha256=digest,
            current_content_sha256=digest,
        )
        ok, reason = transcription._job_version_matches_current_source(
            unreadable, tmp_path / "gone.mp4"
        )
        assert ok is False
        assert "could not be verified" in reason

        changed = _guard_row(
            con, version_content_sha256=digest, current_content_sha256=digest
        )
        media.write_bytes(b"different bytes")
        ok, reason = transcription._job_version_matches_current_source(changed, media)
        assert ok is False
        assert "do not match the job version" in reason
    finally:
        con.close()


# --- Transcribe job accounting ----------------------------------------------


def _txt_only_command(script: Path) -> list[str]:
    return [sys.executable, str(script), "--out", "{output_txt}"]


def _txt_only_script(tmp_path: Path) -> Path:
    script = tmp_path / "txt_only_engine.py"
    script.write_text(
        "import argparse\n"
        "from pathlib import Path\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--out', required=True)\n"
        "args = parser.parse_args()\n"
        "Path(args.out).write_text('plain txt result\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_txt_only_engine_output_is_recorded_as_partial_markdown(tmp_path: Path):
    script = _txt_only_script(tmp_path)
    config, con = _config_and_db(tmp_path, _txt_only_command(script))
    try:
        _scan_media(config, con, count=1)
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT * FROM transcription_job").fetchone()
        markdown = Path(job["output_path"]).read_text(encoding="utf-8")
    finally:
        con.close()

    assert result["partial"] == 1
    assert result["succeeded"] == 0
    assert job["status"] == "partial"
    assert job["quality_status"] == "partial"
    assert "plain txt result" in markdown


def test_scope_review_is_held_even_when_no_local_engine_is_available(tmp_path: Path):
    config, con = _config_and_db(tmp_path, [str(tmp_path / "missing-engine"), "{input}"])
    try:
        source_id, _version_id = _add_source(
            config,
            con,
            "data/Zoom/2026-09-18 Held No Engine/recording.mp4",
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

        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute(
            "SELECT status, approval_status, error FROM transcription_job"
        ).fetchone()
    finally:
        con.close()

    assert result["blocked"] == 0
    assert result["skipped"] == 1
    assert job["status"] == "pending_approval"
    assert job["approval_status"] == "pending_approval"


def test_source_outside_data_root_is_blocked_without_running_the_engine(tmp_path: Path):
    script = _engine_script(tmp_path)
    input_log = tmp_path / "engine-input.bin"
    config, con = _config_and_db(tmp_path, _recording_command(script, input_log))
    relative_path = "data/Zoom/2026-09-19 Outside Root/recording.mp4"
    try:
        _add_source(config, con, relative_path, b"outside media")
        scan_zoom(config, con)
        moved = tmp_path / "outside" / "recording.mp4"
        moved.parent.mkdir(parents=True)
        (config.root / relative_path).replace(moved)
        con.execute(
            "UPDATE source_record SET absolute_path=? WHERE relative_path=?",
            (str(moved), relative_path),
        )
        con.commit()

        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT status, error FROM transcription_job").fetchone()
    finally:
        con.close()

    assert result["attempted"] == 0
    assert result["blocked"] == 1
    assert job["status"] == "blocked"
    assert "outside the configured data root" in job["error"]
    assert not input_log.exists()


def test_source_no_longer_eligible_is_blocked_without_running_the_engine(tmp_path: Path):
    script = _engine_script(tmp_path)
    input_log = tmp_path / "engine-input.bin"
    config, con = _config_and_db(tmp_path, _recording_command(script, input_log))
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-20 Ineligible/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        con.execute("UPDATE source_record SET classification='Personal', scope='Personal'")
        con.commit()

        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        job = con.execute("SELECT status, error FROM transcription_job").fetchone()
    finally:
        con.close()

    assert result["attempted"] == 0
    assert result["blocked"] == 1
    assert job["status"] == "blocked"
    assert "no longer current and eligible" in job["error"]
    assert not input_log.exists()


def test_partial_retry_of_a_good_transcript_is_kept_as_a_separate_attempt(
    tmp_path: Path,
):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-21 Prior Good/recording.mp4",
            b"media",
        )
        scan_zoom(config, con)
        transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve_run=True
        )
        good_job = con.execute("SELECT * FROM transcription_job").fetchone()
        good_path = Path(good_job["output_path"])
        original = good_path.read_text(encoding="utf-8")

        con.execute("UPDATE meeting_group SET duration_seconds=10.0")
        con.execute(
            "UPDATE transcription_job SET status='failed', approval_status='approved'"
        )
        con.commit()
        config.payload["zoom"]["custom_command"] = _command(script, mode="partial")
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", retry_errors=True
        )
        job = con.execute("SELECT * FROM transcription_job").fetchone()
        group = con.execute("SELECT status FROM meeting_group").fetchone()
    finally:
        con.close()

    assert result["partial"] == 1
    assert job["status"] == "partial"
    assert job["output_path"] != str(good_path)
    assert "attempts" in job["output_path"]
    assert good_path.read_text(encoding="utf-8") == original
    assert group["status"] == "partial"


def test_transcribe_jobs_accepts_the_approve_alias(tmp_path: Path):
    script = _engine_script(tmp_path)
    config, con = _config_and_db(tmp_path, _command(script))
    try:
        _scan_media(config, con, count=2)
        result = transcription.transcribe_jobs(
            config, con, requested_engine="custom", approve=True, max_files=1
        )
    finally:
        con.close()

    assert result["attempted"] == 1
    assert result["succeeded"] == 1
