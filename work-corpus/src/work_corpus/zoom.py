from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import Config, DEFAULT_SKIP_CLASSIFICATIONS
from .util import (
    atomic_write_text,
    executable,
    now_iso,
    provenance_header,
    read_text_guess,
    run_command,
    parse_date_hint,
    stable_id,
    vtt_or_srt_to_markdown,
    write_csv,
)


AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".caf"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
TRANSCRIPT_EXTENSIONS = {".vtt", ".srt"}


def zoom_meeting_folder(relative_path: str) -> Optional[str]:
    """Return the dated Zoom meeting root for a source path."""
    parts = Path(relative_path).parts
    if len(parts) < 3 or parts[0] != "data" or parts[1] != "Zoom":
        return None
    folder = parts[2]
    if not parse_date_hint(folder):
        return None
    return f"data/Zoom/{folder}"


def _is_transcript_candidate(row: sqlite3.Row) -> bool:
    ext = row["extension"].lower()
    name = Path(row["absolute_path"]).name.lower()
    if name in {"chat.txt", "meeting_saved_chat.txt", "participants.txt"}:
        return False
    if ext in TRANSCRIPT_EXTENSIONS:
        return True
    if ext == ".txt" and any(token in name for token in ("transcript", "caption", "closed_caption", "audio_transcript", "cc.")):
        return True
    if ext == ".json" and "transcript" in name:
        return True
    return False


def zoom_source_is_eligible(
    config: Config,
    con: sqlite3.Connection,
    row: sqlite3.Row,
) -> bool:
    """Return whether a Zoom source may enter grouping or local processing."""
    skip_classifications = {
        str(value).casefold()
        for value in config.get(
            "normalization",
            "skip_classifications",
            list(DEFAULT_SKIP_CLASSIFICATIONS),
        )
        if str(value).strip()
    }
    if (row["classification"] or "Unknown").casefold() in skip_classifications:
        return False
    source_status = (
        row["source_status"]
        if "source_status" in row.keys()
        else row["status"]
    )
    if source_status != "present" or row["extraction_status"] != "ready":
        return False
    if not row["content_sha256"] or not row["source_version_id"]:
        return False
    return bool(
        con.execute(
            """
            SELECT 1
            FROM source_version
            WHERE source_version_id=?
              AND source_id=?
              AND content_sha256=?
            """,
            (
                row["source_version_id"],
                row["source_id"],
                row["content_sha256"],
            ),
        ).fetchone()
    )


def zoom_group_is_eligible(
    config: Config,
    con: sqlite3.Connection,
    folder_relative_path: str,
) -> bool:
    """Require every current Zoom content candidate in a meeting to be eligible."""
    folder = zoom_meeting_folder(folder_relative_path)
    if folder is None:
        return False
    rows = con.execute(
        """
        SELECT *
        FROM source_record
        WHERE status='present'
          AND source_system='zoom'
          AND kind IN ('media','transcript','transcript_candidate',
                       'meeting_chat','document','structured_text')
        ORDER BY relative_path
        """
    ).fetchall()
    prefix = folder.rstrip("/") + "/"
    meeting_rows = [
        row
        for row in rows
        if row["relative_path"] == folder
        or row["relative_path"].startswith(prefix)
    ]
    return bool(meeting_rows) and all(
        zoom_source_is_eligible(config, con, row) for row in meeting_rows
    )


def _transcript_score(row: sqlite3.Row) -> int:
    ext = row["extension"].lower()
    name = Path(row["absolute_path"]).name.lower()
    score = 0
    if ext == ".vtt":
        score += 100
    elif ext == ".srt":
        score += 90
    elif ext == ".txt":
        score += 50
    elif ext == ".json":
        score += 40
    if "audio_transcript" in name:
        score += 20
    if "transcript" in name:
        score += 15
    if "caption" in name:
        score += 10
    return score


def _media_score(row: sqlite3.Row) -> int:
    path = Path(row["absolute_path"])
    ext = row["extension"].lower()
    name = path.name.lower()
    score = 0
    if name == "audio_only.m4a":
        score += 1000
    elif "audio_only" in name:
        score += 900
    elif ext in AUDIO_EXTENSIONS:
        score += 700
    elif ext in VIDEO_EXTENSIONS:
        score += 400
    if name.startswith("zoom_"):
        score += 40
    if "shared_screen" in name:
        score -= 40
    if "gallery_view" in name:
        score -= 20
    # Smaller files are usually preferable when the content is equivalent.
    size_mb = row["size_bytes"] / (1024 * 1024)
    score -= int(min(size_mb / 100, 100))
    return score


def _duration_seconds(path: Path, ffprobe_command: str) -> Optional[float]:
    command = executable(ffprobe_command) or ffprobe_command
    code, out, _err = run_command(
        [
            command,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        timeout=30,
    )
    if code != 0:
        return None
    try:
        return float(out.strip())
    except (TypeError, ValueError):
        return None


def _normalize_existing_transcript(config: Config, row: sqlite3.Row, group_id: str) -> Path:
    path = Path(row["absolute_path"])
    ext = row["extension"].lower()
    if ext in {".vtt", ".srt"}:
        body = vtt_or_srt_to_markdown(read_text_guess(path), path.parent.name)
        parser = "zoom_existing_caption"
    elif ext == ".json":
        payload = json.loads(read_text_guess(path))
        if isinstance(payload, dict):
            text = payload.get("transcript") or payload.get("text") or payload.get("content") or json.dumps(payload, indent=2, ensure_ascii=False)
        else:
            text = json.dumps(payload, indent=2, ensure_ascii=False)
        body = f"# {path.parent.name}\n\n{text}\n"
        parser = "zoom_existing_json_transcript"
    else:
        body = f"# {path.parent.name}\n\n{read_text_guess(path)}\n"
        parser = "zoom_existing_text_transcript"

    output = config.corpus_dir / "transcripts" / "zoom" / "existing" / f"{group_id}.md"
    header = provenance_header({
        "source_id": row["source_id"],
        "source_system": "zoom",
        "original_path": row["absolute_path"],
        "relative_path": row["relative_path"],
        "original_date": row["date_hint"] or "",
        "file_type": row["extension"],
        "parser": parser,
        "generated_at": now_iso(),
    })
    atomic_write_text(output, header + body.rstrip() + "\n")
    return output


def scan_zoom(config: Config, con: sqlite3.Connection) -> Dict[str, int]:
    candidate_rows = con.execute(
        """
        SELECT *
        FROM source_record
        WHERE status='present'
          AND source_system='zoom'
          AND (kind IN ('media','transcript','transcript_candidate','meeting_chat','document','structured_text'))
        ORDER BY relative_path
        """
    ).fetchall()

    groups: Dict[str, List[sqlite3.Row]] = {}
    for row in candidate_rows:
        folder = zoom_meeting_folder(row["relative_path"])
        if folder is None:
            continue
        groups.setdefault(folder, []).append(row)

    result = {
        "meeting_folders": 0,
        "with_existing_transcript": 0,
        "with_generated_transcript": 0,
        "queued_for_transcription": 0,
        "media_without_transcript": 0,
        "transcript_only": 0,
    }
    queue_rows: List[Dict[str, Any]] = []
    ffprobe_command = str(config.get("zoom", "ffprobe_command", "ffprobe"))

    for folder, items in sorted(groups.items()):
        all_media = [
            row
            for row in items
            if row["extension"].lower() in AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        ]
        all_transcripts = [
            row for row in items if _is_transcript_candidate(row)
        ]
        if not all_media and not all_transcripts:
            continue

        result["meeting_folders"] += 1
        group_id = stable_id("zoom", folder)
        blocked = not zoom_group_is_eligible(config, con, folder)
        if blocked:
            chosen_media = max(all_media, key=_media_score) if all_media else None
            chosen_transcript = (
                max(all_transcripts, key=_transcript_score)
                if all_transcripts
                else None
            )
            con.execute(
                """
                INSERT INTO meeting_group (
                    group_id, folder_relative_path, media_source_id,
                    transcript_source_id, transcript_path, status,
                    duration_seconds, updated_at
                ) VALUES (?, ?, ?, ?, NULL, 'needs_review', NULL, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    folder_relative_path=excluded.folder_relative_path,
                    media_source_id=excluded.media_source_id,
                    transcript_source_id=excluded.transcript_source_id,
                    transcript_path=NULL,
                    status='needs_review',
                    duration_seconds=NULL,
                    updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    folder,
                    chosen_media["source_id"] if chosen_media else None,
                    chosen_transcript["source_id"] if chosen_transcript else None,
                    now_iso(),
                ),
            )
            con.execute(
                """
                UPDATE transcription_job
                SET status='needs_review',
                    error='Zoom meeting contains an ineligible source',
                    completed_at=?
                WHERE group_id=?
                  AND status IN ('pending', 'running', 'error')
                """,
                (now_iso(), group_id),
            )
            continue

        media = [
            row
            for row in all_media
            if zoom_source_is_eligible(config, con, row)
        ]
        transcripts = [
            row
            for row in all_transcripts
            if zoom_source_is_eligible(config, con, row)
        ]
        chosen_media = max(media, key=_media_score) if media else None
        chosen_transcript = max(transcripts, key=_transcript_score) if transcripts else None
        duration = _duration_seconds(Path(chosen_media["absolute_path"]), ffprobe_command) if chosen_media else None

        existing_group = con.execute(
            "SELECT status, transcript_path FROM meeting_group WHERE group_id = ?",
            (group_id,),
        ).fetchone()
        generated_path = None
        if (
            existing_group
            and existing_group["status"] == "generated_transcript"
            and existing_group["transcript_path"]
        ):
            candidate = Path(existing_group["transcript_path"])
            if candidate.exists():
                generated_path = candidate

        if chosen_transcript:
            transcript_path = _normalize_existing_transcript(config, chosen_transcript, group_id)
            status = "existing_transcript"
            result["with_existing_transcript"] += 1
            if not chosen_media:
                result["transcript_only"] += 1
        elif chosen_media and generated_path:
            transcript_path = generated_path
            status = "generated_transcript"
            result["with_generated_transcript"] += 1
        elif chosen_media:
            transcript_path = None
            status = "needs_transcription"
            result["media_without_transcript"] += 1
        else:
            transcript_path = None
            status = "unresolved"

        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, media_source_id,
                transcript_source_id, transcript_path, status,
                duration_seconds, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                folder_relative_path=excluded.folder_relative_path,
                media_source_id=excluded.media_source_id,
                transcript_source_id=excluded.transcript_source_id,
                transcript_path=excluded.transcript_path,
                status=excluded.status,
                duration_seconds=excluded.duration_seconds,
                updated_at=excluded.updated_at
            """,
            (
                group_id,
                folder,
                chosen_media["source_id"] if chosen_media else None,
                chosen_transcript["source_id"] if chosen_transcript else None,
                str(transcript_path) if transcript_path else None,
                status,
                duration,
                now_iso(),
            ),
        )

        if chosen_media and not chosen_transcript and status != "generated_transcript":
            job_id = stable_id("txjob", group_id, chosen_media["source_id"])
            output_stem = config.corpus_dir / "transcripts" / "zoom" / "generated" / group_id
            existing_job = con.execute(
                "SELECT status FROM transcription_job WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            job_status = (
                existing_job["status"]
                if existing_job and existing_job["status"] in {"running", "error"}
                else "pending"
            )
            con.execute(
                """
                INSERT INTO transcription_job (
                    job_id, group_id, media_source_id, output_stem,
                    engine, model, status, error, created_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, NULL, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    group_id=excluded.group_id,
                    media_source_id=excluded.media_source_id,
                    output_stem=excluded.output_stem,
                    status=CASE
                        WHEN transcription_job.status='running' THEN 'running'
                        WHEN transcription_job.status='error' THEN 'error'
                        ELSE excluded.status
                    END
                """,
                (
                    job_id,
                    group_id,
                    chosen_media["source_id"],
                    str(output_stem),
                    job_status,
                    now_iso(),
                ),
            )
            result["queued_for_transcription"] += 1
            queue_rows.append({
                "job_id": job_id,
                "group_id": group_id,
                "folder": folder,
                "media_path": chosen_media["absolute_path"],
                "media_size_bytes": chosen_media["size_bytes"],
                "duration_seconds": duration if duration is not None else "",
                "status": job_status,
                "output_stem": str(output_stem),
            })

    con.commit()

    # Include completed/error jobs in the queue report for a complete view.
    all_jobs = []
    for row in con.execute(
        """
        SELECT j.job_id, j.group_id, g.folder_relative_path AS folder,
               s.absolute_path AS media_path, s.size_bytes AS media_size_bytes,
               g.duration_seconds, j.status, j.engine, j.model, j.error,
               j.output_stem, j.created_at, j.started_at, j.completed_at
        FROM transcription_job j
        JOIN meeting_group g ON g.group_id = j.group_id
        JOIN source_record s ON s.source_id = j.media_source_id
        ORDER BY CASE j.status
            WHEN 'pending' THEN 0
            WHEN 'error' THEN 1
            WHEN 'running' THEN 2
            WHEN 'complete' THEN 3
            ELSE 4 END,
            g.folder_relative_path
        """
    ):
        all_jobs.append(dict(row))
    write_csv(
        config.state_dir / "transcription_queue.csv",
        all_jobs,
        [
            "job_id", "group_id", "folder", "media_path", "media_size_bytes",
            "duration_seconds", "status", "engine", "model", "error",
            "output_stem", "created_at", "started_at", "completed_at",
        ],
    )

    zoom_index = [
        dict(row)
        for row in con.execute(
            """
            SELECT group_id, folder_relative_path, media_source_id,
                   transcript_source_id, transcript_path, status,
                   duration_seconds, updated_at
            FROM meeting_group
            ORDER BY folder_relative_path
            """
        )
    ]
    write_csv(
        config.corpus_dir / "reports" / "zoom_index.csv",
        zoom_index,
        [
            "group_id", "folder_relative_path", "media_source_id",
            "transcript_source_id", "transcript_path", "status",
            "duration_seconds", "updated_at",
        ],
    )
    return result
