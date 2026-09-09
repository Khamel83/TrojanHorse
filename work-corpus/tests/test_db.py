from __future__ import annotations

import fcntl
import hashlib
import sqlite3
from datetime import date

import pytest

from work_corpus import db


connect = db.connect


def _read_lock(database):
    lock_path = database.with_name(database.name + ".lock")
    lock_path.touch()
    return lock_path


REQUIRED_TABLES = {
    "schema_meta",
    "pipeline_run",
    "source_root",
    "source_record",
    "source_version",
    "date_observation",
    "normalized_document",
    "meeting_group",
    "transcription_job",
    "evidence_record",
    "entity",
    "entity_alias",
    "entity_mention",
    "document",
    "task",
    "relationship",
    "review_item",
    "ingestion_checkpoint",
    "mcp_item",
    "derived_text_fts",
}


def _table_names(con: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        if not row[0].startswith("sqlite_")
    }


def _source(con: sqlite3.Connection, *, relative_path: str = "notes/example.md") -> str:
    con.execute(
        """
        INSERT INTO source_root (
            root_key, relative_path, source_system, precedence, enabled
        ) VALUES ('notes', 'data/notes', 'capacities', 10, 1)
        ON CONFLICT(root_key) DO NOTHING
        """
    )
    return db.upsert_source_record(
        con,
        root_key="notes",
        relative_path=relative_path,
        source_system="capacities",
        kind="document",
        scope="Work",
        sensitivity="internal",
    )


def _version(con: sqlite3.Connection, source_id: str, content: bytes = b"one") -> str:
    return db.record_source_version(
        con,
        source_id=source_id,
        size_bytes=len(content),
        mtime_ns=123,
        content_sha256=hashlib.sha256(content).hexdigest(),
        observed_dates='{"file_modification":"2026-09-01"}',
    )


def test_schema_contains_provenance_tables_and_fts(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    try:
        assert REQUIRED_TABLES <= _table_names(con)
        fts_sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='derived_text_fts'"
        ).fetchone()[0]
        assert "fts5" in fts_sql.casefold()
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        con.close()


def test_read_only_connect_requires_an_existing_database(tmp_path):
    database = tmp_path / "missing" / "state.sqlite"

    with pytest.raises(sqlite3.OperationalError):
        connect(database, read_only=True)

    assert not database.exists()
    assert not database.parent.exists()


def test_read_only_connect_fails_closed_without_maintenance_lock(tmp_path):
    database = tmp_path / "state.sqlite"
    con = connect(database)
    con.close()

    with pytest.raises(sqlite3.OperationalError, match="maintenance lock"):
        connect(database, read_only=True)


def test_read_only_connect_preserves_schema_and_rejects_mutation(tmp_path):
    database = tmp_path / "state.sqlite"
    con = connect(database)
    con.close()
    before = database.read_bytes()

    read_only = connect(
        database,
        read_only=True,
        read_only_lock_path=_read_lock(database),
    )
    try:
        assert isinstance(read_only, sqlite3.Connection)
        assert isinstance(
            read_only.execute("SELECT 1 AS value").fetchone(), sqlite3.Row
        )
        assert read_only.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            read_only.execute(
                "INSERT INTO schema_meta (schema_version, migrated_at) "
                "VALUES (999, 'test')"
            )
    finally:
        read_only.close()

    assert database.read_bytes() == before


def test_read_only_wal_connect_does_not_mutate_a_read_only_database_directory(
    tmp_path,
):
    database = tmp_path / "read-only" / "state.sqlite"
    con = connect(database)
    try:
        con.execute("CREATE TABLE wal_probe (value TEXT NOT NULL)")
        con.execute("INSERT INTO wal_probe (value) VALUES ('visible')")
        con.commit()
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        con.close()

    for suffix in ("-shm", "-wal"):
        database.with_name(database.name + suffix).unlink(missing_ok=True)
    lock_path = _read_lock(database)

    before_files = {
        item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
        for item in database.parent.iterdir()
    }
    original_directory_mode = database.parent.stat().st_mode & 0o777
    database.parent.chmod(0o555)
    before_directory = (
        database.parent.stat().st_mode,
        database.parent.stat().st_mtime_ns,
    )
    after_files = None
    after_directory = None
    try:
        read_only = connect(
            database,
            read_only=True,
            read_only_lock_path=lock_path,
        )
        try:
            assert read_only.execute(
                "SELECT value FROM wal_probe"
            ).fetchone()[0] == "visible"
        finally:
            read_only.close()
        after_files = {
            item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
            for item in database.parent.iterdir()
        }
        after_directory = (
            database.parent.stat().st_mode,
            database.parent.stat().st_mtime_ns,
        )
    finally:
        database.parent.chmod(original_directory_mode)

    assert after_files == before_files
    assert after_directory == before_directory


def test_read_only_wal_connect_rejects_active_sidecars_without_mutation(tmp_path):
    database = tmp_path / "state.sqlite"
    writer = connect(database)
    try:
        writer.execute(
            "CREATE TABLE wal_visibility_probe (value TEXT NOT NULL)"
        )
        writer.execute(
            "INSERT INTO wal_visibility_probe (value) VALUES ('visible')"
        )
        writer.commit()

        sidecars = {
            database.with_name(database.name + suffix)
            for suffix in ("-shm", "-wal")
        }
        assert all(sidecar.exists() for sidecar in sidecars)
        lock_path = _read_lock(database)
        before_files = {
            item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
            for item in database.parent.iterdir()
        }
        before_directory = (
            database.parent.stat().st_mode,
            database.parent.stat().st_mtime_ns,
        )

        with pytest.raises(sqlite3.OperationalError, match="WAL"):
            connect(
                database,
                read_only=True,
                read_only_lock_path=lock_path,
            )

        after_files = {
            item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
            for item in database.parent.iterdir()
        }
        after_directory = (
            database.parent.stat().st_mode,
            database.parent.stat().st_mtime_ns,
        )
        assert after_files == before_files
        assert after_directory == before_directory
    finally:
        writer.close()


def test_read_only_connect_rejects_rollback_journal_without_mutation(tmp_path):
    database = tmp_path / "state.sqlite"
    writer = sqlite3.connect(database)
    try:
        writer.execute(
            "CREATE TABLE rollback_visibility_probe (value TEXT NOT NULL)"
        )
        writer.commit()
        assert writer.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "INSERT INTO rollback_visibility_probe (value) VALUES ('pending')"
        )
        journal = database.with_name(database.name + "-journal")
        assert journal.exists()
        lock_path = _read_lock(database)
        before_files = {
            item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
            for item in database.parent.iterdir()
        }
        before_directory = (
            database.parent.stat().st_mode,
            database.parent.stat().st_mtime_ns,
        )

        with pytest.raises(sqlite3.OperationalError, match="rollback journal"):
            connect(
                database,
                read_only=True,
                read_only_lock_path=lock_path,
            )

        after_files = {
            item.name: (item.stat().st_mode, item.stat().st_size, item.read_bytes())
            for item in database.parent.iterdir()
        }
        after_directory = (
            database.parent.stat().st_mode,
            database.parent.stat().st_mtime_ns,
        )
        assert after_files == before_files
        assert after_directory == before_directory
    finally:
        writer.rollback()
        writer.close()


def test_read_only_connect_holds_shared_maintenance_lock(tmp_path):
    database = tmp_path / "state.sqlite"
    lock_path = tmp_path / "mcp" / "granola_rest_delta.lock"
    lock_path.parent.mkdir()
    lock_path.touch()
    con = connect(database)
    con.execute("CREATE TABLE probe (value TEXT NOT NULL)")
    con.execute("INSERT INTO probe VALUES ('committed')")
    con.commit()
    con.close()

    read_only = connect(
        database,
        read_only=True,
        read_only_lock_path=lock_path,
    )
    assert read_only.in_transaction is True
    writer_handle = lock_path.open("rb")
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(writer_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        read_only.close()
        fcntl.flock(writer_handle.fileno(), fcntl.LOCK_UN)
        writer_handle.close()

    writer = connect(database, write_lock_path=lock_path)
    reader_handle = lock_path.open("rb")
    try:
        with pytest.raises(BlockingIOError):
            fcntl.flock(reader_handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
    finally:
        writer.close()
        fcntl.flock(reader_handle.fileno(), fcntl.LOCK_UN)
        reader_handle.close()


def test_schema_has_no_email_career_claim_or_decision_table(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    try:
        tables = _table_names(con)
    finally:
        con.close()

    assert "email_message" not in tables
    assert "career_claim" not in tables
    assert "decision" not in tables


def test_foreign_keys_reject_orphan_provenance(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            db.record_source_version(
                con,
                source_id="missing",
                size_bytes=1,
                mtime_ns=1,
                content_sha256=hashlib.sha256(b"x").hexdigest(),
            )
    finally:
        con.close()


def test_unsafe_legacy_schema_fails_closed_without_accepting_orphans(tmp_path):
    database = tmp_path / "legacy.sqlite"
    legacy = sqlite3.connect(database)
    try:
        legacy.executescript(
            """
            CREATE TABLE source_item (
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
            CREATE TABLE source_version (
                source_version_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL
            );
            INSERT INTO source_version VALUES
                ('orphan', 'missing-source', 'hash', 1, 1, 'a', 'a');
            """
        )
        legacy.commit()
    finally:
        legacy.close()

    with pytest.raises(RuntimeError, match="database preserved"):
        connect(database)

    check = sqlite3.connect(database)
    try:
        assert check.execute(
            "SELECT source_id FROM source_version WHERE source_version_id='orphan'"
        ).fetchone() == ("missing-source",)
        assert check.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='source_item'"
        ).fetchone() == ("source_item",)
    finally:
        check.close()


def test_version_only_legacy_state_fails_closed(tmp_path):
    database = tmp_path / "version-only.sqlite"
    legacy = sqlite3.connect(database)
    try:
        legacy.execute(
            "CREATE TABLE source_version ("
            "source_version_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, "
            "content_sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL, "
            "mtime_ns INTEGER NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL)"
        )
        legacy.execute(
            "INSERT INTO source_version VALUES "
            "('orphan', 'missing-source', 'hash', 1, 1, 'a', 'a')"
        )
        legacy.commit()
    finally:
        legacy.close()

    with pytest.raises(RuntimeError, match="database preserved"):
        connect(database)

    check = sqlite3.connect(database)
    try:
        assert check.execute(
            "SELECT COUNT(*) FROM source_version WHERE source_version_id='orphan'"
        ).fetchone()[0] == 1
    finally:
        check.close()


def test_deterministic_ids_retain_versions_and_make_reruns_idempotent(tmp_path):
    database = tmp_path / "state.sqlite"
    con = connect(database)
    try:
        source_id = _source(con)
        repeated_source_id = _source(con)
        first_version_id = _version(con, source_id, b"one")
        repeated_version_id = _version(con, source_id, b"one")
        second_version_id = _version(con, source_id, b"two")
        evidence_id = db.record_evidence(
            con,
            source_version_id=first_version_id,
            locator="line:12",
            derived_text_path="corpus/normalized/example.md",
            text_sha256=hashlib.sha256(b"derived").hexdigest(),
            evidence_status="derived_reviewed",
        )
        repeated_evidence_id = db.record_evidence(
            con,
            source_version_id=first_version_id,
            locator="line:12",
            derived_text_path="corpus/normalized/example.md",
            text_sha256=hashlib.sha256(b"derived").hexdigest(),
            evidence_status="derived_reviewed",
        )
        review_id = db.record_review_item(
            con,
            issue_type="scope",
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result={"scope": "Work"},
            reason="synthetic test",
            confidence=0.9,
        )
        repeated_review_id = db.record_review_item(
            con,
            issue_type="scope",
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result={"scope": "Work"},
            reason="synthetic test rerun",
            confidence=0.9,
        )
        con.commit()

        assert source_id == repeated_source_id
        assert first_version_id == repeated_version_id
        assert first_version_id != second_version_id
        assert evidence_id == repeated_evidence_id
        assert review_id == repeated_review_id
        assert con.execute("SELECT COUNT(*) FROM source_record").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM source_version").fetchone()[0] == 2
        assert con.execute("SELECT COUNT(*) FROM evidence_record").fetchone()[0] == 1
        assert con.execute("SELECT COUNT(*) FROM review_item").fetchone()[0] == 1
    finally:
        con.close()

    reopened = connect(database)
    try:
        assert reopened.execute("SELECT COUNT(*) FROM source_record").fetchone()[0] == 1
        assert reopened.execute("SELECT COUNT(*) FROM source_version").fetchone()[0] == 2
        assert reopened.execute("SELECT COUNT(*) FROM evidence_record").fetchone()[0] == 1
        assert reopened.execute("SELECT COUNT(*) FROM review_item").fetchone()[0] == 1
    finally:
        reopened.close()


def test_current_tasks_use_run_date_and_event_date(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    try:
        source_id = _source(con)
        version_id = _version(con, source_id)
        evidence_id = db.record_evidence(
            con,
            source_version_id=version_id,
            locator="section:tasks",
            derived_text_path="corpus/normalized/example.md",
            text_sha256=hashlib.sha256(b"tasks").hexdigest(),
            evidence_status="derived_reviewed",
        )
        rows = [
            ("boundary", "2026-08-21"),
            ("inside", "2026-08-22"),
            ("old", "2026-08-20"),
            ("future", "2026-09-20"),
            ("export-only", None),
            ("missing-date", None),
        ]
        con.executemany(
            """
                INSERT INTO task (
                    task_id, action, source_event_date, source_date_basis, due_date, candidate_status,
                    task_status, source_evidence_id, created_at, updated_at
                ) VALUES (?, ?, ?, 'event_date', NULL, 'accepted', 'open', ?,
                          '2026-09-04T00:00:00Z', '2026-09-04T00:00:00Z')
            """,
            [(name, f"Do {name}", event_date, evidence_id) for name, event_date in rows],
        )
        con.execute(
            """
            INSERT INTO task (
                task_id, action, source_event_date, due_date, candidate_status,
                task_status, source_evidence_id, created_at, updated_at
            ) VALUES ('unaccepted', 'Do not surface', '2026-09-01', NULL,
                      'candidate', 'open', ?, '2026-09-04T00:00:00Z',
                      '2026-09-04T00:00:00Z')
            """,
            (evidence_id,),
        )
        con.execute(
            """
            INSERT INTO date_observation (
                observation_id, evidence_id, date_value, basis, precision,
                confidence, created_at
            ) VALUES ('export-date', ?, '2026-09-03', 'export', 'day', 1.0,
                      '2026-09-04T00:00:00Z')
            """,
            (evidence_id,),
        )

        result = db.current_tasks(con, date(2026, 9, 4))
    finally:
        con.close()

    assert {row["task_id"] for row in result} == {"boundary", "inside", "future"}
