from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .util import ensure_dir, stable_source_version_id


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


def _migrate_normalized_documents(con: sqlite3.Connection) -> None:
    columns = {
        row["name"]: row["pk"]
        for row in con.execute("PRAGMA table_info(normalized_document)")
    }
    if columns.get("source_version_id") == 1:
        return

    con.execute("ALTER TABLE normalized_document RENAME TO normalized_document_legacy")
    con.execute("DROP INDEX IF EXISTS idx_normalized_document_source_id")
    con.executescript(NORMALIZED_DOCUMENT_SCHEMA)
    con.execute(
        """
        INSERT INTO normalized_document (
            source_version_id, source_id, normalized_path, parser,
            source_mtime_ns, char_count, line_count, content_sha256,
            status, error, updated_at
        )
        SELECT s.source_version_id, n.source_id, n.normalized_path, n.parser,
               n.source_mtime_ns, n.char_count, n.line_count, n.content_sha256,
               n.status, n.error, n.updated_at
        FROM normalized_document_legacy n
        JOIN source_item s ON s.source_id=n.source_id
        WHERE s.source_version_id IS NOT NULL
        """
    )


def connect(path: Path) -> sqlite3.Connection:
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
    con.commit()
    return con
