from __future__ import annotations

from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re
import sqlite3
from datetime import date
from typing import Any, Dict, List, Tuple

from .config import Config
from .db import current_tasks
from .normalize import _pointer_only
from .util import (
    atomic_write_json,
    atomic_write_text,
    ensure_dir,
    human_bytes,
    now_iso,
    read_text_guess,
    scrub_fts_text,
    write_csv,
)
from .zoom import (
    FINAL_MEDIA_EXTENSIONS,
    TERMINAL_QUEUE_STATUSES,
    zoom_meeting_folder,
)


MANIFEST_FIELDS = [
    "source_id",
    "source_version_id",
    "source_root_key",
    "root_match_kind",
    "relative_path",
    "absolute_path",
    "source_system",
    "kind",
    "extension",
    "size_bytes",
    "mtime_ns",
    "content_sha256",
    "date_hint",
    "scope_proposal",
    "scope_reason",
    "classification",
    "sensitivity",
    "parse_readiness",
    "extraction_status",
    "career_value",
    "operations_value",
    "duplicate_group_id",
    "archive_member_count",
    "archive_semantic_status",
    "archive_extracted_root_key",
    "status",
    "first_seen",
    "last_seen",
]
ARCHIVE_MEMBER_FIELDS = [
    "source_id",
    "archive_path",
    "source_system",
    "member_path",
    "size_bytes",
    "compressed_size_bytes",
    "is_directory",
    "encrypted",
    "semantic_status",
    "extracted_root_key",
]
RESIDUAL_FIELDS = [
    "relative_path",
    "absolute_path",
    "source_id",
    "source_system",
    "kind",
    "extension",
    "size_bytes",
    "mtime_ns",
    "scope_proposal",
    "scope_reason",
    "status",
]


def write_manifest_reports(config: Config, rows: List[Dict[str, Any]]) -> Path:
    """Write derived manifest views without touching the reviewed inventory."""
    reports = ensure_dir(config.corpus_dir / "reports")
    manifest_path = reports / "source_manifest.csv"
    archive_path = reports / "archive_members.csv"
    residual_path = reports / "source_root_residuals.csv"
    for path in (manifest_path, archive_path, residual_path):
        config.assert_derived_path(path)

    archive_rows: List[Dict[str, Any]] = []
    residual_rows: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("root_match_kind") == "residual" and row.get("status") == "present":
            residual_rows.append(row)
        for member in row.get("archive_members") or []:
            archive_rows.append(
                {
                    "source_id": row.get("source_id", ""),
                    "archive_path": row.get("relative_path", ""),
                    "source_system": row.get("source_system", ""),
                    "member_path": member.get("member_path", ""),
                    "size_bytes": member.get("size_bytes", 0),
                    "compressed_size_bytes": member.get("compressed_size_bytes", 0),
                    "is_directory": member.get("is_directory", False),
                    "encrypted": member.get("encrypted", False),
                    "semantic_status": row.get("archive_semantic_status", ""),
                    "extracted_root_key": row.get("archive_extracted_root_key", ""),
                }
            )

    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    write_csv(archive_path, archive_rows, ARCHIVE_MEMBER_FIELDS)
    write_csv(residual_path, residual_rows, RESIDUAL_FIELDS)
    return manifest_path


def _count_phrase(count: int, singular: str, plural: str = "") -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _scalar(con: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    row = con.execute(query, params).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _safe_text(value: Any) -> str:
    """Keep report strings free of URLs and secret-like values."""
    return scrub_fts_text(str(value or ""))


def _read_state_json(config: Config, name: str) -> Dict[str, Any]:
    path = config.state_dir / name
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _physical_summary(con: sqlite3.Connection) -> Dict[str, int]:
    rows = con.execute(
        "SELECT relative_path, status FROM source_record"
    ).fetchall()
    present = [row for row in rows if row["status"] == "present"]
    finder = sum(
        Path(str(row["relative_path"])).name.casefold() == ".ds_store"
        for row in present
    )
    return {
        "present_files": len(present),
        "missing_files": sum(row["status"] == "missing" for row in rows),
        "finder_metadata_files": finder,
        "substantive_files": len(present) - finder,
    }


def _source_root_coverage(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    roots = {
        row["root_key"]: row
        for row in con.execute(
            "SELECT root_key, relative_path, source_system FROM source_root"
        )
    }
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in con.execute(
        """
        SELECT root_key, source_system, relative_path, size_bytes
        FROM source_record
        WHERE status='present'
        ORDER BY root_key, relative_path
        """
    ):
        root_key = str(row["root_key"] or "residual")
        root = roots.get(root_key)
        item = grouped.setdefault(
            root_key,
            {
                "root_key": root_key,
                "root_path": root["relative_path"] if root is not None else "",
                "source_system": row["source_system"],
                "files": 0,
                "substantive_files": 0,
                "bytes": 0,
            },
        )
        item["files"] += 1
        if Path(str(row["relative_path"])).name.casefold() != ".ds_store":
            item["substantive_files"] += 1
        item["bytes"] += int(row["size_bytes"] or 0)

    for root_key, root in roots.items():
        if root_key in grouped:
            continue
        grouped[root_key] = {
            "root_key": root_key,
            "root_path": root["relative_path"],
            "source_system": root["source_system"],
            "files": 0,
            "substantive_files": 0,
            "bytes": 0,
        }
    for item in grouped.values():
        item["human_size"] = human_bytes(int(item["bytes"]))
    return [grouped[key] for key in sorted(grouped)]


def _discovery_excluded(con: sqlite3.Connection) -> Dict[str, int]:
    rows = con.execute(
        """
        SELECT source_id, source_version_id
        FROM source_record
        WHERE status='present'
          AND (kind='discovery' OR source_system='inventory_discovery')
        """
    ).fetchall()
    source_ids = [str(row["source_id"]) for row in rows]
    versions = [str(row["source_version_id"]) for row in rows if row["source_version_id"]]
    if not versions:
        return {
            "source_files": len(source_ids),
            "source_versions": 0,
            "normalized_documents": 0,
            "evidence_records": 0,
        }
    placeholders = ",".join("?" for _value in versions)
    normalized = _scalar(
        con,
        f"SELECT COUNT(*) FROM normalized_document WHERE source_version_id IN ({placeholders})",
        tuple(versions),
    )
    evidence = _scalar(
        con,
        f"SELECT COUNT(*) FROM evidence_record WHERE source_version_id IN ({placeholders})",
        tuple(versions),
    )
    return {
        "source_files": len(source_ids),
        "source_versions": len(versions),
        "normalized_documents": normalized,
        "evidence_records": evidence,
    }


def _normalization_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    statuses = {
        str(row["status"] or "unknown"): int(row["count"])
        for row in con.execute(
            "SELECT status, COUNT(*) AS count FROM normalized_document GROUP BY status ORDER BY status"
        )
    }
    return {
        "total_source_versions": sum(statuses.values()),
        "by_status": statuses,
        "normalized": statuses.get("normalized", 0),
        "unsupported": statuses.get("unsupported", 0),
        "failed": statuses.get("error", 0),
        "prior_good_retained": statuses.get("prior_good_retained", 0),
    }


def _onenote_summary(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    files = _scalar(
        con,
        """
        SELECT COUNT(*) FROM source_record
        WHERE status='present' AND source_system='onenote' AND lower(extension)='.one'
        """,
    )
    status_counts = {
        str(row["status"] or "unknown"): int(row["count"])
        for row in con.execute(
            """
            SELECT n.status, COUNT(*) AS count
            FROM normalized_document n
            JOIN source_record s ON s.source_version_id=n.source_version_id
            WHERE s.source_system='onenote'
            GROUP BY n.status ORDER BY n.status
            """
        )
    }
    state = _read_state_json(config, "onenote_acceptance.json")
    return {
        "files": files,
        "parsed_files": status_counts.get("normalized", 0),
        "pages_extracted": int(state.get("pages_extracted", 0) or 0),
        "reviewed_expected_pages": int(state.get("reviewed_expected_pages", 295) or 295),
        "converter_available": bool(state.get("converter_available", False)),
        "raw_read": bool(state.get("raw_read", False)),
        "status_counts": status_counts or {
            str(key): int(value)
            for key, value in (state.get("status_counts") or {}).items()
        },
    }


def _capacities_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    pointer_only = 0
    for row in con.execute(
        """
        SELECT absolute_path, extension
        FROM source_record
        WHERE status='present' AND source_system='capacities'
        """
    ):
        extension = str(row["extension"] or "").casefold()
        if extension not in {".md", ".markdown", ".csv"}:
            continue
        try:
            raw = read_text_guess(Path(str(row["absolute_path"])), max_bytes=20 * 1024 * 1024)
        except (OSError, UnicodeError, ValueError):
            continue
        if extension in {".md", ".markdown"}:
            is_pointer = _pointer_only(raw)
        else:
            is_pointer = bool(
                re.search(r"(?i)\b(?:file|image|pdf)\b", raw)
                and re.search(r"(?i)\b(?:url|path|payload)\b", raw)
            )
        pointer_only += int(is_pointer)
    return {
        "pointer_only_payloads": pointer_only,
        "signed_urls_fetched": 0,
    }


def _notion_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    page_count = _scalar(
        con,
        """
        SELECT COUNT(*) FROM source_record
        WHERE status='present' AND source_system='notion'
          AND lower(extension) IN ('.html', '.htm')
        """,
    )
    database_count = _scalar(
        con,
        """
        SELECT COUNT(*) FROM source_record
        WHERE status='present' AND source_system='notion'
          AND lower(extension)='.csv'
        """,
    )
    attachment_count = _scalar(
        con,
        """
        SELECT COUNT(*) FROM source_record
        WHERE status='present' AND source_system='notion'
          AND lower(extension) IN (
              '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp',
              '.pptx', '.xlsx', '.docx', '.doc', '.xls', '.ppt'
          )
        """,
    )
    unresolved = _scalar(
        con,
        """
        SELECT COUNT(*) FROM review_item
        WHERE status='pending' AND lower(issue_type) LIKE '%notion%relationship%'
        """,
    )
    return {
        "page_count": page_count,
        "database_count": database_count,
        "attachment_count": attachment_count,
        "unresolved_relationships": unresolved,
    }


def _review_queue_summary(
    con: sqlite3.Connection,
    sensitive_review_count: int,
) -> Dict[str, Any]:
    by_issue_type = {
        _safe_text(row["issue_type"]): int(row["count"])
        for row in con.execute(
            """
            SELECT issue_type, COUNT(*) AS count
            FROM review_item WHERE status='pending'
            GROUP BY issue_type ORDER BY issue_type
            """
        )
    }
    scope_pending = sum(
        count
        for issue_type, count in by_issue_type.items()
        if "scope" in issue_type.casefold()
    )
    return {
        "scope": {
            "pending_review_items": scope_pending,
            "meeting_groups_needing_review": _scalar(
                con, "SELECT COUNT(*) FROM meeting_group WHERE status='needs_review'"
            ),
        },
        "sensitivity": {
            "source_records_for_review": sensitive_review_count,
        },
        "pending_by_issue_type": by_issue_type,
    }


def _entity_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    return {
        "entities": _scalar(con, "SELECT COUNT(*) FROM entity"),
        "aliases": _scalar(con, "SELECT COUNT(*) FROM entity_alias"),
        "unresolved_mentions": _scalar(
            con,
            "SELECT COUNT(*) FROM entity_mention WHERE resolution_status NOT IN ('resolved', 'confirmed')",
        ),
        "ambiguous_merge_proposals": _scalar(
            con,
            "SELECT COUNT(*) FROM review_item WHERE status='pending' AND issue_type='entity_collision'",
        ),
    }


def _task_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    total = _scalar(con, "SELECT COUNT(*) FROM task")
    current = len(current_tasks(con, date.today()))
    candidate_statuses = {
        _safe_text(row["candidate_status"] or "unknown"): int(row["count"])
        for row in con.execute(
            "SELECT candidate_status, COUNT(*) AS count FROM task GROUP BY candidate_status ORDER BY candidate_status"
        )
    }
    return {
        "total_candidates": total,
        "current_candidates": current,
        "historical_or_review_candidates": max(total - current, 0),
        "candidate_statuses": candidate_statuses,
    }


def _index_summary(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    fts_rows = _scalar(con, "SELECT COUNT(*) FROM derived_text_fts")
    relationship_rows = _scalar(con, "SELECT COUNT(*) FROM relationship")
    state = _read_state_json(config, "index_rebuild.json")
    recorded = "fts_rows" in state and "relationship_rows" in state
    fresh = bool(
        recorded
        and int(state.get("fts_rows", -1)) == fts_rows
        and int(state.get("relationship_rows", -1)) == relationship_rows
    )
    return {
        "fts": {
            "rows": fts_rows,
            "freshness": "fresh" if fresh else ("not_recorded" if not recorded else "stale"),
        },
        "relationships": {
            "rows": relationship_rows,
            "freshness": "fresh" if fresh else ("not_recorded" if not recorded else "stale"),
        },
    }


def _raw_immutability_summary(config: Config) -> Dict[str, Any]:
    state = _read_state_json(config, "raw_immutability.json")
    if not state:
        return {"status": "not_recorded"}
    output: Dict[str, Any] = {
        "status": _safe_text(state.get("status", "unknown")),
        "mismatch_count": int(state.get("mismatch_count", 0) or 0),
    }
    for key in (
        "before_files",
        "after_files",
        "before_bytes",
        "after_bytes",
        "before_stream_sha256",
        "after_stream_sha256",
        "compared_at",
    ):
        if key in state:
            output[key] = state[key]
    return output


def _normalised_queue_status(status: Any, approval_status: Any = "") -> str:
    value = str(status or "")
    approval = str(approval_status or "")
    if value == "pending":
        return "queued" if approval == "approved" else "pending_approval"
    if value == "needs_review":
        return "pending_approval"
    if value == "error":
        return "failed"
    if value == "complete":
        return "succeeded"
    return value or "unknown"


def _transcription_retry_count(con: sqlite3.Connection) -> Tuple[int, int]:
    total = 0
    runs = 0
    for row in con.execute(
        "SELECT details_json FROM pipeline_run WHERE command='transcribe'"
    ):
        try:
            details = json.loads(row["details_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        value = details.get("retried", 0)
        if isinstance(value, int) and value > 0:
            total += value
            runs += 1
    return total, runs


def _zoom_summary(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    dated_folders = {
        folder
        for row in con.execute(
            "SELECT relative_path FROM source_record "
            "WHERE status='present' AND source_system='zoom'"
        )
        if (folder := zoom_meeting_folder(str(row["relative_path"])))
    }
    group_counts = {
        _safe_text(row["status"]): int(row["count"])
        for row in con.execute(
            "SELECT status, COUNT(*) AS count FROM meeting_group GROUP BY status ORDER BY status"
        )
    }
    rows = con.execute(
        """
        SELECT j.status, j.approval_status, j.started_at, j.output_sha256,
               j.error, j.media_source_id, j.media_version_id,
               s.extension, s.classification, s.status AS source_status,
               s.extraction_status, s.source_version_id,
               g.transcript_source_id
        FROM transcription_job j
        LEFT JOIN source_record s ON s.source_id=j.media_source_id
        LEFT JOIN meeting_group g ON g.group_id=j.group_id
        ORDER BY j.job_id
        """
    ).fetchall()
    status_counts: Counter[str] = Counter()
    terminal_counts: Counter[str] = Counter()
    failure_reasons: Counter[Tuple[str, str]] = Counter()
    eligible_media = []
    missing_transcripts = []
    for row in rows:
        status = _normalised_queue_status(row["status"], row["approval_status"])
        status_counts[status] += 1
        if (
            str(row["extension"] or "").casefold() in FINAL_MEDIA_EXTENSIONS
            and str(row["classification"] or "").casefold() == "work"
            and row["source_status"] == "present"
            and row["extraction_status"] == "ready"
            and row["media_source_id"]
            and row["media_version_id"]
            and row["media_version_id"] == row["source_version_id"]
        ):
            eligible_media.append((row, status))
            has_usable_transcript = bool(row["transcript_source_id"]) or (
                status in {"succeeded", "partial"}
                and bool(row["output_sha256"])
            )
            if not has_usable_transcript:
                missing_transcripts.append((row, status))
            if status in TERMINAL_QUEUE_STATUSES:
                terminal_counts[status] += 1
            if not has_usable_transcript and status in {"failed", "blocked", "artifact"}:
                failure_reasons[(status, _safe_text(row["error"] or "unspecified"))] += 1
    retries, retry_runs = _transcription_retry_count(con)
    return {
        "dated_folders_observed": len(dated_folders),
        "tracked_groups": sum(group_counts.values()),
        "group_counts": group_counts,
        "existing_transcripts": group_counts.get("existing_transcript", 0),
        "generated_transcripts": sum(
            count for status, count in group_counts.items()
            if status in {"generated_transcript", "succeeded", "partial"}
        ),
        "transcript_only_groups": group_counts.get("transcript_only", 0),
        "unmatched_transcript_only_groups": group_counts.get("transcript_only", 0),
        "transcription_status_counts": dict(sorted(status_counts.items())),
        "terminal_local_status_counts": dict(sorted(terminal_counts.items())),
        "eligible_final_media_without_transcript": len(missing_transcripts),
        "eligible_media_without_terminal_status": sum(
            status not in TERMINAL_QUEUE_STATUSES
            for _row, status in eligible_media
        ),
        "attempted": sum(
            bool(row["started_at"]) for row, _status in eligible_media
        ),
        "retries": retries,
        "retry_runs": retry_runs,
        "output_hashes": sum(
            bool(row["output_sha256"]) for row, _status in eligible_media
        ),
        "failure_reasons": [
            {"status": status, "reason": reason, "count": count}
            for (status, reason), count in sorted(failure_reasons.items())
        ],
    }


def _coverage(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = []
    systems = [row[0] for row in con.execute(
        "SELECT DISTINCT source_system FROM source_record WHERE status='present' ORDER BY source_system"
    )]
    for system in systems:
        count = _scalar(
            con,
            "SELECT COUNT(*) FROM source_record WHERE status='present' AND source_system=?",
            (system,),
        )
        total = _scalar(
            con,
            "SELECT COALESCE(SUM(size_bytes),0) FROM source_record WHERE status='present' AND source_system=?",
            (system,),
        )
        dates = [
            row[0]
            for row in con.execute(
                """
                SELECT date_hint FROM source_record
                WHERE status='present' AND source_system=? AND date_hint IS NOT NULL AND date_hint<>''
                ORDER BY date_hint
                """,
                (system,),
            )
        ]
        rows.append({
            "source_system": system,
            "files": count,
            "bytes": total,
            "human_size": human_bytes(total),
            "earliest_date_hint": dates[0] if dates else "",
            "latest_date_hint": dates[-1] if dates else "",
        })
    return rows


def _mcp_freshness(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Report retrieval freshness without treating unknown dates as current."""
    output: List[Dict[str, Any]] = []
    for row in con.execute(
        """
        SELECT provider, COUNT(*) AS item_count,
               COUNT(retrieval_date) AS known_retrieval_dates,
               MAX(retrieval_date) AS latest_retrieval_date
        FROM mcp_item
        GROUP BY provider
        ORDER BY provider
        """
    ):
        output.append(
            {
                "provider": row["provider"],
                "item_count": row["item_count"],
                "known_retrieval_dates": row["known_retrieval_dates"],
                "latest_retrieval_date": row["latest_retrieval_date"] or "",
                "freshness": "unknown" if not row["known_retrieval_dates"] else "known",
            }
        )
    return output


def _unsupported(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = []
    for row in con.execute(
        """
        SELECT s.source_system, s.extension, n.status, n.error, COUNT(*) AS count
        FROM normalized_document n
        JOIN source_record s ON s.source_id=n.source_id
        WHERE n.status IN ('unsupported','error')
        GROUP BY s.source_system, s.extension, n.status, n.error
        ORDER BY count DESC, s.source_system, s.extension
        """
    ):
        rows.append(dict(row))
    return rows


def _duplicates(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT duplicate_group_id, content_sha256, COUNT(*) AS file_count,
                   SUM(size_bytes) AS total_bytes,
                   GROUP_CONCAT(relative_path, ' | ') AS paths
            FROM source_record
            WHERE status='present' AND duplicate_group_id IS NOT NULL
            GROUP BY duplicate_group_id, content_sha256
            ORDER BY file_count DESC, duplicate_group_id
            """
        )
    ]


def _version_family_key(relative_path: str) -> str:
    path = Path(relative_path)
    stem = path.stem.lower()
    stem = re.sub(r"(?<![a-z])20\d{2}[-_. ]?\d{0,2}[-_. ]?\d{0,2}(?![a-z])", " ", stem)
    stem = re.sub(r"\b(?:final|draft|copy|revised|updated|new|old|latest|clean|redline|edit|edited)\b", " ", stem)
    stem = re.sub(r"\b(?:v|ver|version|rev|revision)[-_. ]?\d+(?:[._-]\d+)*\b", " ", stem)
    stem = re.sub(r"\(\d+\)$", " ", stem)
    stem = re.sub(r"[-_. ]+", " ", stem).strip()
    if len(stem) < 5:
        return ""
    return stem + path.suffix.lower()


def _version_families(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    groups: Dict[tuple, List[str]] = defaultdict(list)
    for row in con.execute(
        "SELECT source_system, relative_path FROM source_record WHERE status='present'"
    ):
        key = _version_family_key(row["relative_path"])
        if key:
            groups[(row["source_system"], key)].append(row["relative_path"])
    output = []
    for (system, key), paths in groups.items():
        if len(paths) < 2:
            continue
        output.append({
            "source_system": system,
            "family_key": key,
            "file_count": len(paths),
            "paths": " | ".join(sorted(paths)),
        })
    return sorted(output, key=lambda row: (-row["file_count"], row["source_system"], row["family_key"]))


def _sensitive_review(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT source_id, relative_path, source_system, classification,
                   sensitivity, parse_readiness, career_value, operations_value
            FROM source_record
            WHERE status='present'
              AND (
                  classification IN (
                      'potential_personal', 'mixed_or_review',
                      'Personal', 'Mixed', 'Unknown'
                  )
                  OR sensitivity='potential_restricted'
              )
            ORDER BY classification, sensitivity, relative_path
            """
        )
    ]


def _largest(con: sqlite3.Connection, limit: int = 30) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT relative_path, source_system, kind, extension, size_bytes
            FROM source_record
            WHERE status='present'
            ORDER BY size_bytes DESC
            LIMIT ?
            """,
            (limit,),
        )
    ]


def build_report(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    reports = config.corpus_dir / "reports"
    config.assert_derived_path(reports)
    reports = ensure_dir(reports)
    coverage = _coverage(con)
    mcp_freshness = _mcp_freshness(con)
    unsupported = _unsupported(con)
    largest = _largest(con)
    duplicates = _duplicates(con)
    version_families = _version_families(con)
    sensitive_review = _sensitive_review(con)
    physical = _physical_summary(con)
    source_counts_by_root = _source_root_coverage(con)
    discovery_excluded = _discovery_excluded(con)
    normalization = _normalization_summary(con)
    onenote = _onenote_summary(config, con)
    capacities = _capacities_summary(con)
    notion = _notion_summary(con)
    review_queues = _review_queue_summary(con, len(sensitive_review))
    entities = _entity_summary(con)
    tasks = _task_summary(con)
    indexes = _index_summary(config, con)
    zoom = _zoom_summary(config, con)
    raw_immutability = _raw_immutability_summary(config)

    source_count = physical["present_files"]
    source_bytes = _scalar(con, "SELECT COALESCE(SUM(size_bytes),0) FROM source_record WHERE status='present'")
    normalized = normalization["normalized"]
    normalize_errors = normalization["failed"]
    normalize_unsupported = normalization["unsupported"]
    mcp_count = _scalar(con, "SELECT COUNT(*) FROM mcp_item")
    zoom_total = zoom["dated_folders_observed"]
    zoom_tracked_groups = zoom["tracked_groups"]
    zoom_existing = zoom["existing_transcripts"]
    zoom_generated = zoom["generated_transcripts"]
    zoom_missing = zoom["eligible_final_media_without_transcript"]
    zoom_unprocessed = zoom["eligible_media_without_terminal_status"]
    tx_pending = sum(
        zoom["transcription_status_counts"].get(status, 0)
        for status in ("pending", "pending_approval", "queued", "running")
    )
    tx_errors = zoom["transcription_status_counts"].get("failed", 0)

    summary = {
        "generated_at": now_iso(),
        "source_files": source_count,
        "source_bytes": source_bytes,
        "source_size": human_bytes(source_bytes),
        "normalized_documents": normalized,
        "normalization_errors": normalize_errors,
        "normalization_unsupported": normalize_unsupported,
        "mcp_items": mcp_count,
        "zoom_meeting_folders": zoom_total,
        "zoom_tracked_groups": zoom_tracked_groups,
        "zoom_existing_transcripts": zoom_existing,
        "zoom_generated_transcripts": zoom_generated,
        "zoom_missing_transcripts": zoom_missing,
        "zoom_media_without_terminal_status": zoom_unprocessed,
        "transcription_jobs_pending": tx_pending,
        "transcription_jobs_error": tx_errors,
        "exact_duplicate_groups": len(duplicates),
        "likely_version_families": len(version_families),
        "sensitive_review_candidates": len(sensitive_review),
        "coverage": coverage,
        "mcp_feed_freshness": mcp_freshness,
        "unsupported": unsupported,
        "physical": physical,
        "source_counts_by_root": source_counts_by_root,
        "discovery_excluded": discovery_excluded,
        "normalization": normalization,
        "zoom": zoom,
        "onenote": onenote,
        "capacities": capacities,
        "notion": notion,
        "review_queues": review_queues,
        "entities": entities,
        "tasks": tasks,
        "indexes": indexes,
        "raw_immutability": raw_immutability,
    }
    atomic_write_json(reports / "status.json", summary)

    write_csv(
        reports / "coverage.csv",
        coverage,
        ["source_system", "files", "bytes", "human_size", "earliest_date_hint", "latest_date_hint"],
    )
    write_csv(
        reports / "unsupported_and_errors.csv",
        unsupported,
        ["source_system", "extension", "status", "error", "count"],
    )
    write_csv(
        reports / "mcp_feed_freshness.csv",
        mcp_freshness,
        [
            "provider",
            "item_count",
            "known_retrieval_dates",
            "latest_retrieval_date",
            "freshness",
        ],
    )
    write_csv(
        reports / "largest_files.csv",
        largest,
        ["relative_path", "source_system", "kind", "extension", "size_bytes"],
    )
    write_csv(
        reports / "duplicate_groups.csv",
        duplicates,
        ["duplicate_group_id", "content_sha256", "file_count", "total_bytes", "paths"],
    )
    write_csv(
        reports / "likely_version_families.csv",
        version_families,
        ["source_system", "family_key", "file_count", "paths"],
    )
    write_csv(
        reports / "excluded_or_sensitive_review.csv",
        sensitive_review,
        [
            "source_id", "relative_path", "source_system", "classification",
            "sensitivity", "parse_readiness", "career_value", "operations_value",
        ],
    )
    write_csv(
        reports / "source_roots.csv",
        source_counts_by_root,
        [
            "root_key", "root_path", "source_system", "files",
            "substantive_files", "bytes", "human_size",
        ],
    )
    write_csv(
        reports / "normalization_status.csv",
        [
            {"status": status, "count": count}
            for status, count in normalization["by_status"].items()
        ],
        ["status", "count"],
    )
    write_csv(
        reports / "zoom_transcription_status.csv",
        [
            {"status": status, "count": count}
            for status, count in zoom["transcription_status_counts"].items()
        ],
        ["status", "count"],
    )
    write_csv(
        reports / "review_queues.csv",
        [
            {"issue_type": issue_type, "count": count}
            for issue_type, count in review_queues["pending_by_issue_type"].items()
        ],
        ["issue_type", "count"],
    )
    write_csv(
        reports / "task_candidates.csv",
        [
            {"candidate_status": status, "count": count}
            for status, count in tasks["candidate_statuses"].items()
        ],
        ["candidate_status", "count"],
    )

    needs: List[str] = []
    if source_count == 0:
        needs.append("No raw source files are currently present under `data/`.")
    if not any(row["source_system"] == "capacities" for row in coverage):
        needs.append("No Capacities export has been identified.")
    if not any(row["source_system"] == "notion" for row in coverage):
        needs.append("No Notion export has been identified.")
    if not any(row["source_system"] == "onenote" for row in coverage):
        needs.append("No OneNote export has been identified.")
    if not any(row["source_system"] == "granola" for row in coverage):
        needs.append("No durable Granola dump has been identified; MCP access alone is not a raw archive.")
    if not any(row["source_system"] == "wispr_flow" for row in coverage):
        needs.append("No durable Wispr Flow dump has been identified.")
    if zoom_unprocessed:
        needs.append(
            f"{zoom_unprocessed} eligible Zoom media items still have no terminal local status."
        )
    blocked_media = zoom["terminal_local_status_counts"].get("blocked", 0)
    if blocked_media:
        needs.append(
            f"{blocked_media} eligible Zoom media items are blocked; a verified local transcription engine is required for successful transcription."
        )
    if normalize_unsupported:
        needs.append(f"{normalize_unsupported} files require conversion or an optional parser.")
    if normalize_errors:
        needs.append(f"{normalize_errors} files produced parsing errors.")
    if tx_errors:
        needs.append(f"{tx_errors} local transcription jobs failed and need review.")
    if duplicates:
        needs.append(f"{_count_phrase(len(duplicates), 'exact duplicate group')} detected among hashed files.")
    if version_families:
        needs.append(f"{_count_phrase(len(version_families), 'likely version family', 'likely version families')} need review; they were not merged.")
    if sensitive_review:
        needs.append(f"{_count_phrase(len(sensitive_review), 'filename/path', 'filenames/paths')} flagged for personal or restricted-content review.")
    if not onenote["converter_available"] and onenote["files"]:
        needs.append("The OneNote converter is unavailable; `.one` files remain raw and blocked.")
    if raw_immutability.get("status") != "passed":
        needs.append("Raw immutability has not been recorded as passed for the current acceptance run.")
    if any(
        section["freshness"] != "fresh"
        for section in indexes.values()
    ):
        needs.append("FTS and relationship index freshness is not yet confirmed by the acceptance run.")

    next_steps = []
    missing_note_sources = [
        name for name in ("capacities", "notion", "onenote")
        if not any(row["source_system"] == name for row in coverage)
    ]
    if missing_note_sources:
        next_steps.append(
            "Add or export the missing note sources under `data/notes/`: "
            + ", ".join(missing_note_sources)
            + "."
        )
    if not any(row["source_system"] == "inventory_discovery" for row in coverage):
        next_steps.append(
            "When the separate note-inventory finishes, place its unpacked report folder under `data/note-inventory-20260903-142816/` and rerun."
        )
    if tx_pending:
        next_steps.append(
            "Review `state/transcription_queue.csv`, configure a local Whisper engine, and run a small transcription batch."
        )
    if mcp_count == 0:
        next_steps.append(
            "Use the MCP capture prompts to persist a small Granola and Wispr Flow sample under `data/mcp/`."
        )
    if normalize_unsupported:
        next_steps.append(
            "Review `unsupported_and_errors.csv`; install optional document parsers or export proprietary formats."
        )
    if not next_steps:
        next_steps.append("The mechanical evidence layer is ready for project/task/career extraction.")

    md = [
        "# What We Have and What We Need",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Current corpus",
        "",
        f"- Raw source files: **{source_count:,}** ({human_bytes(source_bytes)})",
        f"- Substantive source files: **{physical['substantive_files']:,}**; Finder metadata: **{physical['finder_metadata_files']:,}**",
        f"- Normalized documents: **{normalized:,}**",
        f"- Granola/Wispr MCP items: **{mcp_count:,}**",
        f"- Zoom dated source folders observed: **{zoom_total:,}**",
        f"- Zoom groups with tracked media, transcripts, or artifacts: **{zoom_tracked_groups:,}**",
        f"- Existing Zoom transcripts: **{zoom_existing:,}**",
        f"- Locally generated Zoom transcripts: **{zoom_generated:,}**",
        f"- Eligible final Zoom media without a usable transcript: **{zoom_missing:,}**",
        f"- Eligible final Zoom media without terminal status: **{zoom_unprocessed:,}**",
        f"- Exact duplicate groups: **{len(duplicates):,}**",
        f"- Likely version families: **{len(version_families):,}**",
        f"- Sensitive-review candidates: **{len(sensitive_review):,}**",
        f"- Raw immutability: **{raw_immutability.get('status', 'not_recorded')}**",
        "",
        "## Physical and source-root accounting",
        "",
        "| Root | Source system | Files | Substantive | Size |",
        "|---|---|---:|---:|---:|",
    ]
    for row in source_counts_by_root:
        md.append(
            f"| {row['root_key']} | {row['source_system']} | {row['files']:,} | "
            f"{row['substantive_files']:,} | {row['human_size']} |"
        )
    md.extend([
        "",
        "## Discovery and normalization",
        "",
        f"Discovery rows excluded from extraction: **{discovery_excluded['source_files']:,}** "
        f"({discovery_excluded['normalized_documents']:,} normalized, "
        f"{discovery_excluded['evidence_records']:,} evidence records).",
        "",
        "| Normalization status | Count |",
        "|---|---:|",
    ])
    for status, count in normalization["by_status"].items():
        md.append(f"| {status} | {count:,} |")
    md.extend([
        "",
        "## Zoom coverage run",
        "",
        f"Existing transcript groups: **{zoom['existing_transcripts']:,}**; "
        f"generated transcript groups: **{zoom['generated_transcripts']:,}**; "
        f"transcript-only groups without a linked media group: **{zoom['unmatched_transcript_only_groups']:,}**.",
        f"Eligible final media without a usable transcript: **{zoom['eligible_final_media_without_transcript']:,}**; "
        f"without a terminal status: **{zoom['eligible_media_without_terminal_status']:,}**.",
        "",
        "| Transcription status | Count |",
        "|---|---:|",
    ])
    for status, count in zoom["transcription_status_counts"].items():
        md.append(f"| {status} | {count:,} |")
    md.extend([
        "",
        f"Local attempts: **{zoom['attempted']:,}**; retries recorded from run history: **{zoom['retries']:,}**; "
        f"output hashes: **{zoom['output_hashes']:,}**.",
        "",
        "## Adapter and derived-view status",
        "",
        f"- OneNote: {onenote['files']:,} files; {onenote['parsed_files']:,} parsed; "
        f"{onenote['pages_extracted']:,} pages extracted of {onenote['reviewed_expected_pages']:,} reviewed pages; "
        f"converter_available={str(onenote['converter_available']).lower()}.",
        f"- Capacities pointer-only payloads: {capacities['pointer_only_payloads']:,}; signed URLs fetched: {capacities['signed_urls_fetched']:,}.",
        f"- Notion: {notion['page_count']:,} pages, {notion['database_count']:,} databases, "
        f"{notion['attachment_count']:,} local attachments, {notion['unresolved_relationships']:,} unresolved relationships.",
        f"- Review queues: {review_queues['scope']['pending_review_items']:,} scope items and "
        f"{review_queues['sensitivity']['source_records_for_review']:,} sensitivity candidates.",
        f"- Entities: {entities['aliases']:,} aliases and {entities['ambiguous_merge_proposals']:,} ambiguous merge proposals.",
        f"- Tasks: {tasks['current_candidates']:,} current candidates and "
        f"{tasks['historical_or_review_candidates']:,} historical/review candidates.",
        f"- Indexes: FTS {indexes['fts']['rows']:,} rows ({indexes['fts']['freshness']}); "
        f"relationships {indexes['relationships']['rows']:,} rows ({indexes['relationships']['freshness']}).",
        "",
        "## Coverage by source",
        "",
        "| Source | Files | Size | Earliest hint | Latest hint |",
        "|---|---:|---:|---|---|",
    ])
    for row in coverage:
        md.append(
            f"| {row['source_system']} | {row['files']:,} | {row['human_size']} | "
            f"{row['earliest_date_hint']} | {row['latest_date_hint']} |"
        )
    md.extend([
        "",
        "## Wispr Flow and Granola freshness",
        "",
        "| Provider | Items | Known retrieval dates | Latest retrieval | Freshness |",
        "|---|---:|---:|---|---|",
    ])
    for row in mcp_freshness:
        md.append(
            f"| {row['provider']} | {row['item_count']:,} | "
            f"{row['known_retrieval_dates']:,} | {row['latest_retrieval_date']} | "
            f"{row['freshness']} |"
        )
    md.extend(["", "## Gaps and unresolved items", ""])
    md.extend(f"- {item}" for item in needs or ["No mechanical gaps detected."])
    md.extend(["", "## Recommended next steps", ""])
    md.extend(f"{index}. {item}" for index, item in enumerate(next_steps, start=1))
    md.extend([
        "",
        "## Interpretation boundary",
        "",
        "This report establishes storage, format, date, transcript, and ingestion coverage. "
        "It does not establish that every historical note is current or every apparent "
        "accomplishment belongs on a résumé.",
        "",
    ])
    atomic_write_text(reports / "what_we_have_and_need.md", "\n".join(md))

    coverage_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['source_system']))}</td>"
        f"<td>{row['files']:,}</td>"
        f"<td>{html.escape(row['human_size'])}</td>"
        f"<td>{html.escape(str(row['earliest_date_hint']))}</td>"
        f"<td>{html.escape(str(row['latest_date_hint']))}</td>"
        "</tr>"
        for row in coverage
    )
    needs_html = "".join(f"<li>{html.escape(item)}</li>" for item in needs) or "<li>No mechanical gaps detected.</li>"
    steps_html = "".join(f"<li>{html.escape(item)}</li>" for item in next_steps)
    unsupported_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['source_system']))}</td>"
        f"<td>{html.escape(str(row['extension']))}</td>"
        f"<td>{html.escape(str(row['status']))}</td>"
        f"<td>{row['count']}</td>"
        f"<td>{html.escape(str(row['error']))}</td>"
        "</tr>"
        for row in unsupported[:200]
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Work Corpus Status</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.45; max-width: 1400px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; padding: 14px; }}
.card strong {{ font-size: 1.5rem; display: block; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 0.9rem; }}
th, td {{ border: 1px solid #ccc; padding: 7px; text-align: left; vertical-align: top; }}
th {{ background: #eee; }}
.notice {{ background: #f4f4f4; border-left: 5px solid #666; padding: 12px; }}
</style>
</head>
<body>
<h1>Work Corpus Status</h1>
<p>Generated {html.escape(summary['generated_at'])}</p>
<div class="cards">
<div class="card"><strong>{source_count:,}</strong>raw files<br>{html.escape(human_bytes(source_bytes))}</div>
<div class="card"><strong>{normalized:,}</strong>normalized documents</div>
<div class="card"><strong>{mcp_count:,}</strong>MCP items</div>
<div class="card"><strong>{zoom_total:,}</strong>Zoom folders</div>
<div class="card"><strong>{zoom_missing:,}</strong>Zoom transcripts missing</div>
<div class="card"><strong>{len(duplicates):,}</strong>exact duplicate groups</div>
<div class="card"><strong>{len(sensitive_review):,}</strong>sensitive-review candidates</div>
</div>

<h2>Coverage</h2>
<table>
<thead><tr><th>Source</th><th>Files</th><th>Size</th><th>Earliest hint</th><th>Latest hint</th></tr></thead>
<tbody>{coverage_rows}</tbody>
</table>

<h2>What is still needed</h2>
<ul>{needs_html}</ul>

<h2>Recommended next steps</h2>
<ol>{steps_html}</ol>

<h2>Unsupported formats and errors</h2>
<table>
<thead><tr><th>Source</th><th>Extension</th><th>Status</th><th>Count</th><th>Reason</th></tr></thead>
<tbody>{unsupported_rows}</tbody>
</table>

<h2>Acceptance detail</h2>
<pre>{html.escape(json.dumps(summary, indent=2, ensure_ascii=False, default=str))}</pre>

<div class="notice">
The raw archive remains authoritative. This report is a mechanical inventory, not a
determination that every item is current, accurate, externally safe, or résumé-worthy.
</div>
</body>
</html>
"""
    atomic_write_text(reports / "status.html", document)
    atomic_write_text(reports / "inventory.html", document)
    atomic_write_text(reports / "coverage_and_gaps.md", "\n".join(md))

    plan_lines = [
        "# Ingestion Plan",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Recommended sequence",
        "",
    ]
    for index, item in enumerate(next_steps, start=1):
        plan_lines.append(f"{index}. {item}")
    plan_lines.extend([
        "",
        "## Guardrails",
        "",
        "- Keep `data/` unchanged and append new raw capture batches.",
        "- Review sensitive candidates before broad model access.",
        "- Validate three Zoom transcripts before bulk transcription.",
        "- Backfill Granola/Wispr in bounded windows and persist raw responses.",
        "- Build current tasks only after historical evidence is separated from active commitments.",
        "",
    ])
    atomic_write_text(reports / "ingestion_plan.md", "\n".join(plan_lines))
    return summary
