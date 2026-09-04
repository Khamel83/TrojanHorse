from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .util import ensure_dir, now_iso, stable_source_version_id


SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS source_item (
    source_id TEXT PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    absolute_path TEXT NOT NULL,
    source_system TEXT NOT NULL,
    kind TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    content_sha256 TEXT,
    source_version_id TEXT,
    date_hint TEXT,
    classification TEXT,
    sensitivity TEXT,
    parse_readiness TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'inventory_only',
    career_value TEXT,
    operations_value TEXT,
    duplicate_group_id TEXT,
    status TEXT NOT NULL DEFAULT 'present',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_system ON source_item(source_system);
CREATE INDEX IF NOT EXISTS idx_source_kind ON source_item(kind);
CREATE INDEX IF NOT EXISTS idx_source_status ON source_item(status);

CREATE TABLE IF NOT EXISTS source_version (
    source_version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(source_id, content_sha256)
);

CREATE INDEX IF NOT EXISTS idx_source_version_source_id
ON source_version(source_id);

CREATE TABLE IF NOT EXISTS normalized_document (
    source_version_id TEXT PRIMARY KEY
        REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    normalized_path TEXT,
    parser TEXT,
    source_mtime_ns INTEGER,
    char_count INTEGER,
    line_count INTEGER,
    content_sha256 TEXT,
    status TEXT NOT NULL,
    error TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_normalized_document_source_id
ON normalized_document(source_id);

CREATE TABLE IF NOT EXISTS zoom_group (
    group_id TEXT PRIMARY KEY,
    folder_relative_path TEXT NOT NULL UNIQUE,
    media_source_id TEXT REFERENCES source_item(source_id),
    transcript_source_id TEXT REFERENCES source_item(source_id),
    transcript_path TEXT,
    status TEXT NOT NULL,
    duration_seconds REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcription_job (
    job_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES zoom_group(group_id) ON DELETE CASCADE,
    media_source_id TEXT NOT NULL REFERENCES source_item(source_id),
    output_stem TEXT NOT NULL,
    engine TEXT,
    model TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_transcription_status ON transcription_job(status);

CREATE TABLE IF NOT EXISTS email_message (
    email_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_record_key TEXT,
    message_id TEXT,
    conversation_id TEXT,
    in_reply_to TEXT,
    references_json TEXT,
    canonical_subject TEXT,
    subject TEXT,
    sender TEXT,
    to_json TEXT,
    cc_json TEXT,
    sent_at TEXT,
    received_at TEXT,
    folder TEXT,
    body_path TEXT,
    attachments_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_email_conversation ON email_message(conversation_id);
CREATE INDEX IF NOT EXISTS idx_email_subject ON email_message(canonical_subject);
CREATE INDEX IF NOT EXISTS idx_email_received ON email_message(received_at);

CREATE TABLE IF NOT EXISTS mcp_item (
    item_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT,
    title TEXT,
    event_date TEXT,
    normalized_path TEXT,
    source_uri TEXT,
    fetched_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_provider_date ON mcp_item(provider, event_date);

CREATE TABLE IF NOT EXISTS project (
    project_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    status TEXT,
    start_date TEXT,
    end_date TEXT,
    summary TEXT,
    confidence TEXT,
    source_ids_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task (
    task_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    project_id TEXT REFERENCES project(project_id),
    owner TEXT,
    assigner TEXT,
    source_date TEXT,
    due_date TEXT,
    status TEXT,
    blocker TEXT,
    waiting_on TEXT,
    completion_evidence TEXT,
    source_ids_json TEXT,
    confidence TEXT,
    last_reviewed_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision (
    decision_id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES project(project_id),
    decision_date TEXT,
    decision_text TEXT NOT NULL,
    decision_maker TEXT,
    rationale TEXT,
    consequences TEXT,
    source_ids_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS career_claim (
    claim_id TEXT PRIMARY KEY,
    employer TEXT,
    date_range TEXT,
    project_id TEXT REFERENCES project(project_id),
    ownership_level TEXT,
    internal_wording TEXT,
    external_safe_wording TEXT,
    metrics_json TEXT,
    outcome TEXT,
    evidence_strength TEXT,
    confidentiality TEXT,
    source_ids_json TEXT,
    conflict_notes TEXT,
    updated_at TEXT NOT NULL
);
"""


NORMALIZED_DOCUMENT_SCHEMA = r"""
CREATE TABLE normalized_document (
    source_version_id TEXT PRIMARY KEY
        REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    normalized_path TEXT,
    parser TEXT,
    source_mtime_ns INTEGER,
    char_count INTEGER,
    line_count INTEGER,
    content_sha256 TEXT,
    status TEXT NOT NULL,
    error TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_normalized_document_source_id
ON normalized_document(source_id);
"""


def mark_noncurrent_normalized_documents_retained(
    con: sqlite3.Connection,
    updated_at: str,
    skip_classifications: Optional[Iterable[str]] = None,
) -> int:
    """Keep prior output bytes while removing them from the active result set."""
    if skip_classifications is None:
        skip_values = {
            "personal",
            "mixed",
            "unknown",
            "potential_personal",
            "mixed_or_review",
        }
    else:
        skip_values = {
            str(value).casefold()
            for value in skip_classifications
            if str(value).strip()
        }
    if skip_values:
        placeholders = ", ".join("?" for _ in sorted(skip_values))
        classification_guard = (
            f"AND LOWER(COALESCE(s.classification, 'Unknown')) "
            f"NOT IN ({placeholders})"
        )
        parameters = (updated_at, *sorted(skip_values))
    else:
        classification_guard = ""
        parameters = (updated_at,)

    cursor = con.execute(
        f"""
        UPDATE normalized_document
        SET status='prior_good_retained',
            error='Prior good output retained; source version is no longer current and eligible',
            updated_at=?
        WHERE status='normalized'
          AND NOT EXISTS (
              SELECT 1
              FROM source_item s
              JOIN source_version v
                ON v.source_version_id=s.source_version_id
               AND v.source_id=s.source_id
               AND v.content_sha256=s.content_sha256
              WHERE s.source_id=normalized_document.source_id
                AND s.source_version_id=normalized_document.source_version_id
                AND s.status='present'
                AND s.extraction_status='ready'
                AND s.content_sha256 IS NOT NULL
                AND s.content_sha256<>''
                AND s.source_version_id IS NOT NULL
                AND s.source_version_id<>''
                AND s.kind NOT IN (
                    'media', 'email', 'email_data', 'mcp', 'unknown'
                )
                {classification_guard}
          )
        """,
        parameters,
    )
    return max(cursor.rowcount, 0)


def _backfill_source_versions(con: sqlite3.Connection) -> None:
    rows = con.execute(
        """
        SELECT source_id, content_sha256, size_bytes, mtime_ns,
               first_seen, last_seen, metadata_json, extraction_status
        FROM source_item
        """
    ).fetchall()
    for row in rows:
        metadata = {}
        if row["metadata_json"]:
            try:
                import json

                metadata = json.loads(row["metadata_json"])
            except (TypeError, ValueError):
                metadata = {}
        metadata_status = metadata.get("extraction_status")
        extraction_status = (
            metadata_status
            if isinstance(metadata_status, str) and metadata_status
            else row["extraction_status"] or "inventory_only"
        )
        source_version_id = stable_source_version_id(
            row["source_id"],
            row["content_sha256"] or "",
        )
        con.execute(
            """
            UPDATE source_item
            SET source_version_id=?, extraction_status=?
            WHERE source_id=?
            """,
            (source_version_id, extraction_status, row["source_id"]),
        )
        if source_version_id is None:
            continue
        con.execute(
            """
            INSERT INTO source_version (
                source_version_id, source_id, content_sha256, size_bytes,
                mtime_ns, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_version_id) DO UPDATE SET
                size_bytes=excluded.size_bytes,
                mtime_ns=excluded.mtime_ns,
                last_seen=excluded.last_seen
            """,
            (
                source_version_id,
                row["source_id"],
                row["content_sha256"],
                row["size_bytes"],
                row["mtime_ns"],
                row["first_seen"],
                row["last_seen"],
            ),
        )


def _migrate_legacy_normalized_rows(con: sqlite3.Connection) -> None:
    """Migrate only provably identical legacy rows and retain conflicts."""
    table = con.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name='normalized_document_legacy'
        """
    ).fetchone()
    if table is None:
        return

    columns = {
        row["name"]
        for row in con.execute("PRAGMA table_info(normalized_document_legacy)")
    }
    required = {
        "source_id",
        "normalized_path",
        "parser",
        "source_mtime_ns",
        "char_count",
        "line_count",
        "content_sha256",
        "status",
        "error",
        "updated_at",
    }
    if required <= columns:
        comparison_fields = (
            "source_id",
            "normalized_path",
            "parser",
            "source_mtime_ns",
            "char_count",
            "line_count",
            "content_sha256",
            "status",
            "error",
            "updated_at",
        )
        for legacy in con.execute(
            "SELECT * FROM normalized_document_legacy"
        ).fetchall():
            source = con.execute(
                "SELECT source_version_id FROM source_item WHERE source_id=?",
                (legacy["source_id"],),
            ).fetchone()
            if source is None or not source["source_version_id"]:
                # Without a source version there is no safe current-document key.
                continue

            source_version_id = source["source_version_id"]
            current = con.execute(
                "SELECT * FROM normalized_document WHERE source_version_id=?",
                (source_version_id,),
            ).fetchone()
            if current is None:
                con.execute(
                    """
                    INSERT INTO normalized_document (
                        source_version_id, source_id, normalized_path, parser,
                        source_mtime_ns, char_count, line_count, content_sha256,
                        status, error, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_version_id,
                        *(legacy[field] for field in comparison_fields),
                    ),
                )
                con.execute(
                    "DELETE FROM normalized_document_legacy WHERE source_id=?",
                    (legacy["source_id"],),
                )
                continue

            if all(current[field] == legacy[field] for field in comparison_fields):
                con.execute(
                    "DELETE FROM normalized_document_legacy WHERE source_id=?",
                    (legacy["source_id"],),
                )
            # A differing row is intentionally retained for manual reconciliation.

    remaining = con.execute(
        "SELECT 1 FROM normalized_document_legacy LIMIT 1"
    ).fetchone()
    if remaining is None:
        con.execute("DROP TABLE normalized_document_legacy")


def _migrate_normalized_documents(con: sqlite3.Connection) -> None:
    columns = {
        row["name"]: row["pk"]
        for row in con.execute("PRAGMA table_info(normalized_document)")
    }
    if columns.get("source_version_id") == 1:
        _migrate_legacy_normalized_rows(con)
        return

    con.execute("ALTER TABLE normalized_document RENAME TO normalized_document_legacy")
    con.execute("DROP INDEX IF EXISTS idx_normalized_document_source_id")
    con.executescript(NORMALIZED_DOCUMENT_SCHEMA)
    _migrate_legacy_normalized_rows(con)


def connect(
    path: Path,
    *,
    skip_classifications: Optional[Iterable[str]] = None,
) -> sqlite3.Connection:
    ensure_dir(path.parent)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)

    # Lightweight forward migration for an earlier bootstrap database.
    existing = {row[1] for row in con.execute("PRAGMA table_info(source_item)")}
    migrations = {
        "classification": "TEXT",
        "sensitivity": "TEXT",
        "parse_readiness": "TEXT",
        "career_value": "TEXT",
        "operations_value": "TEXT",
        "duplicate_group_id": "TEXT",
        "source_version_id": "TEXT",
        "extraction_status": "TEXT NOT NULL DEFAULT 'inventory_only'",
    }
    for column, sql_type in migrations.items():
        if column not in existing:
            con.execute(f"ALTER TABLE source_item ADD COLUMN {column} {sql_type}")
    _backfill_source_versions(con)
    _migrate_normalized_documents(con)
    # Reconcile legacy output before exposing the migrated connection. Legacy
    # rows did not have the canonical scope and extraction eligibility fields.
    mark_noncurrent_normalized_documents_retained(
        con,
        now_iso(),
        skip_classifications=skip_classifications,
    )
    con.commit()
    return con
