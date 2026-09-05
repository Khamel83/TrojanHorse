"""Local Wispr Flow and Granola snapshot intake.

The adapter reads only reviewed files already present below ``data/``. It
does not connect to an MCP server, call a provider, or upload source text.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .config import Config
from .db import record_evidence, record_review_item
from .util import (
    atomic_write_text,
    now_iso,
    provenance_header,
    read_text_guess,
    scrub_derived_text,
    sha256_text,
    stable_id,
    write_csv,
)


SUPPORTED_PROVIDERS = frozenset({"granola", "wispr_flow"})
PARSER_NAME = "mcp_snapshot"
PARSER_VERSION = "1"


@dataclass(frozen=True)
class SnapshotRecord:
    index: int
    payload: Mapping[str, Any]
    original_response: str
    line_number: Optional[int] = None


@dataclass(frozen=True)
class MalformedRecord:
    index: int
    reason: str
    line_number: Optional[int] = None


def _first(obj: Mapping[str, Any], names: Iterable[str], default: Any = "") -> Any:
    for name in names:
        if name in obj and obj[name] not in (None, ""):
            return obj[name]
    return default


def _date_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    text = str(value).strip()
    if not text:
        return None
    try:
        from datetime import datetime

        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except ValueError:
        # Preserve a provider value that is not an ISO date rather than
        # silently turning a source fact into an empty field.
        return text[:200]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _content_from_obj(obj: Mapping[str, Any]) -> str:
    value = _first(
        obj,
        (
            "transcript",
            "text",
            "content",
            "notes",
            "summary",
            "description",
            "body",
            "raw_text",
        ),
        "",
    )
    if isinstance(value, str):
        return value
    if value not in (None, ""):
        return _canonical_json(value)
    return _canonical_json(dict(obj))


def _records_from_snapshot(path: Path) -> Tuple[List[SnapshotRecord], List[MalformedRecord]]:
    extension = path.suffix.casefold()
    if extension in {".md", ".markdown", ".txt"}:
        text = read_text_guess(path)
        return [SnapshotRecord(0, {"title": path.stem, "content": text}, text)], []

    text = read_text_guess(path)
    records: List[SnapshotRecord] = []
    malformed: List[MalformedRecord] = []
    if extension == ".jsonl":
        for index, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                malformed.append(MalformedRecord(index, f"invalid JSONL: {exc}", index + 1))
                continue
            if not isinstance(payload, dict):
                malformed.append(MalformedRecord(index, "JSONL record is not an object", index + 1))
                continue
            records.append(SnapshotRecord(index, payload, _canonical_json(payload), index + 1))
        return records, malformed

    if extension == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], [MalformedRecord(0, f"invalid JSON: {exc}")]
        if isinstance(payload, list):
            candidates: Sequence[Any] = payload
        elif isinstance(payload, dict):
            candidates = []
            for key in ("meetings", "notes", "items", "results", "data", "value"):
                value = payload.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
            if not candidates:
                candidates = [payload]
        else:
            return [], [MalformedRecord(0, "JSON snapshot is neither an object nor an array")]
        for index, item in enumerate(candidates):
            if not isinstance(item, dict):
                malformed.append(MalformedRecord(index, "snapshot record is not an object"))
                continue
            records.append(SnapshotRecord(index, item, _canonical_json(item)))
        return records, malformed

    return [], [MalformedRecord(0, f"unsupported snapshot extension: {extension or '[none]'}")]


def _record_fields(record: SnapshotRecord) -> Dict[str, Optional[str]]:
    obj = record.payload
    external_id = _first(
        obj,
        ("external_record_id", "external_id", "id", "meeting_id", "note_id", "uuid"),
        "",
    )
    title = _first(obj, ("title", "name", "topic", "meeting_title"), "")
    return {
        "external_record_id": str(external_id).strip() or None,
        "title": str(title).strip() or "Snapshot item",
        "content": _content_from_obj(obj),
        "capture_date": _date_text(
            _first(obj, ("capture_date", "captured_at", "recorded_at", "created_at"), "")
        ),
        "event_date": _date_text(
            _first(obj, ("event_date", "meeting_date", "date", "start_time", "event_at"), "")
        ),
        "retrieval_date": _date_text(
            _first(obj, ("retrieval_date", "retrieved_at", "ingested_at", "fetched_at"), "")
        ),
    }


def _checkpoint_id(provider: str, root_key: str) -> str:
    return stable_id("mcp-checkpoint", provider, root_key)


def _item_id(
    provider: str,
    external_record_id: Optional[str],
    source_version_id: str,
    index: int,
    response_sha256: str,
) -> str:
    if external_record_id:
        return stable_id("mcp-item", provider, external_record_id)
    return stable_id("mcp-item", provider, source_version_id, index, response_sha256)


def _record_review(
    con: sqlite3.Connection,
    *,
    source_id: str,
    provider: str,
    relative_path: str,
    malformed: MalformedRecord,
) -> str:
    return record_review_item(
        con,
        issue_type="mcp_malformed_item",
        proposed_result={
            "provider": provider,
            "relative_path": relative_path,
            "record_index": malformed.index,
            "line_number": malformed.line_number,
            "action": "retain_for_review",
        },
        source_id=source_id,
        reason=malformed.reason,
        confidence=0.0,
        status="pending",
    )


def _ensure_checkpoint(
    con: sqlite3.Connection,
    *,
    checkpoint_id: str,
    provider: str,
    root_key: Optional[str],
) -> None:
    con.execute(
        """
        INSERT INTO ingestion_checkpoint (
            checkpoint_id, provider, root_key, cursor, source_version_id,
            last_successful_retrieval, item_count, error, updated_at
        ) VALUES (?, ?, ?, NULL, NULL, NULL, 0, NULL, ?)
        ON CONFLICT(checkpoint_id) DO UPDATE SET
            provider=excluded.provider,
            root_key=excluded.root_key,
            updated_at=excluded.updated_at
        """,
        (checkpoint_id, provider, root_key, now_iso()),
    )


def _advance_checkpoint(
    con: sqlite3.Connection,
    *,
    checkpoint_id: str,
    cursor: str,
    source_version_id: str,
    item_count: int,
) -> None:
    con.execute(
        """
        UPDATE ingestion_checkpoint
        SET cursor=?, source_version_id=?, item_count=?,
            last_successful_retrieval=?, error=NULL, updated_at=?
        WHERE checkpoint_id=?
        """,
        (cursor, source_version_id, item_count, now_iso(), now_iso(), checkpoint_id),
    )


def _normalized_output(
    config: Config,
    *,
    provider: str,
    item_id: str,
    source_version_id: str,
) -> Path:
    output = config.corpus_dir / "mcp" / provider / source_version_id / f"{item_id}.md"
    config.assert_derived_path(output)
    return output


def _persist_record(
    config: Config,
    con: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    provider: str,
    checkpoint_id: str,
    record: SnapshotRecord,
) -> Tuple[str, str]:
    source_version_id = str(row["source_version_id"] or "")
    if not source_version_id:
        raise ValueError("source snapshot has no source version")
    fields = _record_fields(record)
    response_sha256 = hashlib.sha256(record.original_response.encode("utf-8")).hexdigest()
    item_id = _item_id(
        provider,
        fields["external_record_id"],
        source_version_id,
        record.index,
        response_sha256,
    )
    locator = f"mcp:item:{item_id}"
    output = _normalized_output(
        config,
        provider=provider,
        item_id=item_id,
        source_version_id=source_version_id,
    )
    source_date = fields["event_date"] or fields["capture_date"]
    date_basis = "event_date" if fields["event_date"] else (
        "capture_date" if fields["capture_date"] else "not_observed"
    )
    header = provenance_header(
        {
            "source_id": row["source_id"],
            "source_version_id": source_version_id,
            "source_system": provider,
            "original_path": row["absolute_path"],
            "relative_path": row["relative_path"],
            "original_date": source_date or "",
            "source_date_basis": date_basis,
            "file_type": "mcp_item",
            "parser": PARSER_NAME,
            "parser_version": PARSER_VERSION,
            "locator": locator,
            "generated_at": now_iso(),
        }
    )
    body = "\n".join(
        [
            header.rstrip(),
            f"# {fields['title']}",
            "",
            f"- Provider: {provider}",
            f"- External record ID: {fields['external_record_id'] or ''}",
            f"- Capture date: {fields['capture_date'] or ''}",
            f"- Event date: {fields['event_date'] or ''}",
            f"- Retrieval date: {fields['retrieval_date'] or ''}",
            "",
            "## Content",
            "",
            scrub_derived_text(str(fields["content"] or "")).strip(),
            "",
        ]
    )
    atomic_write_text(output, body)
    evidence_id = record_evidence(
        con,
        source_version_id=source_version_id,
        locator=locator,
        derived_text_path=str(output),
        text_sha256=sha256_text(body),
        evidence_status="derived",
        derived_text=body,
        document_id=item_id,
    )
    con.execute(
        """
        INSERT INTO mcp_item (
            item_id, source_id, provider, external_record_id, capture_date,
            event_date, retrieval_date, original_response_sha256,
            normalized_evidence_id, checkpoint_id, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_id) DO UPDATE SET
            source_id=excluded.source_id,
            provider=excluded.provider,
            external_record_id=excluded.external_record_id,
            capture_date=excluded.capture_date,
            event_date=excluded.event_date,
            retrieval_date=excluded.retrieval_date,
            original_response_sha256=excluded.original_response_sha256,
            normalized_evidence_id=excluded.normalized_evidence_id,
            checkpoint_id=excluded.checkpoint_id,
            updated_at=excluded.updated_at
        """,
        (
            item_id,
            row["source_id"],
            provider,
            fields["external_record_id"],
            fields["capture_date"],
            fields["event_date"],
            fields["retrieval_date"],
            response_sha256,
            evidence_id,
            checkpoint_id,
            now_iso(),
        ),
    )
    return item_id, evidence_id


def _source_rows(con: sqlite3.Connection) -> List[sqlite3.Row]:
    placeholders = ",".join("?" for _value in SUPPORTED_PROVIDERS)
    return con.execute(
        f"""
        SELECT * FROM source_record
        WHERE status='present'
          AND source_system IN ({placeholders})
          AND lower(extension) IN ('.json', '.jsonl', '.md', '.markdown', '.txt')
        ORDER BY source_system, relative_path
        """,
        sorted(SUPPORTED_PROVIDERS),
    ).fetchall()


def _write_index(config: Config, con: sqlite3.Connection) -> None:
    rows = [
        dict(row)
        for row in con.execute(
            """
            SELECT item_id, source_id, provider, external_record_id,
                   capture_date, event_date, retrieval_date,
                   original_response_sha256, normalized_evidence_id,
                   checkpoint_id, updated_at
            FROM mcp_item
            ORDER BY provider, item_id
            """
        )
    ]
    path = config.corpus_dir / "reports" / "mcp_index.csv"
    config.assert_derived_path(path)
    write_csv(
        path,
        rows,
        [
            "item_id",
            "source_id",
            "provider",
            "external_record_id",
            "capture_date",
            "event_date",
            "retrieval_date",
            "original_response_sha256",
            "normalized_evidence_id",
            "checkpoint_id",
            "updated_at",
        ],
    )


def ingest_mcp_sources(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    """Import configured local snapshots and return accounting-only counts."""
    result: Dict[str, Any] = {
        "items": 0,
        "updated_items": 0,
        "source_files": 0,
        "malformed": 0,
        "errors": 0,
        "checkpoints": 0,
    }
    errors: List[str] = []

    for row in _source_rows(con):
        provider = str(row["source_system"])
        checkpoint_id = _checkpoint_id(provider, str(row["root_key"] or ""))
        _ensure_checkpoint(
            con,
            checkpoint_id=checkpoint_id,
            provider=provider,
            root_key=row["root_key"],
        )
        if not row["source_version_id"]:
            malformed = MalformedRecord(
                0,
                "snapshot source has no immutable source version",
            )
            _record_review(
                con,
                source_id=str(row["source_id"]),
                provider=provider,
                relative_path=str(row["relative_path"]),
                malformed=malformed,
            )
            result["malformed"] += 1
            result["errors"] += 1
            errors.append(f"{row['relative_path']}: {malformed.reason}")
            result["source_files"] += 1
            continue
        path = Path(str(row["absolute_path"]))
        try:
            records, malformed = _records_from_snapshot(path)
        except Exception as exc:
            malformed = [MalformedRecord(0, f"snapshot read failed: {type(exc).__name__}: {exc}")]
            records = []
        for item in malformed:
            _record_review(
                con,
                source_id=str(row["source_id"]),
                provider=provider,
                relative_path=str(row["relative_path"]),
                malformed=item,
            )
            result["malformed"] += 1
            errors.append(f"{row['relative_path']} record {item.index}: {item.reason}")

        processed = 0
        for record in records:
            try:
                before = con.execute(
                    "SELECT 1 FROM mcp_item WHERE item_id=?",
                    (
                        _item_id(
                            provider,
                            _record_fields(record)["external_record_id"],
                            str(row["source_version_id"]),
                            record.index,
                            hashlib.sha256(record.original_response.encode("utf-8")).hexdigest(),
                        ),
                    ),
                ).fetchone()
                _persist_record(
                    config,
                    con,
                    row=row,
                    provider=provider,
                    checkpoint_id=checkpoint_id,
                    record=record,
                )
                processed += 1
                result["updated_items"] += int(before is not None)
                result["items"] += 1
            except Exception as exc:
                reason = f"snapshot record failed: {type(exc).__name__}: {exc}"
                _record_review(
                    con,
                    source_id=str(row["source_id"]),
                    provider=provider,
                    relative_path=str(row["relative_path"]),
                    malformed=MalformedRecord(record.index, reason, record.line_number),
                )
                result["errors"] += 1
                errors.append(f"{row['relative_path']} record {record.index}: {reason}")

        if records:
            last = records[-1]
            unique_count = con.execute(
                "SELECT COUNT(*) FROM mcp_item WHERE checkpoint_id=?",
                (checkpoint_id,),
            ).fetchone()[0]
            _advance_checkpoint(
                con,
                checkpoint_id=checkpoint_id,
                cursor=f"{row['relative_path']}:{last.index}",
                source_version_id=str(row["source_version_id"]),
                item_count=int(unique_count),
            )
        result["source_files"] += 1

    con.commit()
    result["checkpoints"] = con.execute(
        "SELECT COUNT(*) FROM ingestion_checkpoint WHERE provider IN ('granola', 'wispr_flow')"
    ).fetchone()[0]
    _write_index(config, con)
    error_path = config.state_dir / "mcp_ingest_errors.txt"
    config.assert_derived_path(error_path)
    atomic_write_text(error_path, "\n".join(errors) + ("\n" if errors else ""))
    return result
