"""Local, deterministic organization passes for the work corpus.

The organization layer creates only source-backed derived records.  It never
rewrites a raw provider export, follows a signed URL, or guesses a canonical
identity from free text.  Ambiguous matches remain review items.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .config import Config
from .db import record_review_item
from .entities import add_alias, create_entity, resolve_mention
from .normalize import _task_date_basis
from .tasks import extract_task_proposals
from .util import (
    atomic_write_json,
    ensure_dir,
    now_iso,
    read_json,
    scrub_derived_text,
    stable_id,
    write_csv,
)


CAPACITIES_PAYLOAD_RELATIONSHIP = "capacities_payload"
CAPACITIES_PAYLOAD_REVIEW = "capacities_payload_match"
MIME_EXTENSIONS: Dict[str, Set[str]] = {
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/jpg": {".jpg", ".jpeg"},
    "application/pdf": {".pdf"},
    "text/plain": {".txt", ".md"},
    "text/markdown": {".md"},
    "message/rfc822": {".eml"},
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
        ".pptx"
    },
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
        ".docx"
    },
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        ".xlsx"
    },
}
PAYLOAD_PATH_MARKERS = ("/media/", "/mediafiles/")
POINTER_TYPES = {"file", "image", "pdf"}
POINTER_FIELDS = {"url", "media", "downloadurl", "signedurl"}


def _read_text(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read(64 * 1024)


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _value(value: str) -> Optional[str]:
    cleaned = str(value or "").strip().strip("'\"")
    if not cleaned or cleaned.casefold() in {"null", "none"}:
        return None
    return cleaned


def _document_metadata(path: Path) -> Dict[str, Optional[str]]:
    """Read simple front-matter fields without retaining the document body."""
    try:
        raw = _read_text(path)
    except (OSError, UnicodeError):
        return {}

    metadata: Dict[str, Optional[str]] = {}
    for line in raw.splitlines()[:80]:
        match = re.match(r"^\s*([A-Za-z][A-Za-z0-9_ -]*)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        metadata[_key(match.group(1))] = _value(match.group(2))
    return metadata


def _pointer_metadata(path: Path) -> Optional[Dict[str, Optional[str]]]:
    """Read only simple pointer metadata; do not retain the pointer URL."""
    metadata = _document_metadata(path)
    pointer_type = str(metadata.get("type") or metadata.get("kind") or "").casefold()
    if pointer_type not in POINTER_TYPES:
        return None
    if not any(field in metadata for field in POINTER_FIELDS):
        return None
    metadata["pointer_type"] = pointer_type
    return metadata


def _parse_size(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = re.fullmatch(r"\s*([0-9]+)(?:\.0+)?\s*", value)
    return int(match.group(1)) if match else None


def _normalised_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def _pointer_name_keys(path: Path, title: Optional[str]) -> Set[str]:
    names: Set[str] = set()
    raw_name = path.name
    variants = {
        raw_name,
        re.sub(r"\.(?:md|markdown)(?:\s+\(\d+\))?$", "", raw_name, flags=re.IGNORECASE),
        re.sub(r"\.(?:md|markdown)$", "", raw_name, flags=re.IGNORECASE),
    }
    variants.update(
        re.sub(r"\s+\(\d+\)$", "", variant).strip()
        for variant in tuple(variants)
    )
    if title:
        variants.add(title)
    for variant in variants:
        if variant:
            names.add(_normalised_name(variant))
    return {name for name in names if name}


def _payload_name_keys(relative_path: str) -> Set[str]:
    name = Path(relative_path).name
    stem = Path(name).stem
    variants = {name, stem, re.sub(r"\s+\(\d+\)$", "", stem)}
    return {_normalised_name(value) for value in variants if value}


def _payload_rows(con: sqlite3.Connection) -> List[sqlite3.Row]:
    return [
        row
        for row in con.execute(
            """
            SELECT source_id, source_version_id, relative_path, absolute_path,
                   extension, size_bytes, content_sha256
            FROM source_record
            WHERE status='present' AND source_system='capacities'
            ORDER BY relative_path, source_id
            """
        )
        if any(marker in f"/{str(row['relative_path']).casefold()}" for marker in PAYLOAD_PATH_MARKERS)
    ]


def _pointer_rows(con: sqlite3.Connection) -> List[Tuple[sqlite3.Row, Dict[str, Optional[str]], Path]]:
    output: List[Tuple[sqlite3.Row, Dict[str, Optional[str]], Path]] = []
    for row in con.execute(
        """
        SELECT source_id, source_version_id, relative_path, absolute_path,
               extension, size_bytes, content_sha256
        FROM source_record
        WHERE status='present' AND source_system='capacities'
        ORDER BY relative_path, source_id
        """
    ):
        path = Path(str(row["absolute_path"]))
        metadata = _pointer_metadata(path)
        if metadata is not None:
            output.append((row, metadata, path))
    return output


def _evidence_id(con: sqlite3.Connection, source_version_id: Optional[str]) -> Optional[str]:
    if not source_version_id:
        return None
    row = con.execute(
        """
        SELECT evidence_id
        FROM evidence_record
        WHERE source_version_id=?
        ORDER BY locator, evidence_id
        LIMIT 1
        """,
        (source_version_id,),
    ).fetchone()
    return str(row["evidence_id"]) if row else None


def _candidate_payloads(
    pointer_row: sqlite3.Row,
    metadata: Mapping[str, Optional[str]],
    payloads: Sequence[sqlite3.Row],
) -> Tuple[List[sqlite3.Row], Optional[str]]:
    size = _parse_size(metadata.get("filesize"))
    if size is None:
        return [], "pointer_missing_file_size"
    candidates = [row for row in payloads if int(row["size_bytes"] or -1) == size]
    if not candidates:
        return [], "no_local_payload_with_exact_size"

    name_keys = _pointer_name_keys(
        Path(str(pointer_row["relative_path"])), metadata.get("title")
    )
    named = [
        row
        for row in candidates
        if name_keys.intersection(_payload_name_keys(str(row["relative_path"])))
    ]
    if named:
        candidates = named

    mime = str(metadata.get("mimetype") or "").casefold().strip()
    allowed_extensions = MIME_EXTENSIONS.get(mime)
    if allowed_extensions:
        mime_candidates = [
            row
            for row in candidates
            if Path(str(row["relative_path"])).suffix.casefold() in allowed_extensions
        ]
        if not mime_candidates:
            return [], "local_payload_mime_mismatch"
        candidates = mime_candidates

    return candidates, None


def _link_payload(
    con: sqlite3.Connection,
    *,
    pointer_source_id: str,
    target_source_id: str,
    evidence_id: str,
) -> None:
    relationship_id = stable_id(
        "relationship",
        CAPACITIES_PAYLOAD_RELATIONSHIP,
        pointer_source_id,
        target_source_id,
    )
    con.execute(
        """
        INSERT INTO relationship (
            relationship_id, relationship_type, from_record_type, from_record_id,
            to_record_type, to_record_id, evidence_id, status, confidence, created_at
        ) VALUES (?, ?, 'source_record', ?, 'source_record', ?, ?, 'confirmed', 1.0, ?)
        ON CONFLICT(relationship_id) DO UPDATE SET
            evidence_id=excluded.evidence_id,
            status=excluded.status,
            confidence=excluded.confidence
        """,
        (
            relationship_id,
            CAPACITIES_PAYLOAD_RELATIONSHIP,
            pointer_source_id,
            target_source_id,
            evidence_id,
            now_iso(),
        ),
    )


def _write_capacity_reconciliation(
    config: Config,
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    state_path = config.state_dir / "capacities_payload_reconciliation.json"
    csv_path = config.corpus_dir / "reports" / "capacities_payload_matches.csv"
    config.assert_derived_path(state_path)
    config.assert_derived_path(csv_path)
    ensure_dir(config.state_dir)
    ensure_dir(csv_path.parent)
    atomic_write_json(
        state_path,
        {
            "schema_version": 1,
            "generated_at": now_iso(),
            **dict(summary),
            "records": list(records),
        },
    )
    write_csv(
        csv_path,
        records,
        [
            "pointer_source_id",
            "pointer_relative_path",
            "pointer_evidence_id",
            "match_status",
            "candidate_count",
            "target_source_ids",
            "target_relative_paths",
            "reason",
        ],
    )


def reconcile_capacities_payloads(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    """Match Capacities pointer records to local payload bytes by exact metadata."""
    payloads = _payload_rows(con)
    pointers = _pointer_rows(con)
    records: List[Dict[str, Any]] = []
    unresolved_reasons: Counter[str] = Counter()
    target_ids: Set[str] = set()
    pointer_ids: List[str] = []
    for pointer_row, metadata, _path in pointers:
        pointer_id = str(pointer_row["source_id"])
        pointer_ids.append(pointer_id)
        evidence_id = _evidence_id(con, pointer_row["source_version_id"])
        candidates, candidate_reason = _candidate_payloads(pointer_row, metadata, payloads)
        hashes = {str(row["content_sha256"]) for row in candidates if row["content_sha256"]}
        missing_hash = any(not row["content_sha256"] for row in candidates)
        target_rows: List[sqlite3.Row] = []
        reason = candidate_reason
        if candidates and missing_hash:
            reason = "candidate_missing_content_hash"
        elif candidates and len(hashes) != 1:
            reason = "multiple_local_payload_contents"
        elif candidates and evidence_id is None:
            reason = "pointer_missing_provenance"
        elif candidates:
            target_rows = list(candidates)

        if target_rows:
            con.execute(
                """
                UPDATE review_item
                SET status='resolved',
                    resolution=?,
                    updated_at=?
                WHERE issue_type=? AND source_id=? AND status='pending'
                """,
                (
                    "Superseded: the pointer now has normalized provenance and a confirmed local payload link.",
                    now_iso(),
                    CAPACITIES_PAYLOAD_REVIEW,
                    pointer_id,
                ),
            )
            for target in target_rows:
                _link_payload(
                    con,
                    pointer_source_id=pointer_id,
                    target_source_id=str(target["source_id"]),
                    evidence_id=evidence_id or "",
                )
                target_ids.add(str(target["source_id"]))
            match_status = (
                "matched_unique_content"
                if len(target_rows) == 1
                else "matched_duplicate_content"
            )
            record_reason = (
                "Exact file size, MIME-compatible extension, and one content hash "
                "matched; duplicate physical copies are retained."
            )
        else:
            match_status = "unresolved"
            record_reason = {
                "pointer_missing_file_size": "Pointer has no local file size; a payload cannot be identified safely.",
                "no_local_payload_with_exact_size": "No preserved local payload has the pointer's exact file size.",
                "local_payload_mime_mismatch": "Local files with the same size do not have a MIME-compatible extension.",
                "candidate_missing_content_hash": "A candidate exists but its immutable content hash is unavailable.",
                "multiple_local_payload_contents": "Multiple local candidates have different content hashes.",
                "pointer_missing_provenance": "A candidate exists but the pointer has no evidence record to anchor the link.",
                None: "The pointer could not be reconciled by the reviewed deterministic rules.",
            }.get(reason, "The pointer could not be reconciled by the reviewed deterministic rules.")
            unresolved_reasons[reason or "unresolved"] += 1
            proposed = {
                "action": "locate_local_payload",
                "pointer_source_id": pointer_id,
                "pointer_relative_path": str(pointer_row["relative_path"]),
                "pointer_evidence_id": evidence_id,
                "file_size_bytes": _parse_size(metadata.get("filesize")),
                "mime_type": metadata.get("mimetype"),
                "match_status": match_status,
            }
            record_review_item(
                con,
                issue_type=CAPACITIES_PAYLOAD_REVIEW,
                source_id=pointer_id,
                evidence_id=evidence_id,
                proposed_result=proposed,
                reason=record_reason,
                confidence=0.0,
                status="pending",
            )

        records.append(
            {
                "pointer_source_id": pointer_id,
                "pointer_relative_path": str(pointer_row["relative_path"]),
                "pointer_evidence_id": evidence_id or "",
                "match_status": match_status,
                "candidate_count": len(target_rows),
                "target_source_ids": json.dumps(
                    [str(row["source_id"]) for row in target_rows],
                    separators=(",", ":"),
                ),
                "target_relative_paths": json.dumps(
                    sorted(str(row["relative_path"]) for row in target_rows),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "reason": scrub_derived_text(record_reason if not target_rows else ""),
            }
        )

    relationship_count = 0
    if pointer_ids:
        placeholders = ",".join("?" for _value in pointer_ids)
        relationship_count = int(
            con.execute(
                f"SELECT COUNT(*) FROM relationship WHERE relationship_type=? "
                f"AND from_record_id IN ({placeholders})",
                [CAPACITIES_PAYLOAD_RELATIONSHIP, *pointer_ids],
            ).fetchone()[0]
        )
    summary = {
        "pointer_count": len(pointers),
        "matched_pointer_count": sum(
            record["match_status"].startswith("matched_") for record in records
        ),
        "unresolved_pointer_count": sum(
            record["match_status"] == "unresolved" for record in records
        ),
        "unresolved_by_reason": dict(sorted(unresolved_reasons.items())),
        "payload_source_record_count": len(payloads),
        "target_payload_record_count": len(target_ids),
        "relationship_count": relationship_count,
        "signed_urls_fetched": 0,
    }
    con.commit()
    _write_capacity_reconciliation(config, records, summary)
    return summary


def _version_family_key(relative_path: str) -> str:
    path = Path(relative_path)
    stem = path.stem.casefold()
    stem = re.sub(
        r"(?<![a-z])20\d{2}[-_. ]?\d{0,2}[-_. ]?\d{0,2}(?![a-z])",
        " ",
        stem,
    )
    stem = re.sub(
        r"\b(?:final|draft|copy|revised|updated|new|old|latest|clean|redline|edit|edited)\b",
        " ",
        stem,
    )
    stem = re.sub(r"\b(?:v|ver|version|rev|revision)[-_. ]?\d+(?:[._-]\d+)*\b", " ", stem)
    stem = re.sub(r"\(\d+\)$", " ", stem)
    stem = re.sub(r"[-_. ]+", " ", stem).strip()
    return stem + path.suffix.casefold() if len(stem) >= 5 else ""


def _review_evidence_id(con: sqlite3.Connection, source_id: Optional[str]) -> Optional[str]:
    if not source_id:
        return None
    row = con.execute(
        """
        SELECT e.evidence_id
        FROM evidence_record e
        JOIN source_version v ON v.source_version_id=e.source_version_id
        WHERE v.source_id=?
        ORDER BY e.locator, e.evidence_id
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()
    return str(row["evidence_id"]) if row else None


def _record_duplicate_reviews(con: sqlite3.Connection) -> int:
    groups: Dict[str, List[sqlite3.Row]] = defaultdict(list)
    for row in con.execute(
        """
        SELECT source_id, relative_path, duplicate_group_id, content_sha256, size_bytes
        FROM source_record
        WHERE status='present' AND duplicate_group_id IS NOT NULL
        ORDER BY duplicate_group_id, relative_path, source_id
        """
    ):
        groups[str(row["duplicate_group_id"])].append(row)
    for group_id, rows in groups.items():
        record_review_item(
            con,
            issue_type="duplicate_group_review",
            proposed_result={
                "action": "keep_physical_records_until_review",
                "duplicate_group_id": group_id,
                "content_sha256": rows[0]["content_sha256"],
                "source_ids": [str(row["source_id"]) for row in rows],
                "relative_paths": [str(row["relative_path"]) for row in rows],
            },
            reason="Exact content duplicates were grouped by hash; no source record was deleted or merged.",
            confidence=1.0,
            status="pending",
        )
    return len(groups)


def _record_version_reviews(con: sqlite3.Connection) -> int:
    groups: Dict[Tuple[str, str], List[sqlite3.Row]] = defaultdict(list)
    for row in con.execute(
        """
        SELECT source_id, source_system, relative_path
        FROM source_record
        WHERE status='present'
        ORDER BY source_system, relative_path, source_id
        """
    ):
        key = _version_family_key(str(row["relative_path"]))
        if key:
            groups[(str(row["source_system"]), key)].append(row)
    family_count = 0
    for (source_system, family_key), rows in sorted(groups.items()):
        if len(rows) < 2:
            continue
        family_count += 1
        record_review_item(
            con,
            issue_type="version_family_review",
            proposed_result={
                "action": "retain_versions_until_review",
                "source_system": source_system,
                "family_key": family_key,
                "source_ids": [str(row["source_id"]) for row in rows],
                "relative_paths": [str(row["relative_path"]) for row in rows],
            },
            reason="Filename heuristics suggest a version family; records remain separate until reviewed.",
            confidence=0.0,
            status="pending",
        )
    return family_count


def _record_sensitivity_reviews(con: sqlite3.Connection) -> Tuple[int, int]:
    rows = con.execute(
        """
        SELECT source_id, relative_path, source_system, classification, sensitivity,
               parse_readiness, career_value, operations_value
        FROM source_record
        WHERE status='present'
          AND (
              classification IN ('potential_personal', 'mixed_or_review', 'Personal', 'Mixed', 'Unknown')
              OR sensitivity='potential_restricted'
          )
        ORDER BY source_id
        """
    ).fetchall()
    resolved_stale = 0
    for row in rows:
        source_id = str(row["source_id"])
        evidence_id = _review_evidence_id(con, source_id)
        if evidence_id:
            stale = con.execute(
                """
                UPDATE review_item
                SET status='resolved',
                    resolution='Superseded: normalized evidence is now available.',
                    updated_at=?
                WHERE issue_type='sensitivity_review'
                  AND source_id=?
                  AND status='pending'
                  AND evidence_id IS NULL
                """,
                (now_iso(), source_id),
            ).rowcount
            resolved_stale += int(stale)
        record_review_item(
            con,
            issue_type="sensitivity_review",
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result={
                "action": "review_scope_and_sensitivity",
                "source_id": str(row["source_id"]),
                "relative_path": str(row["relative_path"]),
                "classification": row["classification"],
                "sensitivity": row["sensitivity"],
            },
            reason="Path and source rules flagged this record; content-level release or privacy judgment was not automated.",
            confidence=0.0,
            status="pending",
        )
    return len(rows), resolved_stale


def _record_wispr_date_reviews(con: sqlite3.Connection) -> int:
    rows = con.execute(
        """
        SELECT item_id, source_id, external_record_id, capture_date, event_date,
               retrieval_date, normalized_evidence_id
        FROM mcp_item
        WHERE lower(provider)='wispr_flow'
          AND (retrieval_date IS NULL OR trim(retrieval_date)='')
        ORDER BY item_id
        """
    ).fetchall()
    for row in rows:
        record_review_item(
            con,
            issue_type="wispr_date_review",
            source_id=str(row["source_id"]),
            evidence_id=row["normalized_evidence_id"] or _review_evidence_id(
                con, str(row["source_id"])
            ),
            proposed_result={
                "action": "preserve_unknown_retrieval_date",
                "item_id": str(row["item_id"]),
                "external_record_id": row["external_record_id"],
                "capture_date_present": bool(row["capture_date"]),
                "event_date_present": bool(row["event_date"]),
            },
            reason="The saved Wispr Flow response has no usable retrieval date; no capture or event date was promoted to freshness.",
            confidence=0.0,
            status="pending",
        )
    return len(rows)


def _record_meeting_reviews(con: sqlite3.Connection) -> int:
    rows = con.execute(
        """
        SELECT group_id, folder_relative_path, meeting_date, status,
               media_source_id, transcript_source_id, transcript_version_id,
               media_version_id
        FROM meeting_group
        WHERE status='needs_review'
        ORDER BY group_id
        """
    ).fetchall()
    for row in rows:
        source_id = row["transcript_source_id"] or row["media_source_id"]
        evidence_id = _evidence_id(con, row["transcript_version_id"])
        if evidence_id is None:
            evidence_id = _evidence_id(con, row["media_version_id"])
        record_review_item(
            con,
            issue_type="meeting_link_review",
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result={
                "action": "review_meeting_group_links",
                "group_id": str(row["group_id"]),
                "folder_relative_path": str(row["folder_relative_path"]),
                "meeting_date": row["meeting_date"],
                "media_source_id": row["media_source_id"],
                "transcript_source_id": row["transcript_source_id"],
            },
            reason="Meeting grouping or transcript linkage remains marked needs_review; no link was forced.",
            confidence=0.0,
            status="pending",
        )
    return len(rows)


def _record_zoom_quality_reviews(con: sqlite3.Connection) -> int:
    rows = con.execute(
        """
        SELECT job_id, group_id, media_source_id, media_version_id,
               status, quality_status, output_sha256
        FROM transcription_job
        WHERE status='partial' OR quality_status='partial'
        ORDER BY job_id
        """
    ).fetchall()
    for row in rows:
        record_review_item(
            con,
            issue_type="zoom_quality_review",
            source_id=row["media_source_id"],
            evidence_id=_evidence_id(con, row["media_version_id"]),
            proposed_result={
                "action": "inspect_partial_transcript_quality",
                "job_id": str(row["job_id"]),
                "group_id": str(row["group_id"]),
                "media_source_id": row["media_source_id"],
                "output_sha256": row["output_sha256"],
                "status": row["status"],
                "quality_status": row["quality_status"],
            },
            reason="The local transcription completed with a quality-limited partial result; no retranscription was started automatically.",
            confidence=0.0,
            status="pending",
        )
    return len(rows)


def _reconcile_malformed_reviews(config: Config, con: sqlite3.Connection) -> int:
    state = read_json(config.state_dir / "granola_acceptance.json", {})
    runs = state.get("repeat_import_runs") if isinstance(state, Mapping) else None
    clean_repeats = bool(
        isinstance(runs, list)
        and runs
        and all(
            isinstance(run, Mapping)
            and int(run.get("malformed", 1) if run.get("malformed") is not None else 1) == 0
            and int(run.get("errors", 1) if run.get("errors") is not None else 1) == 0
            for run in runs
        )
    )
    if not clean_repeats:
        return 0
    resolved = 0
    for row in con.execute(
        """
        SELECT r.review_id, s.source_id, s.source_version_id
        FROM review_item r
        JOIN source_record s ON s.source_id=r.source_id
        WHERE r.issue_type='mcp_malformed_item'
          AND r.status='pending'
          AND s.status='present'
          AND s.source_version_id IS NOT NULL
        """
    ).fetchall():
        con.execute(
            """
            UPDATE review_item
            SET status='resolved',
                resolution='Superseded: two later repeat imports completed with zero malformed records and zero errors; the source now has an immutable version.',
                updated_at=?
            WHERE review_id=? AND status='pending'
            """,
            (now_iso(), row["review_id"]),
        )
        resolved += 1
    return resolved


def _project_and_candidate_reviews(con: sqlite3.Connection) -> Tuple[int, int, int]:
    project_rows: Dict[str, List[Tuple[sqlite3.Row, str, str]]] = defaultdict(list)
    candidate_count = 0
    for row in con.execute(
        """
        SELECT source_id, source_version_id, relative_path, absolute_path, root_key
        FROM source_record
        WHERE status='present' AND source_system='capacities'
        ORDER BY relative_path, source_id
        """
    ):
        path = str(row["relative_path"]).replace("\\", "/")
        metadata = _document_metadata(Path(str(row["absolute_path"])))
        kind = str(metadata.get("type") or metadata.get("kind") or "").casefold()
        title = str(metadata.get("title") or "").strip()
        evidence_id = _evidence_id(con, row["source_version_id"])
        if re.search(r"(?:^|/)projects/", path.casefold()) and kind == "project" and title:
            name_key = _normalised_name(title)
            if name_key and name_key not in {"untitled", "project", "new project"}:
                project_rows[name_key].append((row, title, evidence_id or ""))
            else:
                record_review_item(
                    con,
                    issue_type="entity_candidate_review",
                    source_id=str(row["source_id"]),
                    evidence_id=evidence_id,
                    proposed_result={
                        "action": "review_structured_project_candidate",
                        "candidate_type": "project",
                        "candidate_name": scrub_derived_text(title),
                    },
                    reason="The source marks this as a Project, but its generic title is not safe as a canonical identity.",
                    confidence=0.0,
                    status="pending",
                )
                candidate_count += 1
            continue
        if re.search(r"(?:^|/)pages/", path.casefold()) and kind == "page" and title:
            record_review_item(
                con,
                issue_type="entity_candidate_review",
                source_id=str(row["source_id"]),
                evidence_id=evidence_id,
                proposed_result={
                    "action": "review_structured_page_entity_candidate",
                    "candidate_type": "unknown",
                    "candidate_name": scrub_derived_text(title),
                },
                reason="A Capacities Page title alone does not establish a person, project, or organization identity.",
                confidence=0.0,
                status="pending",
            )
            candidate_count += 1

    project_count = 0
    project_source_links = 0
    for name_key, rows in sorted(project_rows.items()):
        primary = sorted(
            rows,
            key=lambda item: (
                0 if str(item[0]["root_key"]) == "capacities_markdown" else 1,
                str(item[0]["relative_path"]),
                str(item[0]["source_id"]),
            ),
        )[0]
        entity_id = create_entity(
            con,
            "project",
            f"capacities:{name_key}",
            primary[1],
            confidence=1.0,
        )
        project_count += 1
        distinct_titles = sorted({title for _row, title, _evidence in rows})
        for title in distinct_titles:
            matching = next(
                (evidence for _row, candidate_title, evidence in rows if candidate_title == title and evidence),
                None,
            )
            add_alias(
                con,
                entity_id,
                title,
                source_system="capacities",
                evidence_id=matching,
                rule="structured_project_type",
                confidence=1.0,
                review_status="valid",
            )
        for row, title, evidence_id in rows:
            if not evidence_id:
                continue
            resolve_mention(
                con,
                title,
                evidence_id=evidence_id,
                source_id=str(row["source_id"]),
                location="frontmatter:title",
                source_system="capacities",
                context={"structured_type": "Project"},
            )
            project_source_links += 1
    return project_count, project_source_links, candidate_count


def _run_task_proposals(con: sqlite3.Connection, run_date: date) -> int:
    proposal_count = 0
    for row in con.execute(
        """
        SELECT f.evidence_id, f.derived_text, e.source_version_id,
               v.source_id, s.date_hint, s.classification, s.scope, s.metadata_json
        FROM derived_text_fts f
        JOIN evidence_record e ON e.evidence_id=f.evidence_id
        JOIN source_version v ON v.source_version_id=e.source_version_id
        JOIN source_record s ON s.source_id=v.source_id
        WHERE s.status='present'
        ORDER BY f.evidence_id
        """
    ):
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            metadata = {}
        source_basis = str(
            metadata.get("source_date_basis")
            or ("filename_hint" if row["date_hint"] else "not_observed")
        )
        proposals = extract_task_proposals(
            con,
            str(row["derived_text"] or ""),
            source_id=str(row["source_id"]),
            source_evidence_id=str(row["evidence_id"]),
            source_event_date=row["date_hint"],
            source_date_basis=_task_date_basis(source_basis),
            run_date=run_date,
            scope=str(row["classification"] or row["scope"] or "Unknown"),
            commit=False,
        )
        proposal_count += len(proposals)
    con.commit()
    return proposal_count


WORK_ATTEMPTED: Dict[str, str] = {
    "capacities_payload_match": "Compared pointer metadata with local payload size, MIME extension, filename, and immutable hash.",
    "scope_review": "Applied deterministic source and path scope rules; did not promote non-Work evidence.",
    "sensitivity_review": "Applied deterministic path/source sensitivity rules; did not make a content release decision.",
    "duplicate_group_review": "Grouped exact content hashes; retained every physical record.",
    "version_family_review": "Applied conservative filename-family heuristics; retained every version.",
    "task_date_review": "Extracted explicit task language; did not promote missing or historical dates to current work.",
    "task_scope_review": "Extracted explicit task language; did not promote unresolved scope.",
    "entity_candidate_review": "Reviewed structured Capacities metadata; promoted only explicit non-generic Project records.",
    "wispr_date_review": "Inspected persisted Wispr Flow date fields; preserved unknown retrieval dates.",
    "meeting_link_review": "Retained Zoom meeting groups marked needs_review; did not force transcript links.",
    "zoom_quality_review": "Retained the terminal partial transcription result; did not retranscribe automatically.",
    "mcp_malformed_item": "Compared the old review row with later clean repeat-import results.",
}
HUMAN_DECISION: Dict[str, str] = {
    "capacities_payload_match": "Provide a local payload or explicitly approve a new reviewed export/fetch.",
    "scope_review": "Confirm Work, Personal, Mixed, or Unknown for the source.",
    "sensitivity_review": "Confirm whether the source may enter the intended downstream view.",
    "duplicate_group_review": "Choose a canonical display record, if any; keep the rest as provenance.",
    "version_family_review": "Identify current versus historical version without deleting source files.",
    "task_date_review": "Confirm an event date or leave the proposal historical/unresolved.",
    "task_scope_review": "Confirm Work scope before surfacing a task.",
    "entity_candidate_review": "Confirm the entity type and canonical name or leave it unresolved.",
    "wispr_date_review": "Supply provider-backed retrieval timing or accept unknown freshness.",
    "meeting_link_review": "Confirm the correct transcript/media association.",
    "zoom_quality_review": "Accept the partial transcript or authorize a new local quality pass.",
    "mcp_malformed_item": "No action unless the preserved malformed record still needs inspection.",
}


def _write_residual_ledger(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    for row in con.execute(
        """
        SELECT r.review_id, r.issue_type, r.source_id, r.evidence_id, r.reason,
               s.relative_path, e.locator
        FROM review_item r
        LEFT JOIN source_record s ON s.source_id=r.source_id
        LEFT JOIN evidence_record e ON e.evidence_id=r.evidence_id
        WHERE r.status='pending'
        ORDER BY r.issue_type, COALESCE(s.relative_path, ''), r.review_id
        """
    ):
        issue_type = str(row["issue_type"])
        entries.append(
            {
                "review_id": str(row["review_id"]),
                "issue_type": issue_type,
                "source_id": row["source_id"] or "",
                "evidence_id": row["evidence_id"] or "",
                "relative_path": row["relative_path"] or "",
                "locator": row["locator"] or "",
                "reason": scrub_derived_text(str(row["reason"] or "")),
                "work_attempted": WORK_ATTEMPTED.get(
                    issue_type, "Recorded the existing provenance-backed review proposal."
                ),
                "smallest_human_decision": HUMAN_DECISION.get(
                    issue_type, "Resolve or leave the item pending with its source provenance."
                ),
            }
        )
    by_issue = Counter(entry["issue_type"] for entry in entries)
    state = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "pending_count": len(entries),
        "pending_by_issue_type": dict(sorted(by_issue.items())),
        "entries": entries,
    }
    state_path = config.state_dir / "residual_ledger.json"
    csv_path = config.corpus_dir / "reports" / "residual_ledger.csv"
    config.assert_derived_path(state_path)
    config.assert_derived_path(csv_path)
    ensure_dir(config.state_dir)
    ensure_dir(csv_path.parent)
    atomic_write_json(state_path, state)
    write_csv(
        csv_path,
        entries,
        [
            "review_id",
            "issue_type",
            "source_id",
            "evidence_id",
            "relative_path",
            "locator",
            "reason",
            "work_attempted",
            "smallest_human_decision",
        ],
    )
    return {
        "pending_count": len(entries),
        "pending_by_issue_type": dict(sorted(by_issue.items())),
        "state_path": str(state_path),
        "report_path": str(csv_path),
    }


def _review_counts(con: sqlite3.Connection) -> Dict[str, Dict[str, int]]:
    counts: Dict[str, Dict[str, int]] = defaultdict(dict)
    for row in con.execute(
        "SELECT issue_type, status, COUNT(*) AS count FROM review_item "
        "GROUP BY issue_type, status ORDER BY issue_type, status"
    ):
        counts[str(row["issue_type"])][str(row["status"])] = int(row["count"])
    return {key: dict(value) for key, value in sorted(counts.items())}


def organize_all(
    config: Config,
    con: sqlite3.Connection,
    *,
    run_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Run the complete deterministic organization pass."""
    effective_date = run_date or date.today()
    capacities = reconcile_capacities_payloads(config, con)
    resolved_malformed = _reconcile_malformed_reviews(config, con)
    duplicate_groups = _record_duplicate_reviews(con)
    version_families = _record_version_reviews(con)
    sensitivity_candidates, resolved_sensitivity = _record_sensitivity_reviews(con)
    wispr_date_candidates = _record_wispr_date_reviews(con)
    meeting_candidates = _record_meeting_reviews(con)
    zoom_quality_candidates = _record_zoom_quality_reviews(con)
    project_count, project_source_links, candidate_reviews = _project_and_candidate_reviews(con)
    task_proposals_scanned = _run_task_proposals(con, effective_date)
    con.commit()

    entity_counts = {
        str(row["entity_type"]): int(row["count"])
        for row in con.execute(
            "SELECT entity_type, COUNT(*) AS count FROM entity GROUP BY entity_type"
        )
    }
    from .db import current_tasks

    residual = _write_residual_ledger(config, con)
    state = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "run_date": effective_date.isoformat(),
        "capacities": capacities,
        "review_pass": {
            "resolved_stale_mcp_malformed": resolved_malformed,
            "resolved_stale_sensitivity": resolved_sensitivity,
            "duplicate_groups_seen": duplicate_groups,
            "version_families_seen": version_families,
            "sensitivity_candidates_seen": sensitivity_candidates,
            "wispr_unknown_date_candidates_seen": wispr_date_candidates,
            "meeting_link_candidates_seen": meeting_candidates,
            "zoom_quality_candidates_seen": zoom_quality_candidates,
        },
        "entity_counts": {
            "project": entity_counts.get("project", 0),
            "person": entity_counts.get("person", 0),
            "organization": entity_counts.get("organization", 0),
        },
        "project_sources_linked": project_source_links,
        "candidate_review_items": candidate_reviews,
        "task_proposals_scanned": task_proposals_scanned,
        "task_rows": int(con.execute("SELECT COUNT(*) FROM task").fetchone()[0]),
        "current_task_rows": len(current_tasks(con, effective_date)),
        "review_counts": _review_counts(con),
        "residual_ledger": residual,
        "raw_boundary": {
            "raw_data_modified": False,
            "signed_urls_fetched": 0,
        },
    }
    state_path = config.state_dir / "organization_acceptance.json"
    config.assert_derived_path(state_path)
    ensure_dir(config.state_dir)
    atomic_write_json(state_path, state)
    return {
        "capacities": capacities,
        "resolved_stale_mcp_malformed": resolved_malformed,
        "resolved_stale_sensitivity": resolved_sensitivity,
        "duplicate_groups_seen": duplicate_groups,
        "version_families_seen": version_families,
        "sensitivity_candidates_seen": sensitivity_candidates,
        "wispr_unknown_date_candidates_seen": wispr_date_candidates,
        "meeting_link_candidates_seen": meeting_candidates,
        "zoom_quality_candidates_seen": zoom_quality_candidates,
        "entities_created": project_count,
        "project_sources_linked": project_source_links,
        "candidate_review_items": candidate_reviews,
        "task_proposals_scanned": task_proposals_scanned,
        "task_rows": state["task_rows"],
        "current_task_rows": state["current_task_rows"],
        "review_counts": state["review_counts"],
        "residual_ledger": residual,
        "state_path": str(state_path),
    }
