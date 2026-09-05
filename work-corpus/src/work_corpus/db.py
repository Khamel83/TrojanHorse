from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List, Optional, Union

from .util import (
    ensure_dir,
    now_iso,
    scrub_fts_text,
    stable_evidence_id,
    stable_source_id,
    stable_source_version_id,
)


SCHEMA_VERSION = 2


SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    schema_version INTEGER PRIMARY KEY,
    migrated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    run_id TEXT PRIMARY KEY,
    command TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    safe_diagnostics_json TEXT,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS source_root (
    root_key TEXT PRIMARY KEY,
    relative_path TEXT NOT NULL UNIQUE,
    source_system TEXT NOT NULL,
    precedence INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_record (
    source_id TEXT PRIMARY KEY,
    root_key TEXT REFERENCES source_root(root_key) ON DELETE RESTRICT,
    relative_path TEXT NOT NULL UNIQUE,
    absolute_path TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL,
    kind TEXT NOT NULL,
    scope TEXT,
    sensitivity TEXT,
    status TEXT NOT NULL DEFAULT 'present',
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extension TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    content_sha256 TEXT,
    source_version_id TEXT,
    date_hint TEXT,
    classification TEXT,
    parse_readiness TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'inventory_only',
    career_value TEXT,
    operations_value TEXT,
    duplicate_group_id TEXT,
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_record_source_system
ON source_record(source_system);
CREATE INDEX IF NOT EXISTS idx_source_record_scope ON source_record(scope);
CREATE INDEX IF NOT EXISTS idx_source_record_status ON source_record(status);
CREATE INDEX IF NOT EXISTS idx_source_record_kind ON source_record(kind);

CREATE TABLE IF NOT EXISTS source_version (
    source_version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_record(source_id) ON DELETE RESTRICT,
    content_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    observed_dates TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, content_sha256)
);

CREATE INDEX IF NOT EXISTS idx_source_version_source_id
ON source_version(source_id);

CREATE TABLE IF NOT EXISTS normalized_document (
    source_version_id TEXT PRIMARY KEY
        REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    derived_path TEXT,
    normalized_path TEXT,
    parser TEXT,
    parser_version TEXT,
    source_mtime_ns INTEGER,
    char_count INTEGER,
    line_count INTEGER,
    content_sha256 TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_normalized_document_source_id
ON normalized_document(source_id);

CREATE TABLE IF NOT EXISTS date_observation (
    observation_id TEXT PRIMARY KEY,
    evidence_id TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    source_version_id TEXT REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    date_value TEXT NOT NULL,
    basis TEXT NOT NULL,
    precision TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (evidence_id IS NOT NULL OR source_version_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_date_observation_value_basis
ON date_observation(date_value, basis);

CREATE TABLE IF NOT EXISTS meeting_group (
    group_id TEXT PRIMARY KEY,
    folder_relative_path TEXT NOT NULL UNIQUE,
    meeting_date TEXT,
    media_source_id TEXT REFERENCES source_record(source_id),
    media_version_id TEXT REFERENCES source_version(source_version_id),
    transcript_source_id TEXT REFERENCES source_record(source_id),
    transcript_version_id TEXT REFERENCES source_version(source_version_id),
    transcript_path TEXT,
    status TEXT NOT NULL,
    duration_seconds REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transcription_job (
    job_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL REFERENCES meeting_group(group_id) ON DELETE CASCADE,
    media_source_id TEXT REFERENCES source_record(source_id),
    media_version_id TEXT REFERENCES source_version(source_version_id),
    approval_status TEXT NOT NULL DEFAULT 'pending_approval',
    output_stem TEXT NOT NULL DEFAULT '',
    engine TEXT,
    model TEXT,
    local_engine TEXT,
    local_model TEXT,
    status TEXT NOT NULL,
    language TEXT,
    timestamp_coverage REAL,
    speaker_label_status TEXT,
    quality_status TEXT,
    output_path TEXT,
    output_sha256 TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_transcription_status ON transcription_job(status);

CREATE TABLE IF NOT EXISTS evidence_record (
    evidence_id TEXT PRIMARY KEY,
    source_version_id TEXT NOT NULL REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    locator TEXT NOT NULL,
    derived_text_path TEXT,
    text_sha256 TEXT,
    evidence_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_version_id, locator)
);

CREATE INDEX IF NOT EXISTS idx_evidence_record_source_version
ON evidence_record(source_version_id);

CREATE VIRTUAL TABLE IF NOT EXISTS derived_text_fts USING fts5(
    document_id UNINDEXED,
    evidence_id UNINDEXED,
    derived_text
);

CREATE TABLE IF NOT EXISTS entity (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('project', 'person', 'organization')),
    canonical_name TEXT NOT NULL,
    status TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_alias (
    alias_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entity(entity_id) ON DELETE RESTRICT,
    evidence_id TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    alias TEXT NOT NULL,
    source_system TEXT,
    valid_from TEXT,
    valid_to TEXT,
    rule TEXT,
    confidence REAL,
    review_status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_id, alias, source_system, valid_from, valid_to)
);

CREATE INDEX IF NOT EXISTS idx_entity_alias_alias ON entity_alias(alias);

CREATE TABLE IF NOT EXISTS entity_mention (
    mention_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    entity_id TEXT REFERENCES entity(entity_id) ON DELETE RESTRICT,
    original_mention TEXT NOT NULL,
    location TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    rule TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document (
    document_id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL,
    event_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_evidence_id ON document(evidence_id);
CREATE INDEX IF NOT EXISTS idx_document_event_date ON document(event_date);

CREATE TABLE IF NOT EXISTS task (
    task_id TEXT PRIMARY KEY,
    action TEXT NOT NULL,
    owner_entity_id TEXT REFERENCES entity(entity_id) ON DELETE RESTRICT,
    assigner_entity_id TEXT REFERENCES entity(entity_id) ON DELETE RESTRICT,
    project_entity_id TEXT REFERENCES entity(entity_id) ON DELETE RESTRICT,
    source_event_date TEXT,
    event_date TEXT,
    due_date TEXT,
    candidate_status TEXT NOT NULL DEFAULT 'candidate',
    task_status TEXT NOT NULL DEFAULT 'open',
    source_evidence_id TEXT NOT NULL REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    source_date_basis TEXT,
    owner TEXT,
    assigner TEXT,
    project_id TEXT,
    source_date TEXT,
    status TEXT,
    blocker TEXT,
    waiting_on TEXT,
    completion_evidence TEXT,
    source_ids_json TEXT,
    confidence TEXT,
    last_reviewed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_source_event_date ON task(source_event_date);
CREATE INDEX IF NOT EXISTS idx_task_candidate_status ON task(candidate_status);
CREATE INDEX IF NOT EXISTS idx_task_source_date_basis ON task(source_date_basis);

CREATE TABLE IF NOT EXISTS relationship (
    relationship_id TEXT PRIMARY KEY,
    relationship_type TEXT NOT NULL,
    from_record_type TEXT NOT NULL,
    from_record_id TEXT NOT NULL,
    to_record_type TEXT NOT NULL,
    to_record_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    status TEXT NOT NULL,
    confidence REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_relationship_from
ON relationship(from_record_type, from_record_id);
CREATE INDEX IF NOT EXISTS idx_relationship_to
ON relationship(to_record_type, to_record_id);

CREATE TABLE IF NOT EXISTS review_item (
    review_id TEXT PRIMARY KEY,
    issue_type TEXT NOT NULL,
    source_id TEXT REFERENCES source_record(source_id) ON DELETE RESTRICT,
    evidence_id TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    proposal_hash TEXT NOT NULL,
    proposed_result_json TEXT NOT NULL,
    reason TEXT,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_type, source_id, evidence_id, proposal_hash)
);

CREATE INDEX IF NOT EXISTS idx_review_item_status ON review_item(status);

CREATE TABLE IF NOT EXISTS ingestion_checkpoint (
    checkpoint_id TEXT PRIMARY KEY,
    provider TEXT,
    root_key TEXT REFERENCES source_root(root_key) ON DELETE RESTRICT,
    cursor TEXT,
    source_version_id TEXT REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    last_successful_retrieval TEXT,
    item_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_item (
    item_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_record(source_id) ON DELETE RESTRICT,
    provider TEXT NOT NULL,
    external_record_id TEXT,
    capture_date TEXT,
    event_date TEXT,
    retrieval_date TEXT,
    original_response_sha256 TEXT,
    normalized_evidence_id TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
    checkpoint_id TEXT REFERENCES ingestion_checkpoint(checkpoint_id) ON DELETE RESTRICT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mcp_provider_date ON mcp_item(provider, event_date);
"""


NORMALIZED_DOCUMENT_SCHEMA = r"""
CREATE TABLE normalized_document (
    source_version_id TEXT PRIMARY KEY
        REFERENCES source_version(source_version_id) ON DELETE RESTRICT,
    source_id TEXT NOT NULL,
    derived_path TEXT,
    normalized_path TEXT,
    parser TEXT,
    parser_version TEXT,
    source_mtime_ns INTEGER,
    char_count INTEGER,
    line_count INTEGER,
    content_sha256 TEXT,
    status TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
              FROM source_record s
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
        FROM source_record
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
            UPDATE source_record
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
                "SELECT source_version_id FROM source_record WHERE source_id=?",
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


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone() is not None


def _has_foreign_key(
    con: sqlite3.Connection,
    table: str,
    from_column: str,
    target_table: str,
    target_column: str = "",
) -> bool:
    """Return whether a table has the FK needed by the provenance model."""
    for row in con.execute(f'PRAGMA foreign_key_list("{table}")'):
        if row[3] != from_column or row[2] != target_table:
            continue
        if target_column and row[4] != target_column:
            continue
        return True
    return False


SOURCE_RECORD_MIGRATION_SCHEMA = r"""
CREATE TABLE source_record__migration_new (
    source_id TEXT PRIMARY KEY,
    root_key TEXT REFERENCES source_root(root_key) ON DELETE RESTRICT,
    relative_path TEXT NOT NULL UNIQUE,
    absolute_path TEXT NOT NULL DEFAULT '',
    source_system TEXT NOT NULL,
    kind TEXT NOT NULL,
    scope TEXT,
    sensitivity TEXT,
    status TEXT NOT NULL DEFAULT 'present',
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extension TEXT NOT NULL DEFAULT '',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    mtime_ns INTEGER NOT NULL DEFAULT 0,
    content_sha256 TEXT,
    source_version_id TEXT,
    date_hint TEXT,
    classification TEXT,
    parse_readiness TEXT,
    extraction_status TEXT NOT NULL DEFAULT 'inventory_only',
    career_value TEXT,
    operations_value TEXT,
    duplicate_group_id TEXT,
    metadata_json TEXT
);
"""

SOURCE_VERSION_MIGRATION_SCHEMA = r"""
CREATE TABLE source_version__migration_new (
    source_version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source_record(source_id) ON DELETE RESTRICT,
    content_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    observed_dates TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, content_sha256)
);
"""


def _migrate_source_foreign_keys(con: sqlite3.Connection) -> None:
    """Rebuild legacy source tables so provenance links are enforceable.

    SQLite cannot add a foreign key with ALTER TABLE. The rebuild copies all
    recognized columns, rejects orphan versions before any old table is
    dropped, and runs inside the caller's transaction. Unknown legacy columns
    remain intentionally untouched only when the legacy table is not rebuilt;
    the source facts represented by the current model are copied losslessly.
    """
    source_needs_rebuild = not _has_foreign_key(
        con, "source_record", "root_key", "source_root", "root_key"
    )
    version_needs_rebuild = not _has_foreign_key(
        con, "source_version", "source_id", "source_record", "source_id"
    )
    if not source_needs_rebuild and not version_needs_rebuild:
        return

    orphan = con.execute(
        """
        SELECT v.source_version_id, v.source_id
        FROM source_version v
        LEFT JOIN source_record s ON s.source_id=v.source_id
        WHERE s.source_id IS NULL
        LIMIT 1
        """
    ).fetchone()
    if orphan is not None:
        raise RuntimeError(
            "legacy source_version row has no source_record parent "
            f"({orphan['source_version_id']}); database preserved, "
            "run an explicit reviewed migration"
        )

    invalid_root = con.execute(
        """
        SELECT s.source_id, s.root_key
        FROM source_record s
        LEFT JOIN source_root r ON r.root_key=s.root_key
        WHERE s.root_key IS NOT NULL AND r.root_key IS NULL
        LIMIT 1
        """
    ).fetchone()
    if invalid_root is not None:
        raise RuntimeError(
            "legacy source_record row references an unknown source_root "
            f"({invalid_root['root_key']}); database preserved, "
            "run an explicit reviewed migration"
        )

    if source_needs_rebuild:
        if _table_exists(con, "source_record__migration_new"):
            raise RuntimeError(
                "source_record migration table already exists; database preserved, "
                "run an explicit reviewed migration"
            )
        con.executescript(SOURCE_RECORD_MIGRATION_SCHEMA)
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(source_record)")
        }
        source_fields = (
            "source_id", "root_key", "relative_path", "absolute_path",
            "source_system", "kind", "scope", "sensitivity", "status",
            "first_seen", "last_seen", "extension", "size_bytes", "mtime_ns",
            "content_sha256", "source_version_id", "date_hint", "classification",
            "parse_readiness", "extraction_status", "career_value",
            "operations_value", "duplicate_group_id", "metadata_json",
        )
        destination = ", ".join(source_fields)
        placeholders = ", ".join("?" for _ in source_fields)
        rows = con.execute("SELECT * FROM source_record").fetchall()
        for row in rows:
            values = [row[field] if field in columns else None for field in source_fields]
            if values[6] is None and values[17] is not None:
                values[6] = values[17]
            con.execute(
                f"INSERT INTO source_record__migration_new ({destination}) "
                f"VALUES ({placeholders})",
                values,
            )
        con.execute("DROP TABLE source_record")
        con.execute(
            "ALTER TABLE source_record__migration_new RENAME TO source_record"
        )
        con.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_source_record_source_system
            ON source_record(source_system);
            CREATE INDEX IF NOT EXISTS idx_source_record_scope
            ON source_record(scope);
            CREATE INDEX IF NOT EXISTS idx_source_record_status
            ON source_record(status);
            CREATE INDEX IF NOT EXISTS idx_source_record_kind
            ON source_record(kind);
            """
        )

    if version_needs_rebuild:
        if _table_exists(con, "source_version__migration_new"):
            raise RuntimeError(
                "source_version migration table already exists; database preserved, "
                "run an explicit reviewed migration"
            )
        con.executescript(SOURCE_VERSION_MIGRATION_SCHEMA)
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(source_version)")
        }
        version_fields = (
            "source_version_id", "source_id", "content_sha256", "size_bytes",
            "mtime_ns", "observed_dates", "created_at", "first_seen", "last_seen",
        )
        destination = ", ".join(version_fields)
        placeholders = ", ".join("?" for _ in version_fields)
        rows = con.execute("SELECT * FROM source_version").fetchall()
        for row in rows:
            values = [row[field] if field in columns else None for field in version_fields]
            if values[6] is None:
                values[6] = values[7] or now_iso()
            con.execute(
                f"INSERT INTO source_version__migration_new ({destination}) "
                f"VALUES ({placeholders})",
                values,
            )
        con.execute("DROP TABLE source_version")
        con.execute(
            "ALTER TABLE source_version__migration_new RENAME TO source_version"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_source_version_source_id "
            "ON source_version(source_id)"
        )


def _reject_orphaned_legacy_versions(con: sqlite3.Connection) -> None:
    """Reject orphan source versions before any legacy table rename occurs."""
    if not _table_exists(con, "source_version"):
        return
    source_table = (
        "source_record" if _table_exists(con, "source_record") else "source_item"
    )
    if not _table_exists(con, source_table):
        raise RuntimeError(
            "legacy source_version table has no source parent; database preserved, "
            "run an explicit reviewed migration"
        )
    orphan = con.execute(
        f"""
        SELECT v.source_version_id
        FROM source_version v
        LEFT JOIN "{source_table}" s ON s.source_id=v.source_id
        WHERE s.source_id IS NULL
        LIMIT 1
        """
    ).fetchone()
    if orphan is not None:
        raise RuntimeError(
            "legacy source_version row has no source parent "
            f"({orphan['source_version_id']}); database preserved, "
            "run an explicit reviewed migration"
        )


def _rename_bootstrap_tables(con: sqlite3.Connection) -> None:
    """Move bootstrap names forward without deleting data."""
    for old_name, new_name in (
        ("source_item", "source_record"),
        ("zoom_group", "meeting_group"),
    ):
        old_exists = _table_exists(con, old_name)
        new_exists = _table_exists(con, new_name)
        if old_exists and new_exists:
            raise RuntimeError(
                f"schema migration cannot reconcile both {old_name!r} and "
                f"{new_name!r}; preserve the database and migrate it manually"
            )
        if old_exists:
            con.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}"')


def _add_columns(
    con: sqlite3.Connection,
    table: str,
    columns: dict[str, str],
) -> None:
    if not _table_exists(con, table):
        return
    existing = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}
    for column, sql_type in columns.items():
        if column not in existing:
            con.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sql_type}')


def _migrate_columns(con: sqlite3.Connection) -> None:
    _add_columns(
        con,
        "source_record",
        {
            "root_key": "TEXT",
            "scope": "TEXT",
            "classification": "TEXT",
            "sensitivity": "TEXT",
            "parse_readiness": "TEXT",
            "career_value": "TEXT",
            "operations_value": "TEXT",
            "duplicate_group_id": "TEXT",
            "source_version_id": "TEXT",
            "extraction_status": "TEXT NOT NULL DEFAULT 'inventory_only'",
        },
    )
    _add_columns(
        con,
        "source_version",
        {
            "observed_dates": "TEXT",
            "created_at": "TEXT",
        },
    )
    _add_columns(
        con,
        "normalized_document",
        {
            "derived_path": "TEXT",
            "parser_version": "TEXT",
            "created_at": "TEXT",
        },
    )
    _add_columns(
        con,
        "meeting_group",
        {
            "meeting_date": "TEXT",
            "media_version_id": "TEXT",
            "transcript_version_id": "TEXT",
        },
    )
    _add_columns(
        con,
        "transcription_job",
        {
            "media_version_id": "TEXT",
            "approval_status": "TEXT NOT NULL DEFAULT 'pending_approval'",
            "local_engine": "TEXT",
            "local_model": "TEXT",
            "language": "TEXT",
            "timestamp_coverage": "REAL",
            "speaker_label_status": "TEXT",
            "quality_status": "TEXT",
            "output_path": "TEXT",
            "output_sha256": "TEXT",
        },
    )
    _add_columns(
        con,
        "task",
        {
            "owner_entity_id": "TEXT",
            "assigner_entity_id": "TEXT",
            "project_entity_id": "TEXT",
            "source_event_date": "TEXT",
            "event_date": "TEXT",
            "candidate_status": "TEXT NOT NULL DEFAULT 'candidate'",
            "task_status": "TEXT NOT NULL DEFAULT 'open'",
            "source_evidence_id": "TEXT",
            "source_date_basis": "TEXT",
            "created_at": "TEXT",
        },
    )
    _add_columns(
        con,
        "entity_alias",
        {
            "evidence_id": "TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT",
        },
    )
    _add_columns(
        con,
        "entity_mention",
        {
            "rule": "TEXT",
        },
    )
    _add_columns(
        con,
        "mcp_item",
        {
            "external_record_id": "TEXT",
            "capture_date": "TEXT",
            "retrieval_date": "TEXT",
            "original_response_sha256": "TEXT",
            "normalized_evidence_id": "TEXT",
            "checkpoint_id": "TEXT",
        },
    )


def _migrate_mcp_items(con: sqlite3.Connection) -> None:
    """Rebuild the MCP table without the bootstrap-only columns."""
    if not _table_exists(con, "mcp_item"):
        return
    columns = {
        row[1] for row in con.execute('PRAGMA table_info("mcp_item")')
    }
    canonical = {
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
    }
    transitional = columns - canonical
    if not transitional:
        return

    con.execute("DROP TABLE IF EXISTS mcp_item__migration_new")
    con.execute(
        """
        CREATE TABLE mcp_item__migration_new (
            item_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES source_record(source_id) ON DELETE RESTRICT,
            provider TEXT NOT NULL,
            external_record_id TEXT,
            capture_date TEXT,
            event_date TEXT,
            retrieval_date TEXT,
            original_response_sha256 TEXT,
            normalized_evidence_id TEXT REFERENCES evidence_record(evidence_id) ON DELETE RESTRICT,
            checkpoint_id TEXT REFERENCES ingestion_checkpoint(checkpoint_id) ON DELETE RESTRICT,
            updated_at TEXT NOT NULL
        )
        """
    )
    old_columns = columns
    external_expr = "COALESCE(external_record_id, external_id)" if "external_id" in old_columns else "external_record_id"
    retrieval_expr = "COALESCE(retrieval_date, fetched_at)" if "fetched_at" in old_columns else "retrieval_date"
    rows = con.execute(
        f"""
        SELECT item_id, source_id, provider, {external_expr} AS external_record_id,
               capture_date, event_date, {retrieval_expr} AS retrieval_date,
               original_response_sha256, normalized_evidence_id, checkpoint_id,
               updated_at
        FROM mcp_item
        """
    ).fetchall()
    for row in rows:
        if not row["source_id"] or not con.execute(
            "SELECT 1 FROM source_record WHERE source_id=?", (row["source_id"],)
        ).fetchone():
            raise RuntimeError(
                "MCP migration found an item without a valid source parent; "
                "database preserved"
            )
        if not row["provider"]:
            raise RuntimeError(
                "MCP migration found an item without a provider; database preserved"
            )
        con.execute(
            """
            INSERT INTO mcp_item__migration_new (
                item_id, source_id, provider, external_record_id, capture_date,
                event_date, retrieval_date, original_response_sha256,
                normalized_evidence_id, checkpoint_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            tuple(row),
        )
    con.execute("DROP TABLE mcp_item")
    con.execute("ALTER TABLE mcp_item__migration_new RENAME TO mcp_item")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_mcp_provider_date ON mcp_item(provider, event_date)"
    )


def connect(
    path: Path,
    *,
    skip_classifications: Optional[Iterable[str]] = None,
) -> sqlite3.Connection:
    ensure_dir(path.parent)
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        _reject_orphaned_legacy_versions(con)
        _rename_bootstrap_tables(con)
        # Add columns used by CREATE INDEX statements before applying the full
        # schema to a bootstrap database whose tables already exist.
        _migrate_columns(con)
        con.executescript(SCHEMA)
        _migrate_columns(con)
        # SCHEMA enables foreign keys for normal operation. SQLite requires
        # them to be disabled while a legacy table is rebuilt, so switch them
        # off explicitly for that bounded migration step.
        con.execute("PRAGMA foreign_keys=OFF")
        _migrate_mcp_items(con)
        _migrate_source_foreign_keys(con)
        _backfill_source_versions(con)
        _migrate_normalized_documents(con)
        mark_noncurrent_normalized_documents_retained(
            con,
            now_iso(),
            skip_classifications=skip_classifications,
        )
        con.execute(
            """
            INSERT INTO schema_meta (schema_version, migrated_at)
            VALUES (?, ?)
            ON CONFLICT(schema_version) DO NOTHING
            """,
            (SCHEMA_VERSION, now_iso()),
        )
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        violations = con.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                "schema migration preserved data but found foreign-key "
                f"violations: {len(violations)}; database was not dropped"
            )
        return con
    except Exception:
        con.rollback()
        con.close()
        raise


def upsert_source_record(
    con: sqlite3.Connection,
    root_key: str,
    relative_path: str,
    source_system: str,
    kind: str,
    scope: str,
    sensitivity: str,
    status: str = "present",
    first_seen: Optional[str] = None,
    last_seen: Optional[str] = None,
) -> str:
    """Create or refresh a stable source location without touching its versions."""
    source_id = stable_source_id(root_key, relative_path)
    observed_at = last_seen or now_iso()
    first_observed = first_seen or observed_at
    con.execute(
        """
        INSERT INTO source_record (
            source_id, root_key, relative_path, source_system, kind, scope,
            classification, sensitivity, status, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            root_key=excluded.root_key,
            relative_path=excluded.relative_path,
            source_system=excluded.source_system,
            kind=excluded.kind,
            scope=excluded.scope,
            classification=excluded.classification,
            sensitivity=excluded.sensitivity,
            status=excluded.status,
            last_seen=excluded.last_seen
        """,
        (
            source_id,
            root_key,
            relative_path,
            source_system,
            kind,
            scope,
            scope,
            sensitivity,
            status,
            first_observed,
            observed_at,
        ),
    )
    return source_id


def record_source_version(
    con: sqlite3.Connection,
    source_id: str,
    size_bytes: int,
    mtime_ns: int,
    content_sha256: str,
    observed_dates: Optional[Union[str, dict[str, Any]]] = None,
    created_at: Optional[str] = None,
) -> str:
    """Record one immutable content version and refresh audit observations."""
    version_id = stable_source_version_id(source_id, content_sha256)
    if version_id is None:
        raise ValueError("source version requires a content hash")
    timestamp = created_at or now_iso()
    dates_json = (
        json.dumps(observed_dates, sort_keys=True, separators=(",", ":"))
        if isinstance(observed_dates, dict)
        else observed_dates
    )
    con.execute(
        """
        INSERT INTO source_version (
            source_version_id, source_id, size_bytes, mtime_ns, content_sha256,
            observed_dates, created_at, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_version_id) DO UPDATE SET
            size_bytes=excluded.size_bytes,
            mtime_ns=excluded.mtime_ns,
            observed_dates=COALESCE(excluded.observed_dates, source_version.observed_dates),
            last_seen=excluded.last_seen
        """,
        (
            version_id,
            source_id,
            size_bytes,
            mtime_ns,
            content_sha256,
            dates_json,
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    con.execute(
        """
        UPDATE source_record
        SET source_version_id=?, content_sha256=?, size_bytes=?, mtime_ns=?,
            last_seen=?
        WHERE source_id=?
        """,
        (version_id, content_sha256, size_bytes, mtime_ns, timestamp, source_id),
    )
    return version_id


def record_evidence(
    con: sqlite3.Connection,
    source_version_id: str,
    locator: str,
    derived_text_path: Optional[str],
    text_sha256: Optional[str],
    evidence_status: str,
    created_at: Optional[str] = None,
    *,
    derived_text: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    """Record a deterministic locator within an immutable source version."""
    evidence_id = stable_evidence_id(source_version_id, locator)
    timestamp = created_at or now_iso()
    con.execute(
        """
        INSERT INTO evidence_record (
            evidence_id, source_version_id, locator, derived_text_path,
            text_sha256, evidence_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(evidence_id) DO UPDATE SET
            derived_text_path=excluded.derived_text_path,
            text_sha256=excluded.text_sha256,
            evidence_status=excluded.evidence_status,
            updated_at=excluded.updated_at
        """,
        (
            evidence_id,
            source_version_id,
            locator,
            derived_text_path,
            text_sha256,
            evidence_status,
            timestamp,
            timestamp,
        ),
    )
    if derived_text is not None:
        con.execute("DELETE FROM derived_text_fts WHERE evidence_id=?", (evidence_id,))
        con.execute(
            "INSERT INTO derived_text_fts (document_id, evidence_id, derived_text) VALUES (?, ?, ?)",
            (document_id, evidence_id, scrub_fts_text(derived_text)),
        )
    return evidence_id


def record_review_item(
    con: sqlite3.Connection,
    issue_type: str,
    proposed_result: Any,
    source_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
    reason: Optional[str] = None,
    confidence: Optional[float] = None,
    status: str = "pending",
) -> str:
    """Record one stable proposal while preserving any prior resolution."""
    proposal_json = json.dumps(
        proposed_result,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    proposal_hash = hashlib.sha256(proposal_json.encode("utf-8")).hexdigest()
    identity = ":".join(
        ("review-item:v1", issue_type, source_id or "", evidence_id or "", proposal_hash)
    )
    review_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    timestamp = now_iso()
    con.execute(
        """
        INSERT INTO review_item (
            review_id, issue_type, source_id, evidence_id, proposal_hash,
            proposed_result_json, reason, confidence, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_id) DO UPDATE SET
            reason=excluded.reason,
            confidence=excluded.confidence,
            updated_at=excluded.updated_at
        """,
        (
            review_id,
            issue_type,
            source_id,
            evidence_id,
            proposal_hash,
            proposal_json,
            reason,
            confidence,
            status,
            timestamp,
            timestamp,
        ),
    )
    return review_id


def current_tasks(
    con: sqlite3.Connection,
    run_date: Union[str, date, datetime],
) -> List[sqlite3.Row]:
    """Return explicit, unresolved tasks current relative to the supplied run date."""
    if isinstance(run_date, datetime):
        effective_date = run_date.date()
    elif isinstance(run_date, date):
        effective_date = run_date
    else:
        effective_date = date.fromisoformat(run_date)
    boundary = effective_date - timedelta(days=14)
    return con.execute(
        """
        SELECT t.*
        FROM task AS t
        JOIN evidence_record AS e
          ON e.evidence_id = t.source_evidence_id
        JOIN source_version AS v
          ON v.source_version_id = e.source_version_id
        JOIN source_record AS s
          ON s.source_id = v.source_id
        WHERE TRIM(t.action) <> ''
          AND COALESCE(t.source_event_date, t.event_date) IS NOT NULL
          AND date(COALESCE(t.source_event_date, t.event_date)) >= date(?)
          AND LOWER(TRIM(t.source_date_basis))
              IN ('event', 'event_date', 'meeting', 'meeting_date')
          AND LOWER(COALESCE(s.classification, s.scope, 'Unknown')) = 'work'
          AND LOWER(COALESCE(t.candidate_status, 'candidate'))
              IN ('accepted', 'approved', 'confirmed', 'current')
          AND LOWER(COALESCE(t.task_status, t.status, 'open'))
              NOT IN ('completed', 'cancelled', 'dismissed', 'historical')
        ORDER BY date(COALESCE(t.source_event_date, t.event_date)), t.task_id
        """,
        (boundary.isoformat(),),
    ).fetchall()
