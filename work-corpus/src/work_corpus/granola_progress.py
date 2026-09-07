"""Derive Granola coverage from local captures and the imported corpus."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from .config import Config
from .util import atomic_write_json, now_iso, read_json


DETAIL_TOOLS = frozenset({"granola_get_meetings", "incremental_details"})
TRANSCRIPT_TOOLS = frozenset(
    {"granola_get_meeting_transcript", "incremental_transcripts"}
)
TERMINAL_STATUSES = frozenset({"not_found", "unavailable", "terminal_unavailable"})
RATE_LIMIT_STATUSES = frozenset(
    {"429", "rate_limited", "rate_limit", "too_many_requests"}
)
MAX_BATCH_SIZE = 10
RATE_LIMIT_BATCH_SIZE = 5


def _nonempty(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (str, bytes)):
        return bool(value.strip())
    return bool(value)


def _record_id(record: Mapping[str, Any]) -> Optional[str]:
    for key in ("external_record_id", "external_id", "id", "meeting_id", "uuid"):
        value = record.get(key)
        if _nonempty(value):
            return str(value).strip()
    return None


def _request_ids(request: Mapping[str, Any]) -> Set[str]:
    values: List[Any] = []
    for key in ("meeting_ids", "requested_ids"):
        value = request.get(key)
        if isinstance(value, list):
            values.extend(value)
    if _nonempty(request.get("meeting_id")):
        values.append(request["meeting_id"])
    return {str(value).strip() for value in values if _nonempty(value)}


def _status_text(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _capture_requests(
    payload: Mapping[str, Any],
) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    detail_ids: Set[str] = set()
    transcript_ids: Set[str] = set()
    terminal_ids: Set[str] = set()
    rate_limited_ids: Set[str] = set()
    metadata = payload.get("_capture")
    if not isinstance(metadata, Mapping):
        return detail_ids, transcript_ids, terminal_ids, rate_limited_ids

    for key in ("not_found_ids", "unavailable_ids", "terminal_unavailable_ids"):
        values = metadata.get(key)
        if isinstance(values, list):
            terminal_ids.update(
                str(value).strip() for value in values if _nonempty(value)
            )
    for key in ("rate_limited_ids", "rate_limit_ids"):
        values = metadata.get(key)
        if isinstance(values, list):
            rate_limited_ids.update(
                str(value).strip() for value in values if _nonempty(value)
            )

    requests = metadata.get("requests")
    if not isinstance(requests, list):
        return detail_ids, transcript_ids, terminal_ids, rate_limited_ids
    for request in requests:
        if not isinstance(request, Mapping):
            continue
        kind = str(request.get("tool") or request.get("kind") or "").casefold()
        ids = _request_ids(request)
        if kind in DETAIL_TOOLS:
            detail_ids.update(ids)
        if kind in TRANSCRIPT_TOOLS:
            transcript_ids.update(ids)
        status = _status_text(
            request.get("status")
            or request.get("outcome")
            or request.get("result")
            or ""
        )
        if status in TERMINAL_STATUSES:
            terminal_ids.update(ids)
        if status in RATE_LIMIT_STATUSES:
            rate_limited_ids.update(ids)
    return detail_ids, transcript_ids, terminal_ids, rate_limited_ids


def _load_capture(path: Path) -> Optional[Mapping[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _ids_from_records(payload: Mapping[str, Any]) -> Iterable[Tuple[str, Mapping[str, Any]]]:
    records = payload.get("meetings")
    if not isinstance(records, list):
        return ()
    output: List[Tuple[str, Mapping[str, Any]]] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        record_id = _record_id(record)
        if record_id:
            output.append((record_id, record))
    return output


def _db_id_sets(
    con: sqlite3.Connection,
    listed_ids: Set[str],
) -> Tuple[Set[str], Set[str]]:
    imported: Set[str] = set()
    searchable: Set[str] = set()
    rows = con.execute(
        """
        SELECT m.external_record_id, m.normalized_evidence_id,
               e.evidence_id AS evidence_id, f.evidence_id AS fts_evidence_id
        FROM mcp_item AS m
        LEFT JOIN evidence_record AS e
          ON e.evidence_id=m.normalized_evidence_id
        LEFT JOIN derived_text_fts AS f
          ON f.evidence_id=m.normalized_evidence_id
        WHERE m.provider='granola' AND m.external_record_id IS NOT NULL
        """
    ).fetchall()
    for row in rows:
        record_id = str(row["external_record_id"])
        if record_id not in listed_ids:
            continue
        imported.add(record_id)
        if row["evidence_id"] and row["fts_evidence_id"]:
            searchable.add(record_id)
    return imported, searchable


def _source_file_state(
    con: sqlite3.Connection,
    root: Path,
    paths: Iterable[Path],
) -> List[Dict[str, Any]]:
    rows = {
        str(row["relative_path"]): row
        for row in con.execute(
            """
            SELECT relative_path, source_version_id, status, extraction_status
            FROM source_record
            WHERE source_system='granola'
            """
        )
    }
    output: List[Dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        row = rows.get(relative)
        output.append(
            {
                "path": relative,
                "registered": row is not None,
                "source_version_id": row["source_version_id"] if row else None,
                "status": row["status"] if row else "missing",
                "extraction_status": row["extraction_status"] if row else "missing",
            }
        )
    return output


def _rest_api_progress(
    config: Config,
    con: sqlite3.Connection,
    root: Path,
) -> Dict[str, Any]:
    """Report the newest complete REST backfill separately from MCP IDs."""
    paths = sorted(root.glob("granola-api-backfill-*.json"))
    valid: List[Tuple[Path, Mapping[str, Any]]] = []
    for path in paths:
        payload = _load_capture(path)
        if not payload:
            continue
        capture = payload.get("_capture")
        if isinstance(capture, Mapping) and capture.get("transport") == "granola_rest_api":
            valid.append((path, payload))
    if not valid:
        return {
            "status": "not_recorded",
            "capture_file_count": len(paths),
            "note_count": 0,
            "unique_note_id_count": 0,
            "summary_count": 0,
            "transcript_count": 0,
            "summary_only_count": 0,
            "list_page_count": 0,
            "imported_id_count": 0,
            "searchable_id_count": 0,
        }

    path, payload = max(valid, key=lambda item: (item[0].stat().st_mtime_ns, item[0].name))
    raw_notes = payload.get("notes")
    meetings = payload.get("meetings")
    capture = payload.get("_capture")
    notes = [note for note in raw_notes if isinstance(note, Mapping)] if isinstance(raw_notes, list) else []
    normalized = [item for item in meetings if isinstance(item, Mapping)] if isinstance(meetings, list) else []
    note_ids = {
        str(note.get("id")).strip()
        for note in notes
        if _nonempty(note.get("id"))
    }
    imported_ids, searchable_ids = _db_id_sets(con, note_ids)
    errors = capture.get("errors", []) if isinstance(capture, Mapping) else []
    list_pages = capture.get("list_pages", []) if isinstance(capture, Mapping) else []
    complete = bool(
        notes
        and len(notes) == len(note_ids)
        and len(normalized) == len(note_ids)
        and len(imported_ids) == len(note_ids)
        and len(searchable_ids) == len(note_ids)
        and not errors
    )
    return {
        "status": "complete" if complete else "incomplete",
        "capture_file_count": len(paths),
        "capture_file": path.relative_to(config.root).as_posix(),
        "capture_id": _safe_capture_id(payload.get("capture_id")),
        "note_count": len(notes),
        "unique_note_id_count": len(note_ids),
        "summary_count": sum(
            1
            for note in notes
            if _nonempty(note.get("summary_markdown")) or _nonempty(note.get("summary_text"))
        ),
        "transcript_count": sum(
            1
            for note in notes
            if _nonempty(note.get("transcript"))
        ),
        "summary_only_count": sum(
            1
            for note in notes
            if (
                _nonempty(note.get("summary_markdown"))
                or _nonempty(note.get("summary_text"))
            )
            and not _nonempty(note.get("transcript"))
        ),
        "list_page_count": len(list_pages) if isinstance(list_pages, list) else 0,
        "imported_id_count": len(imported_ids),
        "searchable_id_count": len(searchable_ids),
        "missing_import_count": len(note_ids - imported_ids),
        "unsearchable_id_count": len(imported_ids - searchable_ids),
        "error_count": len(errors) if isinstance(errors, list) else 0,
    }


def _safe_capture_id(value: Any) -> str:
    """Return a bounded capture identifier for reports."""
    return str(value or "").strip()[:200]


def derive_granola_progress(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    """Return exact Granola coverage sets without changing source or DB state."""
    granola_root = config.source_root("mcp_granola").path
    inventory_paths = sorted(granola_root.glob("granola-inventory-*.json"))
    if not inventory_paths:
        raise ValueError(f"no Granola inventory snapshot found below {granola_root}")
    inventory_path = inventory_paths[-1]
    inventory_payload = _load_capture(inventory_path)
    if inventory_payload is None:
        raise ValueError(f"invalid Granola inventory snapshot: {inventory_path}")

    listed_ids = {
        record_id
        for record_id, _record in _ids_from_records(inventory_payload)
    }
    # Include both numbered heartbeat batches and valid content captures made
    # before the batch naming convention was established. Exact ID sets below
    # deduplicate any repeated capture of the same meeting.
    content_paths = sorted(granola_root.glob("granola-content-*.json"))
    content_ids: Set[str] = set()
    detailed_ids: Set[str] = set()
    transcript_ids: Set[str] = set()
    requested_detail_ids: Set[str] = set()
    requested_transcript_ids: Set[str] = set()
    terminal_ids: Set[str] = set()
    latest_rate_limited_ids: Set[str] = set()
    malformed_capture_paths: List[str] = []
    latest_content_path = (
        max(content_paths, key=lambda path: (path.stat().st_mtime_ns, path.name))
        if content_paths
        else None
    )

    for path in content_paths:
        payload = _load_capture(path)
        if payload is None:
            malformed_capture_paths.append(str(path))
            continue
        detail_requests, transcript_requests, terminal, rate_limited = _capture_requests(
            payload
        )
        requested_detail_ids.update(detail_requests)
        requested_transcript_ids.update(transcript_requests)
        terminal_ids.update(terminal)
        if path == latest_content_path:
            latest_rate_limited_ids = rate_limited
        for record_id, record in _ids_from_records(payload):
            content_ids.add(record_id)
            if _nonempty(record.get("summary")):
                detailed_ids.add(record_id)
            if _nonempty(record.get("transcript")):
                transcript_ids.add(record_id)

    previous_path = config.state_dir / "mcp" / "granola_detail_progress.json"
    previous = read_json(previous_path, {})
    previous_not_found = {
        str(value).strip()
        for value in (previous.get("not_found_ids", []) if isinstance(previous, Mapping) else [])
        if _nonempty(value)
    }
    previous_retries = {
        str(value).strip()
        for value in (
            previous.get("transcript_retry_ids", [])
            if isinstance(previous, Mapping)
            else []
        )
        if _nonempty(value)
    }

    terminal_listed_ids = terminal_ids & listed_ids
    detailed_listed_ids = detailed_ids & listed_ids
    transcript_listed_ids = transcript_ids & listed_ids
    content_listed_ids = content_ids & listed_ids
    metadata_only_ids = listed_ids - detailed_listed_ids - terminal_listed_ids
    transcript_pending_ids = listed_ids - transcript_listed_ids - terminal_listed_ids
    transcript_retry_ids = (
        (requested_transcript_ids | previous_retries)
        & transcript_pending_ids
    )
    detail_retry_ids = (
        requested_detail_ids & listed_ids & (listed_ids - detailed_listed_ids)
    ) - terminal_listed_ids
    retryable_ids = detail_retry_ids | transcript_retry_ids
    summary_only_ids = detailed_listed_ids - transcript_listed_ids
    transcript_only_ids = transcript_listed_ids - detailed_listed_ids
    outstanding_ids = metadata_only_ids | transcript_pending_ids
    imported_ids, searchable_ids = _db_id_sets(con, listed_ids)
    source_files = _source_file_state(con, config.root, [inventory_path, *content_paths])
    source_file_paths = {item["path"] for item in source_files}
    registered_source_files = {
        item["path"] for item in source_files if item["registered"]
    }
    priority_ids = sorted(retryable_ids) + sorted(
        (metadata_only_ids | summary_only_ids) - retryable_ids
    )
    rest_api = _rest_api_progress(config, con, granola_root)
    next_batch_size = (
        RATE_LIMIT_BATCH_SIZE if latest_rate_limited_ids else MAX_BATCH_SIZE
    )

    relative_inventory_path = inventory_path.relative_to(config.root).as_posix()
    return {
        "schema_version": 2,
        "provider": "granola",
        "status": "complete" if not outstanding_ids else "incomplete",
        "generated_at": now_iso(),
        "source_snapshot": relative_inventory_path,
        "capture_file_count": len(content_paths) + 1,
        "content_capture_file_count": len(content_paths),
        "registered_capture_file_count": len(registered_source_files),
        "unregistered_capture_files": sorted(source_file_paths - registered_source_files),
        "malformed_capture_files": sorted(malformed_capture_paths),
        "listed_id_count": len(listed_ids),
        "listed_ids": sorted(listed_ids),
        "content_captured_id_count": len(content_listed_ids),
        "content_captured_ids": sorted(content_listed_ids),
        "detailed_summary_id_count": len(detailed_listed_ids),
        "detailed_summary_ids": sorted(detailed_listed_ids),
        "transcript_id_count": len(transcript_listed_ids),
        "transcript_ids": sorted(transcript_listed_ids),
        "summary_only_ids": sorted(summary_only_ids),
        "transcript_only_ids": sorted(transcript_only_ids),
        "metadata_only_pending": len(metadata_only_ids),
        "metadata_only_ids": sorted(metadata_only_ids),
        "transcript_pending_count": len(transcript_pending_ids),
        "transcript_pending_ids": sorted(transcript_pending_ids),
        "requested_detail_id_count": len(requested_detail_ids & listed_ids),
        "requested_transcript_id_count": len(requested_transcript_ids & listed_ids),
        "detail_retry_ids": sorted(detail_retry_ids),
        "transcript_retry_ids": sorted(transcript_retry_ids),
        "retryable_ids": sorted(retryable_ids),
        "rate_limited_id_count": len(latest_rate_limited_ids),
        "rate_limited_ids": sorted(latest_rate_limited_ids),
        "terminal_unavailable_ids": sorted(terminal_ids),
        "terminal_unavailable_listed_ids": sorted(terminal_listed_ids),
        "requested_ids_not_in_inventory": sorted(
            (requested_detail_ids | requested_transcript_ids) - listed_ids
        ),
        "returned_ids_not_in_inventory": sorted(content_ids - listed_ids),
        "previous_state_not_found_ids": sorted(previous_not_found),
        "previous_state_not_listed_ids": sorted(previous_not_found - listed_ids),
        "imported_id_count": len(imported_ids),
        "imported_ids": sorted(imported_ids),
        "searchable_id_count": len(searchable_ids),
        "searchable_ids": sorted(searchable_ids),
        "unimported_ids": sorted(listed_ids - imported_ids),
        "unsearchable_ids": sorted(imported_ids - searchable_ids),
        "max_batch_size": MAX_BATCH_SIZE,
        "next_batch_size": next_batch_size,
        "next_batch_ids": priority_ids[:next_batch_size],
        "batch_policy": (
            "rate_limit_recovery"
            if latest_rate_limited_ids
            else "connector_maximum"
        ),
        "next_action": (
            "All listed meetings have detailed summaries and transcripts or supported terminal outcomes."
            if not outstanding_ids
            else (
                "Retry rate-limited IDs first with a five-ID recovery batch."
                if latest_rate_limited_ids
                else "Retry retryable IDs first, then fetch up to ten pending detail/transcript IDs."
            )
        ),
        "source_files": source_files,
        "rest_api": rest_api,
    }


def write_granola_progress(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    """Derive and persist the local Granola progress checkpoint."""
    progress = derive_granola_progress(config, con)
    path = config.state_dir / "mcp" / "granola_detail_progress.json"
    config.assert_derived_path(path)
    atomic_write_json(path, progress)
    return progress
