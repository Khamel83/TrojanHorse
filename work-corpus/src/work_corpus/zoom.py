from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import DEFAULT_SKIP_CLASSIFICATIONS, Config
from .db import record_review_item
from .util import (
    atomic_write_text,
    now_iso,
    parse_date_hint,
    provenance_header,
    read_text_guess,
    stable_id,
    vtt_or_srt_to_markdown,
    write_csv,
)

FINAL_MEDIA_EXTENSIONS = {".mp4", ".m4a"}
AUDIO_EXTENSIONS = {
    ".aac",
    ".caf",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
TRANSCRIPT_EXTENSIONS = {".srt", ".vtt"}
ARTIFACT_EXTENSIONS = {
    ".crdownload",
    ".download",
    ".part",
    ".tmp",
    ".zoom",
}

QUEUE_STATUSES = {
    "not_needed",
    "existing_transcript",
    "pending_approval",
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "blocked",
    "artifact",
    "skipped",
}
TERMINAL_QUEUE_STATUSES = {
    "not_needed",
    "existing_transcript",
    "succeeded",
    "partial",
    "failed",
    "blocked",
    "artifact",
    "skipped",
}

_TIMESTAMP_RE = re.compile(
    r"^\s*(?P<start>(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3})"
    r"\s*-->\s*"
    r"(?P<end>(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3})"
)


def _row_value(row: Optional[sqlite3.Row], key: str, default: Any = None) -> Any:
    if row is None:
        return default
    try:
        if key in row.keys():
            return row[key]
    except AttributeError:
        try:
            return row[key]
        except (KeyError, TypeError):
            pass
    return default


def _extension(row: sqlite3.Row) -> str:
    extension = str(_row_value(row, "extension", "") or "").lower()
    if extension:
        return extension
    return Path(str(_row_value(row, "absolute_path", ""))).suffix.lower()


def _relative_path(row: sqlite3.Row) -> str:
    return str(_row_value(row, "relative_path", "") or "").replace("\\", "/")


def _absolute_path(row: sqlite3.Row) -> Path:
    return Path(str(_row_value(row, "absolute_path", "")))


def _row_with_safe_provenance(
    con: sqlite3.Connection,
    row: sqlite3.Row,
) -> Dict[str, Any]:
    """Copy a source row with only valid Task 3 foreign-key references."""
    values = {key: row[key] for key in row.keys()}
    source_id = str(values.get("source_id") or "")
    if not source_id or not con.execute(
        "SELECT 1 FROM source_record WHERE source_id=?", (source_id,)
    ).fetchone():
        values["source_id"] = None
        values["source_version_id"] = None
        return values

    version_id = str(values.get("source_version_id") or "")
    digest = str(values.get("content_sha256") or "")
    if not version_id or not digest or not con.execute(
        """
        SELECT 1 FROM source_version
        WHERE source_version_id=? AND source_id=? AND content_sha256=?
        """,
        (version_id, source_id, digest),
    ).fetchone():
        values["source_version_id"] = None
    return values


def zoom_meeting_folder(relative_path: str) -> Optional[str]:
    """Return the dated Zoom meeting folder immediately below the Zoom root."""
    normalised = relative_path.replace("\\", "/").strip("/")
    parts = normalised.split("/")
    if len(parts) < 4 or parts[:2] != ["data", "Zoom"]:
        return None
    folder = parts[2]
    if not parse_date_hint(folder):
        return None
    return "/".join(parts[:3])


def zoom_group_id(folder_relative_path: str, root_key: str = "zoom") -> str:
    """Return the stable identity of one dated Zoom folder."""
    return stable_id("zoom-group", root_key, folder_relative_path)


def _group_title(folder_relative_path: str) -> str:
    """Return a conservative title used only to create review proposals."""
    title = Path(folder_relative_path).name
    title = re.sub(
        r"(?<!\d)20\d{2}[-_. ](?:0?[1-9]|1[0-2])[-_. ](?:0?[1-9]|[12]\d|3[01])(?!\d)",
        " ",
        title,
    )
    title = re.sub(
        r"(?<!\d)20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)",
        " ",
        title,
    )
    title = re.sub(r"\s+", " ", title).strip(" -_.")
    return title.casefold()


def _is_excluded_transcript_name(name: str) -> bool:
    low = name.casefold().replace("_", "-").replace(" ", "-")
    if low in {
        "chat.txt",
        "meeting-chat.txt",
        "meeting-saved-chat.txt",
        "saved-chat.txt",
        "participant.txt",
        "participants.txt",
        "meeting-participants.txt",
    }:
        return True
    return "chat" in low or "participant" in low


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


def _parse_transcript_cues(text: str) -> Tuple[List[Tuple[float, float, str]], bool]:
    lines = text.replace("\ufeff", "").splitlines()
    cues: List[Tuple[float, float, str]] = []
    timestamp_seen = False
    timestamp_valid = True
    current_start: Optional[float] = None
    current_end: Optional[float] = None
    current_text: List[str] = []

    def flush() -> None:
        nonlocal current_start, current_end, current_text, timestamp_valid
        if current_start is None or current_end is None:
            current_text = []
            return
        body = " ".join(part.strip() for part in current_text if part.strip()).strip()
        if not body:
            timestamp_valid = False
        else:
            cues.append((current_start, current_end, body))
        current_start = None
        current_end = None
        current_text = []

    for raw in lines:
        line = raw.strip()
        match = _TIMESTAMP_RE.match(line)
        if match:
            flush()
            timestamp_seen = True
            try:
                current_start = _timestamp_seconds(match.group("start"))
                current_end = _timestamp_seconds(match.group("end"))
                if current_end < current_start:
                    timestamp_valid = False
            except ValueError:
                timestamp_valid = False
            continue
        if not line or line == "WEBVTT" or line.startswith("NOTE"):
            flush()
            continue
        if line.isdigit() and current_start is None:
            continue
        if current_start is not None:
            current_text.append(line)
    flush()

    previous_start = -1.0
    for start, end, _body in cues:
        if start < previous_start or end < start:
            timestamp_valid = False
        previous_start = start
    return cues, timestamp_seen and timestamp_valid and bool(cues)


def _is_transcript_candidate(row: sqlite3.Row) -> bool:
    name = Path(str(_row_value(row, "absolute_path", ""))).name
    if _is_excluded_transcript_name(name):
        return False
    kind = str(_row_value(row, "kind", "") or "").casefold()
    if kind == "meeting_chat":
        return False
    extension = _extension(row)
    if extension in TRANSCRIPT_EXTENSIONS:
        return True
    if extension == ".txt":
        low = name.casefold()
        return any(
            token in low
            for token in ("transcript", "caption", "closed_caption", "audio_transcript")
        )
    return False


def _is_usable_transcript(row: sqlite3.Row) -> bool:
    if not _is_transcript_candidate(row):
        return False
    try:
        text = read_text_guess(_absolute_path(row))
    except (OSError, UnicodeError, ValueError):
        return False
    if not text.strip():
        return False
    extension = _extension(row)
    if extension in TRANSCRIPT_EXTENSIONS:
        _cues, valid = _parse_transcript_cues(text)
        return valid
    return True


def _transcript_score(row: sqlite3.Row) -> Tuple[int, str]:
    extension = _extension(row)
    rank = {".vtt": 300, ".srt": 200, ".txt": 100}.get(extension, 0)
    return rank, _relative_path(row)


def _choose_transcript(rows: Sequence[sqlite3.Row]) -> Optional[sqlite3.Row]:
    usable = [row for row in rows if _is_usable_transcript(row)]
    if not usable:
        return None
    return sorted(
        usable,
        key=lambda row: (-_transcript_score(row)[0], _transcript_score(row)[1]),
    )[0]


def _media_score(row: sqlite3.Row) -> Tuple[int, str]:
    path = _absolute_path(row)
    extension = _extension(row)
    name = path.name.casefold()
    score = 100 if extension == ".m4a" else 80 if extension == ".mp4" else 10
    if name == "audio_only.m4a":
        score += 1000
    elif "audio_only" in name:
        score += 900
    if name.startswith("zoom_"):
        score += 40
    return score, _relative_path(row)


def _configured_skip_classifications(config: Config) -> set[str]:
    values = config.get(
        "normalization",
        "skip_classifications",
        list(DEFAULT_SKIP_CLASSIFICATIONS),
    )
    return {str(value).casefold() for value in values if str(value).strip()}


def zoom_source_is_eligible(
    config: Config,
    con: sqlite3.Connection,
    row: sqlite3.Row,
) -> bool:
    """Return whether a hashed, current Zoom source may be processed."""
    classification = str(
        _row_value(row, "classification", None)
        or _row_value(row, "scope", "Unknown")
        or "Unknown"
    )
    if classification.casefold() in _configured_skip_classifications(config):
        return False
    status = str(
        _row_value(row, "source_status", None)
        or _row_value(row, "status", "")
        or ""
    )
    if status != "present":
        return False
    if str(_row_value(row, "extraction_status", "")) != "ready":
        return False
    source_id = str(_row_value(row, "source_id", "") or "")
    version_id = str(_row_value(row, "source_version_id", "") or "")
    digest = str(_row_value(row, "content_sha256", "") or "")
    if not source_id or not version_id or not digest:
        return False
    return bool(
        con.execute(
            """
            SELECT 1 FROM source_version
            WHERE source_version_id=? AND source_id=? AND content_sha256=?
            """,
            (version_id, source_id, digest),
        ).fetchone()
    )


def _meeting_rows(
    con: sqlite3.Connection,
    folder_relative_path: str,
) -> List[sqlite3.Row]:
    prefix = folder_relative_path.rstrip("/") + "/"
    return [
        row
        for row in con.execute(
            """
            SELECT * FROM source_record
            WHERE source_system='zoom' AND status='present'
            ORDER BY relative_path
            """
        ).fetchall()
        if _relative_path(row) == folder_relative_path
        or _relative_path(row).startswith(prefix)
    ]


def zoom_group_is_eligible(
    config: Config,
    con: sqlite3.Connection,
    folder_relative_path: str,
) -> bool:
    """Return whether the semantic contents of one Zoom group are eligible."""
    folder = zoom_meeting_folder(folder_relative_path)
    if folder is None:
        return False
    rows = _meeting_rows(con, folder)
    semantic = [
        row
        for row in rows
        if _extension(row) in FINAL_MEDIA_EXTENSIONS or _is_transcript_candidate(row)
    ]
    return bool(semantic) and all(
        zoom_source_is_eligible(config, con, row) for row in semantic
    )


def _artifact_reason(row: sqlite3.Row) -> Optional[str]:
    extension = _extension(row)
    name = Path(str(_row_value(row, "absolute_path", ""))).name.casefold()
    metadata_raw = _row_value(row, "metadata_json", "")
    metadata: Dict[str, Any] = {}
    if metadata_raw:
        try:
            parsed = json.loads(metadata_raw)
            if isinstance(parsed, dict):
                metadata = parsed
        except (TypeError, ValueError):
            pass
    if extension == ".tmp" or name.endswith(".tmp"):
        return "temporary Zoom artifact (.tmp)"
    if extension == ".zoom" or name.endswith(".zoom"):
        return "unvalidated Zoom artifact (.zoom)"
    if metadata.get("corrupt") or metadata.get("media_status") == "corrupt":
        return "corrupt Zoom media artifact"
    if extension in MEDIA_EXTENSIONS and extension not in FINAL_MEDIA_EXTENSIONS:
        return f"non-final Zoom media extension {extension}"
    if metadata.get("artifact_reason"):
        return str(metadata["artifact_reason"])
    return None


def _job_id(group_id: str, row: sqlite3.Row) -> str:
    return stable_id(
        "txjob",
        group_id,
        _row_value(row, "source_id", ""),
        _row_value(row, "source_version_id", "") or "inventory-only",
    )


def _output_stem(config: Config, group_id: str, row: sqlite3.Row) -> Path:
    version_key = str(
        _row_value(row, "source_version_id", "")
        or _row_value(row, "source_id", "")
    )
    output = (
        config.corpus_dir
        / "transcripts"
        / "zoom"
        / "generated"
        / group_id
        / version_key
    )
    config.assert_derived_path(output)
    return output


def _legacy_status(status: str, approval_status: str) -> str:
    if status == "pending":
        return "queued" if approval_status == "approved" else "pending_approval"
    if status == "needs_review":
        return "pending_approval"
    if status == "error":
        return "failed"
    if status == "complete":
        return "succeeded"
    return status


def _upsert_job(
    config: Config,
    con: sqlite3.Connection,
    group_id: str,
    row: sqlite3.Row,
    *,
    status: str,
    reason: Optional[str] = None,
    approval_status: Optional[str] = None,
) -> Tuple[str, str]:
    job_id = _job_id(group_id, row)
    output_stem = _output_stem(config, group_id, row)
    existing = con.execute(
        "SELECT status, approval_status FROM transcription_job WHERE job_id=?",
        (job_id,),
    ).fetchone()
    if existing:
        raw_existing_status = str(existing["status"])
        existing_status = _legacy_status(
            str(existing["status"]), str(existing["approval_status"] or "")
        )
        if existing_status != existing["status"]:
            if raw_existing_status == "needs_review":
                con.execute(
                    """
                    UPDATE transcription_job
                    SET status='pending_approval', approval_status='pending_approval',
                        error='Zoom group requires scope review', completed_at=NULL
                    WHERE job_id=?
                    """,
                    (job_id,),
                )
            else:
                con.execute(
                    "UPDATE transcription_job SET status=? WHERE job_id=?",
                    (existing_status, job_id),
                )
        effective_status = existing_status
        effective_approval = (
            "pending_approval"
            if raw_existing_status == "needs_review"
            else str(existing["approval_status"] or "")
        ) or (
            "approved"
            if effective_status in {"queued", "running"}
            else "pending_approval"
        )
        if status == "pending_approval" and effective_status == "not_needed":
            effective_status = "pending_approval"
            effective_approval = approval_status or "pending_approval"
            con.execute(
                """
                UPDATE transcription_job
                SET status=?, approval_status=?, error=NULL, completed_at=NULL
                WHERE job_id=?
                """,
                (effective_status, effective_approval, job_id),
            )
        if (
            status in {"artifact", "blocked", "not_needed"}
            and effective_status not in TERMINAL_QUEUE_STATUSES
        ):
            effective_status = status
            effective_approval = approval_status or "not_needed"
            con.execute(
                """
                UPDATE transcription_job
                SET status=?, approval_status=?, error=?, completed_at=?
                WHERE job_id=?
                """,
                (effective_status, effective_approval, reason, now_iso(), job_id),
            )
        return job_id, effective_status

    effective_approval = approval_status or (
        "pending_approval" if status == "pending_approval" else "not_needed"
    )
    con.execute(
        """
        INSERT INTO transcription_job (
            job_id, group_id, media_source_id, media_version_id,
            approval_status, output_stem, engine, model, local_engine,
            local_model, status, language, error, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, NULL, ?, ?)
        """,
        (
            job_id,
            group_id,
            _row_value(row, "source_id", None),
            _row_value(row, "source_version_id", None),
            effective_approval,
            str(output_stem),
            status,
            reason,
            now_iso(),
        ),
    )
    return job_id, status


def _normalize_existing_transcript(
    config: Config,
    row: sqlite3.Row,
    group_id: str,
) -> Path:
    path = _absolute_path(row)
    extension = _extension(row)
    if extension in TRANSCRIPT_EXTENSIONS:
        body = vtt_or_srt_to_markdown(read_text_guess(path), path.parent.name)
        parser = "zoom_existing_caption"
    else:
        body = f"# {path.parent.name}\n\n{read_text_guess(path).strip()}\n"
        parser = "zoom_existing_text_transcript"

    output = config.corpus_dir / "transcripts" / "zoom" / "existing" / f"{group_id}.md"
    config.assert_derived_path(output)
    header = provenance_header(
        {
            "source_id": _row_value(row, "source_id", ""),
            "source_system": "zoom",
            "original_path": str(path),
            "relative_path": _relative_path(row),
            "original_date": _row_value(row, "date_hint", "") or "",
            "file_type": extension,
            "parser": parser,
            "generated_at": now_iso(),
        }
    )
    linkage = (
        f"<!-- meeting_group_id: {group_id}; "
        f"source_version_id: {_row_value(row, 'source_version_id', '')} -->\n"
    )
    atomic_write_text(output, header + linkage + body.rstrip() + "\n")
    return output


def _scope_review_required(config: Config, rows: Iterable[sqlite3.Row]) -> bool:
    skip = _configured_skip_classifications(config)
    for row in rows:
        if _extension(row) not in FINAL_MEDIA_EXTENSIONS and not _is_transcript_candidate(row):
            continue
        classification = str(
            _row_value(row, "classification", None)
            or _row_value(row, "scope", "Unknown")
            or "Unknown"
        )
        if classification.casefold() in skip:
            return True
    return False


def _group_status_from_jobs(
    con: sqlite3.Connection,
    group_id: str,
    default: str,
) -> Tuple[str, Optional[str]]:
    rows = con.execute(
        "SELECT status, output_path FROM transcription_job WHERE group_id=?",
        (group_id,),
    ).fetchall()
    if not rows:
        return default, None
    statuses = [_legacy_status(str(row["status"]), "") for row in rows]
    output_paths = [row["output_path"] for row in rows if row["output_path"]]
    for status in (
        "running",
        "queued",
        "pending_approval",
        "failed",
        "partial",
        "succeeded",
        "blocked",
        "artifact",
    ):
        if status in statuses:
            return status, output_paths[-1] if output_paths else None
    return default, output_paths[-1] if output_paths else None


def _write_queue_report(
    config: Config,
    con: sqlite3.Connection,
    queue_rows: Sequence[Dict[str, Any]],
) -> None:
    by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {
        (
            str(row.get("group_id", "")),
            str(row.get("media_source_id", "")),
            str(row.get("media_version_id", "")),
        ): dict(row)
        for row in queue_rows
    }
    for row in con.execute(
        """
        SELECT j.job_id, j.group_id, j.media_source_id, j.media_version_id,
               j.approval_status, j.status, j.engine, j.model, j.local_engine,
               j.local_model, j.language, j.timestamp_coverage,
               j.speaker_label_status, j.quality_status, j.output_path,
               j.output_sha256, j.error, j.output_stem, j.created_at,
               j.started_at, j.completed_at, g.folder_relative_path,
               s.absolute_path AS media_path, s.relative_path,
               s.size_bytes AS media_size_bytes
        FROM transcription_job j
        JOIN meeting_group g ON g.group_id=j.group_id
        LEFT JOIN source_record s ON s.source_id=j.media_source_id
        ORDER BY g.folder_relative_path, j.job_id
        """
    ):
        item = dict(row)
        key = (
            str(item.get("group_id", "")),
            str(item.get("media_source_id", "")),
            str(item.get("media_version_id", "")),
        )
        by_key[key] = item

    path = config.state_dir / "transcription_queue.csv"
    config.assert_derived_path(path)
    write_csv(
        path,
        list(by_key.values()),
        [
            "job_id",
            "group_id",
            "folder_relative_path",
            "media_source_id",
            "media_version_id",
            "relative_path",
            "media_path",
            "media_size_bytes",
            "approval_status",
            "status",
            "engine",
            "model",
            "local_engine",
            "local_model",
            "language",
            "timestamp_coverage",
            "speaker_label_status",
            "quality_status",
            "output_path",
            "output_sha256",
            "error",
            "output_stem",
            "created_at",
            "started_at",
            "completed_at",
        ],
    )


def _write_zoom_index(config: Config, con: sqlite3.Connection) -> None:
    path = config.corpus_dir / "reports" / "zoom_index.csv"
    config.assert_derived_path(path)
    rows = [
        dict(row)
        for row in con.execute(
            """
            SELECT group_id, folder_relative_path, meeting_date,
                   media_source_id, media_version_id, transcript_source_id,
                   transcript_version_id, transcript_path, status,
                   duration_seconds, updated_at
            FROM meeting_group ORDER BY folder_relative_path
            """
        )
    ]
    write_csv(
        path,
        rows,
        [
            "group_id",
            "folder_relative_path",
            "meeting_date",
            "media_source_id",
            "media_version_id",
            "transcript_source_id",
            "transcript_version_id",
            "transcript_path",
            "status",
            "duration_seconds",
            "updated_at",
        ],
    )


def _mark_not_needed_jobs(con: sqlite3.Connection, group_id: str, reason: str) -> None:
    con.execute(
        """
        UPDATE transcription_job
        SET status='not_needed', approval_status='not_needed', error=?, completed_at=?
        WHERE group_id=? AND status IN ('pending', 'pending_approval', 'queued', 'running', 'error')
        """,
        (reason, now_iso(), group_id),
    )


def scan_zoom(config: Config, con: sqlite3.Connection) -> Dict[str, int]:
    """Group Zoom sources, prefer local transcripts, and build the full queue."""
    rows = _meeting_rows(con, "data/Zoom")
    grouped: Dict[str, List[sqlite3.Row]] = {}
    for row in rows:
        folder = zoom_meeting_folder(_relative_path(row))
        if folder:
            grouped.setdefault(folder, []).append(row)

    result: Dict[str, int] = {
        "meeting_folders": 0,
        "with_existing_transcript": 0,
        "with_generated_transcript": 0,
        "queued_for_transcription": 0,
        "media_without_transcript": 0,
        "transcript_only": 0,
        "artifacts": 0,
        "blocked": 0,
    }
    queue_rows: List[Dict[str, Any]] = []
    transcript_only_groups: List[sqlite3.Row] = []

    for folder, items in sorted(grouped.items()):
        items = [_row_with_safe_provenance(con, row) for row in items]
        final_media = [
            row
            for row in items
            if _extension(row) in FINAL_MEDIA_EXTENSIONS
            and not _artifact_reason(row)
        ]
        other_artifacts = [row for row in items if _artifact_reason(row)]
        transcript_candidates = [row for row in items if _is_transcript_candidate(row)]
        usable_transcript = _choose_transcript(transcript_candidates)
        if not final_media and not transcript_candidates and not other_artifacts:
            continue

        result["meeting_folders"] += 1
        group_id = zoom_group_id(folder, "zoom")
        chosen_media = max(final_media, key=_media_score) if final_media else None
        scope_review = _scope_review_required(config, items)
        if scope_review:
            chosen_transcript = (
                max(transcript_candidates, key=_transcript_score)
                if transcript_candidates
                else None
            )
            con.execute(
                """
                INSERT INTO meeting_group (
                    group_id, folder_relative_path, meeting_date, media_source_id,
                    media_version_id, transcript_source_id, transcript_version_id,
                    transcript_path, status, duration_seconds, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 'needs_review', NULL, ?)
                ON CONFLICT(group_id) DO UPDATE SET
                    folder_relative_path=excluded.folder_relative_path,
                    meeting_date=excluded.meeting_date,
                    media_source_id=excluded.media_source_id,
                    media_version_id=excluded.media_version_id,
                    transcript_source_id=excluded.transcript_source_id,
                    transcript_version_id=excluded.transcript_version_id,
                    status='needs_review',
                    updated_at=excluded.updated_at
                """,
                (
                    group_id,
                    folder,
                    parse_date_hint(Path(folder).name) or None,
                    _row_value(chosen_media, "source_id", None),
                    _row_value(chosen_media, "source_version_id", None),
                    _row_value(chosen_transcript, "source_id", None),
                    _row_value(chosen_transcript, "source_version_id", None),
                    now_iso(),
                ),
            )
            con.execute(
                """
                UPDATE transcription_job
                SET status='pending_approval', approval_status='pending_approval',
                    error=?, completed_at=NULL
                WHERE group_id=?
                  AND status IN ('pending', 'pending_approval', 'queued', 'running', 'error', 'needs_review')
                """,
                (
                    "Zoom group contains a personal or mixed-scope source",
                    group_id,
                ),
            )
            continue

        if usable_transcript:
            try:
                transcript_path = _normalize_existing_transcript(
                    config, usable_transcript, group_id
                )
            except Exception as exc:
                transcript_path = None
                record_review_item(
                    con,
                    "zoom_transcript_parse",
                    {
                        "group_id": group_id,
                        "source_id": _row_value(usable_transcript, "source_id", ""),
                    },
                    source_id=_row_value(usable_transcript, "source_id", None),
                    reason=f"existing transcript could not be normalized: {exc}",
                    confidence=0.95,
                )
            if transcript_path is not None:
                status = "existing_transcript" if final_media else "transcript_only"
                con.execute(
                    """
                    INSERT INTO meeting_group (
                        group_id, folder_relative_path, meeting_date, media_source_id,
                        media_version_id, transcript_source_id, transcript_version_id,
                        transcript_path, status, duration_seconds, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    ON CONFLICT(group_id) DO UPDATE SET
                        folder_relative_path=excluded.folder_relative_path,
                        meeting_date=excluded.meeting_date,
                        media_source_id=excluded.media_source_id,
                        media_version_id=excluded.media_version_id,
                        transcript_source_id=excluded.transcript_source_id,
                        transcript_version_id=excluded.transcript_version_id,
                        transcript_path=excluded.transcript_path,
                        status=excluded.status,
                        updated_at=excluded.updated_at
                    """,
                    (
                        group_id,
                        folder,
                        parse_date_hint(Path(folder).name) or None,
                        _row_value(chosen_media, "source_id", None),
                        _row_value(chosen_media, "source_version_id", None),
                        _row_value(usable_transcript, "source_id", None),
                        _row_value(usable_transcript, "source_version_id", None),
                        str(transcript_path),
                        status,
                        now_iso(),
                    ),
                )
                _mark_not_needed_jobs(
                    con, group_id, "A usable existing transcript covers this Zoom group"
                )
                result["with_existing_transcript"] += 1
                if not final_media:
                    result["transcript_only"] += 1
                    transcript_only_groups.append(
                        con.execute(
                            "SELECT * FROM meeting_group WHERE group_id=?", (group_id,)
                        ).fetchone()
                    )
                for media in final_media:
                    queue_rows.append(
                        {
                            "group_id": group_id,
                            "folder_relative_path": folder,
                            "media_source_id": _row_value(media, "source_id", ""),
                            "media_version_id": _row_value(media, "source_version_id", ""),
                            "relative_path": _relative_path(media),
                            "media_path": str(_absolute_path(media)),
                            "media_size_bytes": _row_value(media, "size_bytes", ""),
                            "status": "existing_transcript",
                            "approval_status": "not_needed",
                        }
                    )
                for artifact in other_artifacts:
                    artifact_job, artifact_status = _upsert_job(
                        config,
                        con,
                        group_id,
                        artifact,
                        status="artifact",
                        reason=_artifact_reason(artifact),
                        approval_status="not_needed",
                    )
                    result["artifacts"] += 1
                    queue_rows.append(
                        {
                            "job_id": artifact_job,
                            "group_id": group_id,
                            "folder_relative_path": folder,
                            "media_source_id": _row_value(artifact, "source_id", ""),
                            "media_version_id": _row_value(artifact, "source_version_id", ""),
                            "relative_path": _relative_path(artifact),
                            "media_path": str(_absolute_path(artifact)),
                            "media_size_bytes": _row_value(artifact, "size_bytes", ""),
                            "status": artifact_status,
                            "approval_status": "not_needed",
                            "error": _artifact_reason(artifact),
                        }
                    )
                continue

        group_status = "blocked" if final_media else "artifact"
        group_output: Optional[str] = None
        # Create the parent before inserting jobs because transcription_job has
        # a foreign key to meeting_group.
        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, meeting_date, media_source_id,
                media_version_id, transcript_source_id, transcript_version_id,
                transcript_path, status, duration_seconds, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, NULL, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                folder_relative_path=excluded.folder_relative_path,
                meeting_date=excluded.meeting_date,
                media_source_id=excluded.media_source_id,
                media_version_id=excluded.media_version_id,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                group_id,
                folder,
                parse_date_hint(Path(folder).name) or None,
                _row_value(chosen_media, "source_id", None),
                _row_value(chosen_media, "source_version_id", None),
                group_status,
                now_iso(),
            ),
        )
        for media in final_media:
            result["media_without_transcript"] += 1
            eligible = zoom_source_is_eligible(config, con, media)
            if eligible:
                job_status = "pending_approval"
                job_reason = None
                result["queued_for_transcription"] += 1
                group_status = "pending_approval"
            else:
                job_status = "blocked"
                job_reason = "Zoom media is not hashed, current, or extraction-ready"
                result["blocked"] += 1
            job_id, effective_status = _upsert_job(
                config,
                con,
                group_id,
                media,
                status=job_status,
                reason=job_reason,
                approval_status="pending_approval" if eligible else "not_needed",
            )
            if effective_status in {
                "succeeded",
                "partial",
                "failed",
                "blocked",
                "queued",
                "running",
                "pending_approval",
            }:
                group_status, group_output = _group_status_from_jobs(
                    con, group_id, group_status
                )
            queue_rows.append(
                {
                    "job_id": job_id,
                    "group_id": group_id,
                    "folder_relative_path": folder,
                    "media_source_id": _row_value(media, "source_id", ""),
                    "media_version_id": _row_value(media, "source_version_id", ""),
                    "relative_path": _relative_path(media),
                    "media_path": str(_absolute_path(media)),
                    "media_size_bytes": _row_value(media, "size_bytes", ""),
                    "status": effective_status,
                    "approval_status": "pending_approval" if eligible else "not_needed",
                    "error": job_reason,
                }
            )

        for artifact in other_artifacts:
            artifact_job, artifact_status = _upsert_job(
                config,
                con,
                group_id,
                artifact,
                status="artifact",
                reason=_artifact_reason(artifact),
                approval_status="not_needed",
            )
            result["artifacts"] += 1
            if not final_media:
                group_status = "artifact"
            queue_rows.append(
                {
                    "job_id": artifact_job,
                    "group_id": group_id,
                    "folder_relative_path": folder,
                    "media_source_id": _row_value(artifact, "source_id", ""),
                    "media_version_id": _row_value(artifact, "source_version_id", ""),
                    "relative_path": _relative_path(artifact),
                    "media_path": str(_absolute_path(artifact)),
                    "media_size_bytes": _row_value(artifact, "size_bytes", ""),
                    "status": artifact_status,
                    "approval_status": "not_needed",
                    "error": _artifact_reason(artifact),
                }
            )

        if not final_media and transcript_candidates:
            group_status = "transcript_only"
            result["transcript_only"] += 1
            transcript_only_groups.append(
                con.execute("SELECT * FROM meeting_group WHERE group_id=?", (group_id,)).fetchone()
            )

        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, meeting_date, media_source_id,
                media_version_id, transcript_source_id, transcript_version_id,
                transcript_path, status, duration_seconds, updated_at
            ) VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                folder_relative_path=excluded.folder_relative_path,
                meeting_date=excluded.meeting_date,
                media_source_id=excluded.media_source_id,
                media_version_id=excluded.media_version_id,
                transcript_path=COALESCE(excluded.transcript_path, meeting_group.transcript_path),
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (
                group_id,
                folder,
                parse_date_hint(Path(folder).name) or None,
                _row_value(chosen_media, "source_id", None),
                _row_value(chosen_media, "source_version_id", None),
                group_output,
                group_status,
                now_iso(),
            ),
        )

    media_groups = list(
        con.execute(
            "SELECT * FROM meeting_group WHERE media_source_id IS NOT NULL"
        )
    )
    for transcript_group in transcript_only_groups:
        if transcript_group is None:
            continue
        transcript_title = _group_title(transcript_group["folder_relative_path"])
        if not transcript_title:
            continue
        for media_group in media_groups:
            if media_group["group_id"] == transcript_group["group_id"]:
                continue
            if _group_title(media_group["folder_relative_path"]) != transcript_title:
                continue
            record_review_item(
                con,
                "zoom_transcript_match",
                {
                    "candidate_group_id": media_group["group_id"],
                    "transcript_group_id": transcript_group["group_id"],
                    "title": transcript_title,
                },
                source_id=transcript_group["transcript_source_id"],
                reason="Same normalized folder title; operator review is required before linking",
                confidence=0.5,
            )

    con.commit()
    _write_queue_report(config, con, queue_rows)
    _write_zoom_index(config, con)
    return result
