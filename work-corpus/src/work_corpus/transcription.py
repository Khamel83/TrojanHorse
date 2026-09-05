from __future__ import annotations

import importlib.util
import os
import re
import shlex
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from .util import (
    atomic_write_text,
    ensure_dir,
    executable,
    now_iso,
    provenance_header,
    read_text_guess,
    run_command,
    sha256_file,
    stable_id,
    vtt_or_srt_to_markdown,
)
from .zoom import FINAL_MEDIA_EXTENSIONS, zoom_source_is_eligible

_TIMESTAMP_RE = re.compile(
    r"^\s*(?P<start>(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3})"
    r"\s*-->\s*"
    r"(?P<end>(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3})"
)


def _format_vtt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _command_parts(template: Any) -> List[str]:
    if isinstance(template, str):
        return shlex.split(template)
    if isinstance(template, (list, tuple)):
        return [str(part) for part in template]
    return []


def _resolved_executable(value: str) -> Optional[str]:
    path = Path(value).expanduser()
    if path.exists() and path.is_file():
        return str(path.resolve())
    return executable(value)


def _engine_available(config: Config, requested: str) -> Tuple[Optional[str], str]:
    """Resolve only engines that execute locally and never upload input."""
    # Config can be changed by a caller between runs; re-apply the boundary at
    # the execution edge instead of trusting an earlier load-time validation.
    config._validate_local_transcription()
    section = config.section("zoom")
    requested = (requested or str(section.get("engine", "auto"))).casefold()

    if requested == "custom":
        parts = _command_parts(section.get("custom_command", []))
        if not parts:
            return None, "zoom.custom_command is empty"
        if not _resolved_executable(parts[0]):
            return None, f"custom transcription command not found: {parts[0]}"
        return "custom", ""

    if requested in {"whisper_cpp", "whisper.cpp"}:
        command = _resolved_executable(
            str(section.get("whisper_cpp_command", "whisper-cli"))
        )
        model = str(section.get("whisper_cpp_model", "")).strip()
        if not command:
            return None, "whisper.cpp command not found"
        if not model or not Path(model).expanduser().is_file():
            return None, "whisper.cpp model path is not configured or does not exist"
        return "whisper_cpp", ""

    if requested == "faster_whisper":
        if importlib.util.find_spec("faster_whisper") is None:
            return None, "Python package faster-whisper is not installed"
        return "faster_whisper", ""

    if requested == "openai_whisper":
        return None, (
            "OpenAI Whisper CLI is not allowed for local-only execution because "
            "its model path may download models; configure a verified local "
            "engine instead"
        )

    if requested != "auto":
        return None, f"unknown transcription engine: {requested}"

    parts = _command_parts(section.get("custom_command", []))
    if parts and _resolved_executable(parts[0]):
        return "custom", ""

    command = _resolved_executable(
        str(section.get("whisper_cpp_command", "whisper-cli"))
    )
    model = str(section.get("whisper_cpp_model", "")).strip()
    if command and model and Path(model).expanduser().is_file():
        return "whisper_cpp", ""
    if importlib.util.find_spec("faster_whisper") is not None:
        return "faster_whisper", ""
    return None, (
        "no configured local transcription engine found. "
        "OpenAI Whisper CLI is not allowed because its model path may download "
        "models; configure a local command or verified local Whisper model."
    )


def _engine_details(config: Config, engine: str) -> Tuple[str, str]:
    section = config.section("zoom")
    model = str(section.get("model", "large-v3"))
    if engine == "custom":
        parts = _command_parts(section.get("custom_command", []))
        return str(_resolved_executable(parts[0]) or parts[0]), model
    if engine == "whisper_cpp":
        command = str(
            _resolved_executable(
                str(section.get("whisper_cpp_command", "whisper-cli"))
            )
            or section.get("whisper_cpp_command", "whisper-cli")
        )
        return command, str(section.get("whisper_cpp_model", ""))
    if engine == "faster_whisper":
        return "python:faster-whisper", model
    if engine == "openai_whisper":
        return str(_resolved_executable("whisper") or "whisper"), model
    return engine, model


def _prepare_wav(config: Config, media_path: Path, temp_dir: Path) -> Path:
    if media_path.suffix.lower() == ".wav":
        return media_path
    ffmpeg_name = str(config.get("zoom", "ffmpeg_command", "ffmpeg"))
    ffmpeg = _resolved_executable(ffmpeg_name)
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to transcode this media file but was not found")
    wav = temp_dir / "audio-16k-mono.wav"
    code, _out, err = run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ],
        timeout=None,
    )
    if code != 0 or not wav.exists():
        raise RuntimeError(f"ffmpeg conversion failed: {err.strip()}")
    return wav


def _transcribe_whisper_cpp(
    config: Config,
    media_path: Path,
    output_stem: Path,
    temp_dir: Path,
) -> Tuple[Path, Path]:
    section = config.section("zoom")
    command = _resolved_executable(
        str(section.get("whisper_cpp_command", "whisper-cli"))
    )
    model = Path(str(section.get("whisper_cpp_model", ""))).expanduser()
    if not command or not model.is_file():
        raise RuntimeError("whisper.cpp command/model is not configured")
    wav = _prepare_wav(config, media_path, temp_dir)
    ensure_dir(output_stem.parent)
    args = [
        command,
        "-m",
        str(model),
        "-f",
        str(wav),
        "-l",
        str(section.get("language", "en")),
        "-otxt",
        "-ovtt",
        "-of",
        str(output_stem),
    ]
    code, out, err = run_command(args, timeout=None)
    vtt = Path(str(output_stem) + ".vtt")
    txt = Path(str(output_stem) + ".txt")
    if code != 0 or not (vtt.exists() or txt.exists()):
        raise RuntimeError(f"whisper.cpp failed: {(err or out).strip()}")
    return vtt, txt


def _transcribe_faster_whisper(
    config: Config,
    media_path: Path,
    output_stem: Path,
) -> Tuple[Path, Path]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    section = config.section("zoom")
    model_name = str(section.get("model", "large-v3"))
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        local_files_only=True,
    )
    segments, _info = model.transcribe(
        str(media_path),
        language=str(section.get("language", "en")) or None,
        vad_filter=True,
        beam_size=5,
    )
    ensure_dir(output_stem.parent)
    vtt_path = Path(str(output_stem) + ".vtt")
    txt_path = Path(str(output_stem) + ".txt")
    vtt_lines = ["WEBVTT", ""]
    txt_lines: List[str] = []
    for index, segment in enumerate(segments, start=1):
        text = segment.text.strip()
        if not text:
            continue
        vtt_lines.extend(
            [
                str(index),
                f"{_format_vtt_time(segment.start)} --> {_format_vtt_time(segment.end)}",
                text,
                "",
            ]
        )
        txt_lines.append(text)
    atomic_write_text(vtt_path, "\n".join(vtt_lines).rstrip() + "\n")
    atomic_write_text(txt_path, "\n".join(txt_lines).rstrip() + "\n")
    return vtt_path, txt_path


def _transcribe_custom(
    config: Config,
    media_path: Path,
    output_stem: Path,
) -> Tuple[Path, Path]:
    """Run a configured local command without invoking a shell."""
    section = config.section("zoom")
    parts = _command_parts(section.get("custom_command", []))
    if not parts:
        raise RuntimeError("zoom.custom_command is empty")

    ensure_dir(output_stem.parent)
    output_vtt = Path(str(output_stem) + ".vtt")
    output_txt = Path(str(output_stem) + ".txt")
    values = {
        "input": str(media_path),
        "output_stem": str(output_stem),
        "output_vtt": str(output_vtt),
        "output_txt": str(output_txt),
        "language": str(section.get("language", "en")),
        "model": str(section.get("model", "large-v3")),
    }
    try:
        args = [part.format(**values) for part in parts]
    except KeyError as exc:
        raise RuntimeError(f"unsupported custom command placeholder: {exc}") from exc
    code, out, err = run_command(args, timeout=None)
    if code != 0:
        raise RuntimeError(f"custom transcription command failed: {(err or out).strip()}")
    if not (output_vtt.exists() or output_txt.exists()):
        raise RuntimeError(
            "custom transcription command completed but did not create "
            f"{output_vtt.name} or {output_txt.name}"
        )
    return output_vtt, output_txt


def _transcribe_openai_whisper(
    config: Config,
    media_path: Path,
    output_stem: Path,
) -> Tuple[Path, Path]:
    command = _resolved_executable("whisper")
    if not command:
        raise RuntimeError("OpenAI Whisper CLI not found")
    section = config.section("zoom")
    ensure_dir(output_stem.parent)
    code, out, err = run_command(
        [
            command,
            str(media_path),
            "--model",
            str(section.get("model", "large-v3")),
            "--language",
            str(section.get("language", "en")),
            "--output_dir",
            str(output_stem.parent),
            "--output_format",
            "all",
        ],
        timeout=None,
    )
    generated_base = output_stem.parent / media_path.stem
    generated_vtt = generated_base.with_suffix(".vtt")
    generated_txt = generated_base.with_suffix(".txt")
    target_vtt = Path(str(output_stem) + ".vtt")
    target_txt = Path(str(output_stem) + ".txt")
    if code != 0 or not (generated_vtt.exists() or generated_txt.exists()):
        raise RuntimeError(f"OpenAI Whisper CLI failed: {(err or out).strip()}")
    if generated_vtt.exists() and generated_vtt != target_vtt:
        os.replace(generated_vtt, target_vtt)
    if generated_txt.exists() and generated_txt != target_txt:
        os.replace(generated_txt, target_txt)
    return target_vtt, target_txt


def _run_local_engine(
    config: Config,
    engine: str,
    media_path: Path,
    output_stem: Path,
    temp_dir: Path,
) -> Tuple[Path, Path]:
    if engine == "custom":
        return _transcribe_custom(config, media_path, output_stem)
    if engine == "whisper_cpp":
        return _transcribe_whisper_cpp(config, media_path, output_stem, temp_dir)
    if engine == "faster_whisper":
        return _transcribe_faster_whisper(config, media_path, output_stem)
    if engine == "openai_whisper":
        raise RuntimeError(
            "OpenAI Whisper CLI is not allowed for local-only execution because "
            "its model path may download models"
        )
    raise RuntimeError(f"unsupported local engine: {engine}")


def _timestamp_seconds(value: str) -> float:
    fields = value.replace(",", ".").split(":")
    if len(fields) == 2:
        hours = 0.0
        minutes, seconds = fields
    elif len(fields) == 3:
        hours, minutes, seconds = fields
    else:
        raise ValueError(f"invalid timestamp: {value}")
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def _parse_output_cues(text: str) -> Tuple[List[Tuple[float, float, str]], bool]:
    cues: List[Tuple[float, float, str]] = []
    start: Optional[float] = None
    end: Optional[float] = None
    body: List[str] = []
    timestamp_seen = False
    valid = True

    def flush() -> None:
        nonlocal start, end, body, valid
        if start is None or end is None:
            body = []
            return
        text_body = " ".join(part.strip() for part in body if part.strip()).strip()
        if not text_body or end < start:
            valid = False
        else:
            cues.append((start, end, text_body))
        start = None
        end = None
        body = []

    for raw in text.replace("\ufeff", "").splitlines():
        line = raw.strip()
        match = _TIMESTAMP_RE.match(line)
        if match:
            flush()
            timestamp_seen = True
            try:
                start = _timestamp_seconds(match.group("start"))
                end = _timestamp_seconds(match.group("end"))
            except ValueError:
                valid = False
            continue
        if not line or line == "WEBVTT" or line.startswith("NOTE"):
            flush()
            continue
        if line.isdigit() and start is None:
            continue
        if start is not None:
            body.append(line)
    flush()

    previous = -1.0
    for cue_start, cue_end, _text in cues:
        if cue_start < previous or cue_end < cue_start:
            valid = False
        previous = cue_start
    return cues, timestamp_seen and valid and bool(cues)


def _speaker_label_status(text: str) -> str:
    if re.search(r"<v\s+[^>]+>", text, flags=re.IGNORECASE):
        return "present"
    for line in text.splitlines():
        if "-->" not in line and re.match(
            r"^\s*[^\s:][^:]{0,60}:\s*\S", line
        ):
            return "present"
    if re.search(r"<v\s*>", text, flags=re.IGNORECASE):
        return "unresolved"
    return "absent"


def assess_transcript_quality(
    vtt_path: Path,
    txt_path: Path,
    duration_seconds: Optional[float],
) -> Dict[str, Any]:
    """Assess a local output without promoting quality warnings to facts."""
    vtt_text = ""
    txt_text = ""
    if vtt_path.exists():
        vtt_text = read_text_guess(vtt_path)
    if txt_path.exists():
        txt_text = read_text_guess(txt_path)
    source_text = vtt_text.strip() or txt_text.strip()
    if not source_text:
        raise RuntimeError("transcription output is empty")

    cues: List[Tuple[float, float, str]] = []
    timestamped = False
    if vtt_text.strip():
        cues, timestamped = _parse_output_cues(vtt_text)
    if timestamped:
        last_end = max(end for _start, end, _body in cues)
        if duration_seconds and duration_seconds > 0:
            coverage = min(1.0, max(0.0, last_end / float(duration_seconds)))
        else:
            coverage = 1.0
        quality_status = "good" if coverage >= 0.5 else "partial"
        quality_error = None if quality_status == "good" else "timestamp coverage is below 50%"
    else:
        coverage = 0.0
        quality_status = "partial"
        quality_error = "non-empty output has no valid ordered timestamp cues"

    return {
        "quality_status": quality_status,
        "timestamp_coverage": coverage,
        "speaker_label_status": _speaker_label_status(source_text),
        "error": quality_error,
        "text": source_text,
    }


def _create_markdown(
    config: Config,
    media_row: sqlite3.Row,
    group_row: sqlite3.Row,
    vtt_path: Path,
    txt_path: Path,
    engine: str,
    model: str,
    output_path: Optional[Path] = None,
) -> Path:
    if vtt_path.exists() and read_text_guess(vtt_path).strip():
        body = vtt_or_srt_to_markdown(
            read_text_guess(vtt_path),
            Path(group_row["folder_relative_path"]).name,
        )
    elif txt_path.exists():
        body = (
            f"# {Path(group_row['folder_relative_path']).name}\n\n"
            f"{read_text_guess(txt_path).strip()}\n"
        )
    else:
        raise RuntimeError("transcription output is empty")

    if output_path is None:
        configured = group_row["transcript_path"]
        output_path = Path(configured) if configured else (
            config.corpus_dir
            / "transcripts"
            / "zoom"
            / "generated"
            / f"{group_row['group_id']}.md"
        )
    config.assert_derived_path(output_path)
    header = provenance_header(
        {
            "source_id": media_row["source_id"],
            "source_system": "zoom",
            "original_path": media_row["absolute_path"],
            "relative_path": media_row["relative_path"],
            "original_date": media_row["date_hint"] or "",
            "file_type": "generated_local_transcript",
            "parser": f"{engine}:{model}",
            "generated_at": now_iso(),
        }
    )
    linkage = (
        f"<!-- meeting_group_id: {group_row['group_id']}; "
        f"source_version_id: {media_row['source_version_id']} -->\n"
    )
    atomic_write_text(output_path, header + linkage + body.rstrip() + "\n")
    return output_path


def approve_transcription_run(con: sqlite3.Connection) -> int:
    """Approve the complete pending local queue atomically."""
    cursor = con.execute(
        """
        UPDATE transcription_job
        SET status='queued', approval_status='approved', error=NULL
        WHERE status IN ('pending_approval', 'pending')
          AND COALESCE(approval_status, 'pending_approval') <> 'not_needed'
        """
    )
    con.commit()
    return max(cursor.rowcount, 0)


def _checkpoint(
    con: sqlite3.Connection,
    job_id: str,
    source_version_id: Optional[str],
    error: Optional[str],
) -> None:
    checkpoint_id = stable_id("tx-checkpoint", "local_transcription", "zoom")
    previous = con.execute(
        "SELECT item_count FROM ingestion_checkpoint WHERE checkpoint_id=?",
        (checkpoint_id,),
    ).fetchone()
    count = int(previous[0]) if previous else 0
    con.execute(
        """
        INSERT INTO ingestion_checkpoint (
            checkpoint_id, provider, root_key, cursor, source_version_id,
            last_successful_retrieval, item_count, error, updated_at
        ) VALUES (?, 'local_transcription', NULL, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(checkpoint_id) DO UPDATE SET
            cursor=excluded.cursor,
            source_version_id=excluded.source_version_id,
            last_successful_retrieval=excluded.last_successful_retrieval,
            item_count=excluded.item_count,
            error=excluded.error,
            updated_at=excluded.updated_at
        """,
        (
            checkpoint_id,
            job_id,
            source_version_id,
            now_iso(),
            count + 1,
            error,
            now_iso(),
        ),
    )
    con.commit()


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _job_version_matches_current_source(
    job: sqlite3.Row,
    media_path: Path,
) -> Tuple[bool, str]:
    """Prove that the bytes at the current source path are the job's version."""
    job_version_id = str(job["media_version_id"] or "")
    if not job_version_id or not job["version_exists"]:
        return False, "source version is missing from provenance state"
    if str(job["version_source_id"] or "") != str(job["media_source_id"] or ""):
        return False, "transcription job source version is bound to another source"
    if str(job["current_source_version_id"] or "") != job_version_id:
        return (
            False,
            "transcription job targets a historical source version; current "
            "source bytes are not a matching version",
        )
    expected_hash = str(job["version_content_sha256"] or "")
    if not expected_hash or str(job["current_content_sha256"] or "") != expected_hash:
        return False, "current source provenance does not match the job version"
    try:
        actual_hash = sha256_file(media_path)
    except (OSError, ValueError) as exc:
        return False, f"current source bytes could not be verified: {exc}"
    if actual_hash != expected_hash:
        return False, "current source bytes do not match the job version"
    return True, ""


def _hold_scope_review_job(con: sqlite3.Connection, job_id: str) -> None:
    con.execute(
        """
        UPDATE transcription_job
        SET status='pending_approval', approval_status='pending_approval',
            error=?, completed_at=NULL
        WHERE job_id=?
        """,
        ("Zoom group requires scope review", job_id),
    )


def requeue_engine_preflight_blocks(con: sqlite3.Connection) -> int:
    """Requeue jobs blocked only because no local engine was discovered."""
    cursor = con.execute(
        """
        UPDATE transcription_job
        SET status='queued', approval_status='approved', error=NULL,
            started_at=NULL, completed_at=NULL
        WHERE status='blocked'
          AND approval_status='approved'
          AND (
              error LIKE 'no configured local transcription engine found.%'
              OR error LIKE 'custom transcription command not found:%'
              OR error = 'whisper.cpp command not found'
              OR error = 'whisper.cpp model path is not configured or does not exist'
              OR error = 'Python package faster-whisper is not installed'
          )
        """
    )
    con.commit()
    return max(cursor.rowcount, 0)


def _result() -> Dict[str, int]:
    return {
        "attempted": 0,
        "succeeded": 0,
        "partial": 0,
        "failed": 0,
        "blocked": 0,
        "artifact": 0,
        "skipped": 0,
        "retried": 0,
        "requeued": 0,
        "pending_approval": 0,
        # Compatibility aliases for callers of the bootstrap command.
        "complete": 0,
        "errors": 0,
    }


def transcribe_jobs(
    config: Config,
    con: sqlite3.Connection,
    requested_engine: str = "",
    max_files: Optional[int] = None,
    all_jobs: bool = False,
    retry_errors: bool = False,
    retry_blocked: bool = False,
    approve_run: bool = False,
    approve: Optional[bool] = None,
) -> Dict[str, int]:
    """Run approved local jobs sequentially and checkpoint each terminal result."""
    if approve is not None:
        approve_run = approve
    if approve_run:
        approve_transcription_run(con)
    requeued = requeue_engine_preflight_blocks(con) if retry_blocked else 0

    # A process restart can safely return an abandoned item to the approved
    # queue. Terminal results are never reset or deleted.
    con.execute(
        """
        UPDATE transcription_job
        SET status='queued'
        WHERE status='running' AND approval_status='approved'
        """
    )
    con.execute(
        """
        UPDATE transcription_job
        SET status=CASE WHEN approval_status='approved' THEN 'queued' ELSE 'pending_approval' END
        WHERE status='pending'
        """
    )
    con.execute("UPDATE transcription_job SET status='failed' WHERE status='error'")
    con.execute("UPDATE transcription_job SET status='succeeded' WHERE status='complete'")
    con.execute(
        """
        UPDATE transcription_job
        SET status='pending_approval', approval_status='pending_approval',
            error='Zoom group requires scope review', completed_at=NULL
        WHERE status='needs_review'
        """
    )
    con.commit()

    result = _result()
    result["requeued"] = requeued
    result["artifact"] = con.execute(
        "SELECT COUNT(*) FROM transcription_job WHERE status='artifact'"
    ).fetchone()[0]
    result["pending_approval"] = con.execute(
        "SELECT COUNT(*) FROM transcription_job WHERE status='pending_approval'"
    ).fetchone()[0]
    statuses = ["queued"]
    if retry_errors:
        statuses.append("failed")
    placeholders = ",".join("?" for _status in statuses)
    query = f"""
        SELECT j.*, g.folder_relative_path, g.transcript_path,
               g.duration_seconds, g.status AS group_status,
               s.absolute_path, s.relative_path, s.date_hint, s.source_id,
               s.status AS source_status, s.extraction_status,
               s.content_sha256, s.source_version_id,
               s.source_version_id AS current_source_version_id,
               s.content_sha256 AS current_content_sha256,
               s.classification, s.kind, s.size_bytes,
               v.source_version_id AS version_exists,
               v.source_id AS version_source_id,
               v.content_sha256 AS version_content_sha256
        FROM transcription_job j
        JOIN meeting_group g ON g.group_id=j.group_id
        JOIN source_record s ON s.source_id=j.media_source_id
        LEFT JOIN source_version v ON v.source_version_id=j.media_version_id
        WHERE j.status IN ({placeholders})
          AND j.approval_status='approved'
        ORDER BY g.folder_relative_path, j.job_id
    """
    jobs = con.execute(query, statuses).fetchall()
    if max_files is not None:
        jobs = jobs[: max(0, max_files)]
    result["retried"] = sum(1 for job in jobs if job["status"] == "failed")
    if not jobs:
        result["complete"] = result["succeeded"]
        result["errors"] = result["failed"]
        return result

    engine, reason = _engine_available(config, requested_engine)
    if engine is None:
        for job in jobs:
            if job["group_status"] == "needs_review":
                _hold_scope_review_job(con, job["job_id"])
                result["skipped"] += 1
                con.commit()
                continue
            con.execute(
                """
                UPDATE transcription_job
                SET status='blocked', approval_status='approved', error=?, completed_at=?
                WHERE job_id=?
                """,
                (reason, now_iso(), job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], reason)
            result["blocked"] += 1
        result["complete"] = result["succeeded"]
        result["errors"] = result["failed"]
        return result

    local_engine, local_model = _engine_details(config, engine)
    section = config.section("zoom")
    language = str(section.get("language", "en"))

    for job in jobs:
        if job["group_status"] == "needs_review":
            _hold_scope_review_job(con, job["job_id"])
            con.commit()
            result["skipped"] += 1
            continue

        media_path = Path(str(job["absolute_path"]))
        if media_path.suffix.lower() not in FINAL_MEDIA_EXTENSIONS:
            reason_text = "transcription input is not a final MP4 or M4A"
            con.execute(
                "UPDATE transcription_job SET status='artifact', error=?, completed_at=? WHERE job_id=?",
                (reason_text, now_iso(), job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], reason_text)
            result["artifact"] += 1
            continue
        if not _path_is_within(media_path, config.data_dir):
            reason_text = "transcription input is outside the configured data root"
            con.execute(
                "UPDATE transcription_job SET status='blocked', error=?, completed_at=? WHERE job_id=?",
                (reason_text, now_iso(), job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], reason_text)
            result["blocked"] += 1
            continue
        version_matches, version_reason = _job_version_matches_current_source(
            job, media_path
        )
        if not version_matches:
            con.execute(
                "UPDATE transcription_job SET status='blocked', error=?, completed_at=? WHERE job_id=?",
                (version_reason, now_iso(), job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], version_reason)
            result["blocked"] += 1
            continue
        if not zoom_source_is_eligible(config, con, job):
            reason_text = "Zoom source version is no longer current and eligible"
            con.execute(
                "UPDATE transcription_job SET status='blocked', error=?, completed_at=? WHERE job_id=?",
                (reason_text, now_iso(), job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], reason_text)
            result["blocked"] += 1
            continue

        result["attempted"] += 1
        con.execute(
            """
            UPDATE transcription_job
            SET status='running', engine=?, model=?, local_engine=?, local_model=?,
                language=?, started_at=?, error=NULL
            WHERE job_id=?
            """,
            (
                engine,
                str(section.get("model", "large-v3")),
                local_engine,
                local_model,
                language,
                now_iso(),
                job["job_id"],
            ),
        )
        con.commit()

        temp_root = ensure_dir(config.state_dir / "tmp")
        temp_dir = Path(
            tempfile.mkdtemp(prefix=f"{job['job_id']}-", dir=str(temp_root))
        )
        try:
            staged_stem = temp_dir / "transcript"
            vtt_path, txt_path = _run_local_engine(
                config, engine, media_path, staged_stem, temp_dir
            )
            for output in (vtt_path, txt_path):
                if output.exists() and not _path_is_within(output, temp_dir):
                    raise RuntimeError("local engine output escaped its staging directory")
            quality = assess_transcript_quality(
                vtt_path,
                txt_path,
                job["duration_seconds"],
            )
            group_row = con.execute(
                "SELECT * FROM meeting_group WHERE group_id=?", (job["group_id"],)
            ).fetchone()
            media_row = con.execute(
                "SELECT * FROM source_record WHERE source_id=?", (job["media_source_id"],)
            ).fetchone()
            prior_path = Path(job["output_path"]) if job["output_path"] else None
            prior_good = bool(
                prior_path
                and prior_path.exists()
                and job["quality_status"] == "good"
            )
            final_output = Path(str(job["output_stem"]) + ".md")
            if prior_good and quality["quality_status"] != "good":
                final_output = (
                    config.corpus_dir
                    / "transcripts"
                    / "zoom"
                    / "generated"
                    / "attempts"
                    / f"{job['job_id']}-{stable_id('attempt', job['job_id'], now_iso())}.md"
                )
            markdown_path = _create_markdown(
                config,
                media_row,
                group_row,
                vtt_path,
                txt_path,
                engine,
                str(section.get("model", "large-v3")),
                output_path=final_output,
            )
            output_hash = sha256_file(markdown_path)
            status = (
                "succeeded"
                if quality["quality_status"] == "good"
                else "partial"
            )
            con.execute(
                """
                UPDATE transcription_job
                SET status=?, completed_at=?, timestamp_coverage=?,
                    speaker_label_status=?, quality_status=?, output_path=?,
                    output_sha256=?, error=?
                WHERE job_id=?
                """,
                (
                    status,
                    now_iso(),
                    quality["timestamp_coverage"],
                    quality["speaker_label_status"],
                    quality["quality_status"],
                    str(markdown_path),
                    output_hash,
                    quality["error"],
                    job["job_id"],
                ),
            )
            if not prior_good or status == "succeeded":
                con.execute(
                    """
                    UPDATE meeting_group
                    SET status=?, transcript_path=?, updated_at=?
                    WHERE group_id=?
                    """,
                    (status, str(markdown_path), now_iso(), job["group_id"]),
                )
            else:
                con.execute(
                    "UPDATE meeting_group SET status='partial', updated_at=? WHERE group_id=?",
                    (now_iso(), job["group_id"]),
                )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], None)
            result[status] += 1
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            con.execute(
                """
                UPDATE transcription_job
                SET status='failed', completed_at=?, error=?
                WHERE job_id=?
                """,
                (now_iso(), error, job["job_id"]),
            )
            con.commit()
            _checkpoint(con, job["job_id"], job["media_version_id"], error)
            result["failed"] += 1
        finally:
            if not bool(section.get("keep_temporary_wav", False)):
                shutil.rmtree(temp_dir, ignore_errors=True)

    result["complete"] = result["succeeded"]
    result["errors"] = result["failed"]
    return result
