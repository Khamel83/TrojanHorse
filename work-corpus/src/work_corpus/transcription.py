from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import shlex
import sqlite3
import tempfile
import time
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
    vtt_or_srt_to_markdown,
)
from .zoom import zoom_group_is_eligible, zoom_source_is_eligible


def _format_vtt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _engine_available(config: Config, requested: str) -> Tuple[Optional[str], str]:
    section = config.section("zoom")
    requested = requested or str(section.get("engine", "auto"))

    if requested == "custom":
        command_template = section.get("custom_command", [])
        if not command_template:
            return None, "zoom.custom_command is empty"
        if isinstance(command_template, str):
            parts = shlex.split(command_template)
        else:
            parts = [str(part) for part in command_template]
        if not parts:
            return None, "zoom.custom_command is empty"
        command_name = parts[0]
        if not (Path(command_name).expanduser().exists() or executable(command_name)):
            return None, f"custom transcription command not found: {command_name}"
        return "custom", ""

    if requested in {"whisper_cpp", "whisper.cpp"}:
        command = executable(str(section.get("whisper_cpp_command", "whisper-cli")))
        model = str(section.get("whisper_cpp_model", "")).strip()
        if not command:
            return None, "whisper.cpp command not found"
        if not model or not Path(model).expanduser().exists():
            return None, "whisper.cpp model path is not configured or does not exist"
        return "whisper_cpp", ""

    if requested == "faster_whisper":
        if importlib.util.find_spec("faster_whisper") is None:
            return None, "Python package faster-whisper is not installed"
        return "faster_whisper", ""

    if requested == "openai_whisper":
        command = executable("whisper")
        if not command:
            return None, "OpenAI Whisper CLI command 'whisper' not found"
        return "openai_whisper", ""

    if requested != "auto":
        return None, f"unknown transcription engine: {requested}"

    command_template = section.get("custom_command", [])
    if command_template:
        if isinstance(command_template, str):
            custom_parts = shlex.split(command_template)
        else:
            custom_parts = [str(part) for part in command_template]
        if custom_parts and (Path(custom_parts[0]).expanduser().exists() or executable(custom_parts[0])):
            return "custom", ""

    command = executable(str(section.get("whisper_cpp_command", "whisper-cli")))
    model = str(section.get("whisper_cpp_model", "")).strip()
    if command and model and Path(model).expanduser().exists():
        return "whisper_cpp", ""
    if importlib.util.find_spec("faster_whisper") is not None:
        return "faster_whisper", ""
    return None, (
        "no configured local transcription engine found. "
        "Configure whisper.cpp plus a local model, or install faster-whisper."
    )


def _prepare_wav(config: Config, media_path: Path, temp_dir: Path) -> Path:
    if media_path.suffix.lower() == ".wav":
        return media_path
    ffmpeg_name = str(config.get("zoom", "ffmpeg_command", "ffmpeg"))
    ffmpeg = executable(ffmpeg_name)
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to transcode this media file but was not found")
    wav = temp_dir / "audio-16k-mono.wav"
    code, _out, err = run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(media_path),
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            str(wav),
        ],
        timeout=None,
    )
    if code != 0 or not wav.exists():
        raise RuntimeError(f"ffmpeg conversion failed: {err.strip()}")
    return wav


def _transcribe_whisper_cpp(config: Config, media_path: Path, output_stem: Path, temp_dir: Path) -> Tuple[Path, Path]:
    section = config.section("zoom")
    command = executable(str(section.get("whisper_cpp_command", "whisper-cli")))
    model = Path(str(section.get("whisper_cpp_model", ""))).expanduser()
    if not command or not model.exists():
        raise RuntimeError("whisper.cpp command/model is not configured")
    wav = _prepare_wav(config, media_path, temp_dir)
    ensure_dir(output_stem.parent)
    args = [
        command,
        "-m", str(model),
        "-f", str(wav),
        "-l", str(section.get("language", "en")),
        "-otxt",
        "-ovtt",
        "-of", str(output_stem),
    ]
    code, out, err = run_command(args, timeout=None)
    vtt = Path(str(output_stem) + ".vtt")
    txt = Path(str(output_stem) + ".txt")
    if code != 0 or not (vtt.exists() or txt.exists()):
        raise RuntimeError(f"whisper.cpp failed: {(err or out).strip()}")
    return vtt, txt


def _transcribe_faster_whisper(config: Config, media_path: Path, output_stem: Path) -> Tuple[Path, Path]:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed") from exc

    section = config.section("zoom")
    model_name = str(section.get("model", "small.en"))
    local_only = bool(section.get("local_models_only", True))
    model = WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        local_files_only=local_only,
    )
    segments, info = model.transcribe(
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
        vtt_lines.extend([
            str(index),
            f"{_format_vtt_time(segment.start)} --> {_format_vtt_time(segment.end)}",
            text,
            "",
        ])
        txt_lines.append(text)
    atomic_write_text(vtt_path, "\n".join(vtt_lines).rstrip() + "\n")
    atomic_write_text(txt_path, "\n".join(txt_lines).rstrip() + "\n")
    return vtt_path, txt_path


def _transcribe_custom(config: Config, media_path: Path, output_stem: Path) -> Tuple[Path, Path]:
    """Run a user-supplied local command without invoking a shell.

    Supported placeholders in each argument:
      {input}, {output_stem}, {output_vtt}, {output_txt}, {language}, {model}

    The command must create either the configured VTT or TXT output. This adapter
    is intentionally generic so an existing local transcription tool can be used
    without coupling the corpus to a particular vendor.
    """
    section = config.section("zoom")
    template = section.get("custom_command", [])
    if isinstance(template, str):
        parts = shlex.split(template)
    else:
        parts = [str(part) for part in template]
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
        "model": str(section.get("model", "small.en")),
    }
    args = [part.format(**values) for part in parts]
    code, out, err = run_command(args, timeout=None)
    if code != 0:
        raise RuntimeError(f"custom transcription command failed: {(err or out).strip()}")
    if not (output_vtt.exists() or output_txt.exists()):
        raise RuntimeError(
            "custom transcription command completed but did not create "
            f"{output_vtt.name} or {output_txt.name}"
        )
    return output_vtt, output_txt


def _transcribe_openai_whisper(config: Config, media_path: Path, output_stem: Path) -> Tuple[Path, Path]:
    command = executable("whisper")
    if not command:
        raise RuntimeError("OpenAI Whisper CLI not found")
    section = config.section("zoom")
    ensure_dir(output_stem.parent)
    code, out, err = run_command(
        [
            command,
            str(media_path),
            "--model", str(section.get("model", "small.en")),
            "--language", str(section.get("language", "en")),
            "--output_dir", str(output_stem.parent),
            "--output_format", "all",
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


def _create_markdown(
    config: Config,
    media_row: sqlite3.Row,
    group_row: sqlite3.Row,
    vtt_path: Path,
    txt_path: Path,
    engine: str,
    model: str,
) -> Path:
    if vtt_path.exists():
        body = vtt_or_srt_to_markdown(read_text_guess(vtt_path), Path(group_row["folder_relative_path"]).name)
    else:
        body = f"# {Path(group_row['folder_relative_path']).name}\n\n{read_text_guess(txt_path)}\n"
    output = Path(str(group_row["transcript_path"] or (config.corpus_dir / "transcripts" / "zoom" / "generated" / f"{group_row['group_id']}.md")))
    if output.suffix.lower() != ".md":
        output = config.corpus_dir / "transcripts" / "zoom" / "generated" / f"{group_row['group_id']}.md"
    header = provenance_header({
        "source_id": media_row["source_id"],
        "source_system": "zoom",
        "original_path": media_row["absolute_path"],
        "relative_path": media_row["relative_path"],
        "original_date": media_row["date_hint"] or "",
        "file_type": "generated_local_transcript",
        "parser": f"{engine}:{model}",
        "generated_at": now_iso(),
    })
    atomic_write_text(output, header + body.rstrip() + "\n")
    return output


def transcribe_jobs(
    config: Config,
    con: sqlite3.Connection,
    requested_engine: str = "",
    max_files: Optional[int] = None,
    all_jobs: bool = False,
    retry_errors: bool = False,
) -> Dict[str, int]:
    statuses = ["pending"]
    if retry_errors:
        statuses.append("error")
    placeholders = ",".join("?" for _ in statuses)
    query = f"""
        SELECT j.*, g.folder_relative_path, g.transcript_path,
               g.duration_seconds, g.status AS group_status,
               s.absolute_path, s.relative_path, s.date_hint, s.source_id,
               s.mtime_ns, s.status AS source_status,
               s.extraction_status, s.content_sha256, s.source_version_id,
               s.classification, s.kind
        FROM transcription_job j
        JOIN meeting_group g ON g.group_id = j.group_id
        JOIN source_record s ON s.source_id = j.media_source_id
        WHERE j.status IN ({placeholders})
        ORDER BY COALESCE(g.duration_seconds, 999999999), g.folder_relative_path
    """
    candidate_jobs = con.execute(query, statuses).fetchall()
    jobs = []
    for job in candidate_jobs:
        source_eligible = (
            job["group_status"] != "needs_review"
            and zoom_group_is_eligible(config, con, job["folder_relative_path"])
            and zoom_source_is_eligible(config, con, job)
        )
        if source_eligible:
            jobs.append(job)
        else:
            con.execute(
                """
                UPDATE transcription_job
                SET status='needs_review',
                    error='Zoom source or meeting is not currently eligible',
                    completed_at=?
                WHERE job_id=?
                """,
                (now_iso(), job["job_id"]),
            )
    con.commit()

    if not all_jobs:
        limit = max_files if max_files is not None else 3
        jobs = jobs[: max(0, limit)]
    elif max_files is not None:
        jobs = jobs[: max(0, max_files)]

    result = {"attempted": 0, "complete": 0, "errors": 0}
    if not jobs:
        return result

    engine, reason = _engine_available(config, requested_engine)
    if engine is None:
        raise RuntimeError(reason)
    section = config.section("zoom")
    model = str(section.get("model", "small.en"))

    for job in jobs:
        if not zoom_group_is_eligible(config, con, job["folder_relative_path"]):
            con.execute(
                """
                UPDATE transcription_job
                SET status='needs_review',
                    error='Zoom meeting is no longer currently eligible',
                    completed_at=?
                WHERE job_id=?
                """,
                (now_iso(), job["job_id"]),
            )
            con.commit()
            continue
        result["attempted"] += 1
        con.execute(
            """
            UPDATE transcription_job
            SET status='running', engine=?, model=?, started_at=?, error=NULL
            WHERE job_id=?
            """,
            (engine, model, now_iso(), job["job_id"]),
        )
        con.commit()

        media_path = Path(job["absolute_path"])
        output_stem = Path(job["output_stem"])
        temp_root = ensure_dir(config.state_dir / "tmp")
        temp_dir = Path(tempfile.mkdtemp(prefix=f"{job['job_id']}-", dir=str(temp_root)))
        try:
            if engine == "custom":
                vtt_path, txt_path = _transcribe_custom(config, media_path, output_stem)
            elif engine == "whisper_cpp":
                vtt_path, txt_path = _transcribe_whisper_cpp(config, media_path, output_stem, temp_dir)
            elif engine == "faster_whisper":
                vtt_path, txt_path = _transcribe_faster_whisper(config, media_path, output_stem)
            elif engine == "openai_whisper":
                vtt_path, txt_path = _transcribe_openai_whisper(config, media_path, output_stem)
            else:
                raise RuntimeError(f"unsupported engine: {engine}")

            group_row = con.execute("SELECT * FROM meeting_group WHERE group_id=?", (job["group_id"],)).fetchone()
            media_row = con.execute("SELECT * FROM source_record WHERE source_id=?", (job["media_source_id"],)).fetchone()
            markdown_path = _create_markdown(config, media_row, group_row, vtt_path, txt_path, engine, model)

            con.execute(
                """
                UPDATE transcription_job
                SET status='complete', completed_at=?, error=NULL
                WHERE job_id=?
                """,
                (now_iso(), job["job_id"]),
            )
            con.execute(
                """
                UPDATE meeting_group
                SET status='generated_transcript', transcript_path=?, updated_at=?
                WHERE group_id=?
                """,
                (str(markdown_path), now_iso(), job["group_id"]),
            )
            con.commit()
            result["complete"] += 1
        except Exception as exc:
            con.execute(
                """
                UPDATE transcription_job
                SET status='error', completed_at=?, error=?
                WHERE job_id=?
                """,
                (now_iso(), f"{type(exc).__name__}: {exc}", job["job_id"]),
            )
            con.commit()
            result["errors"] += 1
        finally:
            if not bool(section.get("keep_temporary_wav", False)):
                shutil.rmtree(temp_dir, ignore_errors=True)

    return result
