from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from .util import ensure_dir


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
    date_hint TEXT,
    classification TEXT,
    sensitivity TEXT,
    parse_readiness TEXT,
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

CREATE TABLE IF NOT EXISTS normalized_document (
    source_id TEXT PRIMARY KEY REFERENCES source_item(source_id) ON DELETE CASCADE,
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
    }
    for column, sql_type in migrations.items():
        if column not in existing:
            con.execute(f"ALTER TABLE source_item ADD COLUMN {column} {sql_type}")
    con.commit()
    return con
