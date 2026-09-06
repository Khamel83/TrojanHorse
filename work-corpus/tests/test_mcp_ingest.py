from __future__ import annotations

import hashlib
import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import connect, record_source_version, upsert_source_record
from work_corpus.mcp_ingest import ingest_mcp_sources


def _source(tmp_path: Path, provider: str, name: str, content: str):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "mcp.sqlite")
    root_key = "mcp_granola" if provider == "granola" else "mcp_wispr_flow"
    con.execute(
        """
        INSERT INTO source_root (root_key, relative_path, source_system, precedence, enabled)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(root_key) DO NOTHING
        """,
        (root_key, f"data/mcp/{provider}", provider, 45),
    )
    relative_path = f"data/mcp/{provider}/{name}"
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    source_id = upsert_source_record(
        con,
        root_key=root_key,
        relative_path=relative_path,
        source_system=provider,
        kind="mcp",
        scope="Work",
        sensitivity="internal_review",
    )
    payload = content.encode("utf-8")
    version_id = record_source_version(
        con,
        source_id,
        len(payload),
        path.stat().st_mtime_ns,
        hashlib.sha256(payload).hexdigest(),
    )
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, extension=?, classification='Work', scope='Work',
            extraction_status='ready'
        WHERE source_id=?
        """,
        (str(path), path.suffix.lower(), source_id),
    )
    con.commit()
    return config, con, source_id, version_id


def test_external_id_is_idempotent_and_event_date_is_preserved(tmp_path: Path):
    payload = json.dumps(
        {
            "items": [
                {
                    "id": "granola-42",
                    "title": "Weekly review",
                    "event_date": "2026-09-03T10:00:00Z",
                    "capture_date": "2026-09-03",
                    "retrieval_date": "2026-09-04",
                    "content": "Discuss launch status.",
                }
            ]
        }
    )
    config, con, _source_id, version_id = _source(
        tmp_path, "granola", "snapshot.json", payload
    )
    try:
        first = ingest_mcp_sources(config, con)
        first_checkpoint_count = con.execute(
            "SELECT item_count FROM ingestion_checkpoint"
        ).fetchone()[0]
        second = ingest_mcp_sources(config, con)
        item = con.execute("SELECT * FROM mcp_item").fetchone()
        evidence_count = con.execute("SELECT COUNT(*) FROM evidence_record").fetchone()[0]
        checkpoint = con.execute(
            "SELECT provider, cursor, source_version_id, item_count FROM ingestion_checkpoint"
        ).fetchone()
        columns = [row[1] for row in con.execute("PRAGMA table_info(mcp_item)")]
    finally:
        con.close()

    assert first["items"] == 1
    assert second["items"] == 1
    assert second["updated_items"] == 1
    assert first_checkpoint_count == 1
    assert item["provider"] == "granola"
    assert item["external_record_id"] == "granola-42"
    assert item["event_date"] == "2026-09-03"
    assert item["capture_date"] == "2026-09-03"
    assert item["retrieval_date"] == "2026-09-04"
    assert item["original_response_sha256"]
    assert item["normalized_evidence_id"]
    assert item["checkpoint_id"]
    assert evidence_count == 1
    assert checkpoint["provider"] == "granola"
    assert checkpoint["cursor"].endswith(":0")
    assert checkpoint["source_version_id"] == version_id
    assert checkpoint["item_count"] == 1
    assert columns == [
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
    ]


def test_overlapping_snapshot_reuses_evidence_for_same_response(tmp_path: Path):
    payload = json.dumps(
        {
            "items": [
                {
                    "id": "overlap-1",
                    "title": "Repeated capture",
                    "content": "The same item is present in both snapshots.",
                }
            ]
        }
    )
    config, con, _source_id, _version_id = _source(
        tmp_path, "granola", "first.json", payload
    )
    second_path = tmp_path / "data/mcp/granola/second.json"
    second_path.write_text(payload, encoding="utf-8")
    second_source_id = upsert_source_record(
        con,
        root_key="mcp_granola",
        relative_path="data/mcp/granola/second.json",
        source_system="granola",
        kind="mcp",
        scope="Work",
        sensitivity="internal_review",
    )
    second_bytes = payload.encode("utf-8")
    record_source_version(
        con,
        second_source_id,
        len(second_bytes),
        second_path.stat().st_mtime_ns,
        hashlib.sha256(second_bytes).hexdigest(),
    )
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, extension=?, classification='Work', scope='Work',
            extraction_status='ready'
        WHERE source_id=?
        """,
        (str(second_path), second_path.suffix.lower(), second_source_id),
    )
    con.commit()
    try:
        first = ingest_mcp_sources(config, con)
        first_evidence = con.execute(
            "SELECT normalized_evidence_id FROM mcp_item"
        ).fetchone()[0]
        second = ingest_mcp_sources(config, con)
        item_count = con.execute("SELECT COUNT(*) FROM mcp_item").fetchone()[0]
        evidence_count = con.execute(
            "SELECT COUNT(*) FROM evidence_record"
        ).fetchone()[0]
        second_evidence = con.execute(
            "SELECT normalized_evidence_id FROM mcp_item"
        ).fetchone()[0]
    finally:
        con.close()

    assert first["items"] == 2
    assert second["items"] == 2
    assert item_count == 1
    assert evidence_count == 1
    assert second_evidence == first_evidence


def test_thinner_overlapping_snapshot_does_not_replace_richer_content(tmp_path: Path):
    rich_payload = json.dumps(
        {
            "items": [
                {
                    "id": "merge-1",
                    "title": "Recorded meeting",
                    "event_date": "2026-09-03T10:00:00Z",
                    "retrieval_date": "2026-09-06",
                    "transcript": "Long transcript content. " * 100,
                }
            ]
        }
    )
    config, con, rich_source_id, _version_id = _source(
        tmp_path, "granola", "a-rich.json", rich_payload
    )
    thin_payload = json.dumps(
        {
            "items": [
                {
                    "id": "merge-1",
                    "title": "Recorded meeting",
                    "event_date": "2026-09-03T10:00:00Z",
                    "summary": "Short listing metadata.",
                }
            ]
        }
    )
    thin_path = tmp_path / "data/mcp/granola/z-thin.json"
    thin_path.write_text(thin_payload, encoding="utf-8")
    thin_source_id = upsert_source_record(
        con,
        root_key="mcp_granola",
        relative_path="data/mcp/granola/z-thin.json",
        source_system="granola",
        kind="mcp",
        scope="Work",
        sensitivity="internal_review",
    )
    thin_bytes = thin_payload.encode("utf-8")
    record_source_version(
        con,
        thin_source_id,
        len(thin_bytes),
        thin_path.stat().st_mtime_ns,
        hashlib.sha256(thin_bytes).hexdigest(),
    )
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, extension=?, classification='Work', scope='Work',
            extraction_status='ready'
        WHERE source_id=?
        """,
        (str(thin_path), thin_path.suffix.lower(), thin_source_id),
    )
    con.commit()
    try:
        result = ingest_mcp_sources(config, con)
        item = con.execute("SELECT * FROM mcp_item").fetchone()
        derived = con.execute(
            "SELECT derived_text FROM derived_text_fts WHERE evidence_id=?",
            (item["normalized_evidence_id"],),
        ).fetchone()[0]
    finally:
        con.close()

    assert result["items"] == 2
    assert item["source_id"] == rich_source_id
    assert item["retrieval_date"] == "2026-09-06"
    assert "Long transcript content." in derived
    assert "Short listing metadata." not in derived


def test_mcp_derived_metadata_is_scrubbed(tmp_path: Path):
    payload = json.dumps(
        {
            "items": [
                {
                    "id": "safe-id",
                    "title": "token: title-secret",
                    "content": "A local note.",
                }
            ]
        }
    )
    config, con, _source_id, _version_id = _source(
        tmp_path, "granola", "snapshot.json", payload
    )
    try:
        ingest_mcp_sources(config, con)
        evidence_path = Path(
            con.execute(
                "SELECT derived_text_path FROM evidence_record"
            ).fetchone()[0]
        )
        derived = evidence_path.read_text(encoding="utf-8")
    finally:
        con.close()

    assert "title-secret" not in derived
    assert "[REDACTED_SECRET]" in derived


def test_malformed_snapshot_does_not_advance_checkpoint(tmp_path: Path):
    payload = '''{"id":"valid","content":"ok"}
not-json
'''
    config, con, _source_id, _version_id = _source(
        tmp_path, "granola", "snapshot.jsonl", payload
    )
    try:
        ingest_mcp_sources(config, con)
        checkpoint = con.execute(
            "SELECT cursor, last_successful_retrieval, error FROM ingestion_checkpoint"
        ).fetchone()
    finally:
        con.close()

    assert checkpoint["cursor"] is None
    assert checkpoint["last_successful_retrieval"] is None
    assert checkpoint["error"]


def test_missing_external_ids_use_content_hash_fallback_without_duplicates(tmp_path: Path):
    payload = json.dumps(
        [
            {"title": "First", "content": "same source"},
            {"title": "Second", "content": "another source"},
        ]
    )
    config, con, _source_id, _version_id = _source(
        tmp_path, "wispr_flow", "snapshot.json", payload
    )
    try:
        ingest_mcp_sources(config, con)
        first_ids = [row["item_id"] for row in con.execute("SELECT item_id FROM mcp_item ORDER BY item_id")]
        ingest_mcp_sources(config, con)
        second_ids = [row["item_id"] for row in con.execute("SELECT item_id FROM mcp_item ORDER BY item_id")]
    finally:
        con.close()

    assert len(first_ids) == 2
    assert first_ids == second_ids


def test_malformed_snapshot_record_creates_review_item(tmp_path: Path):
    payload = """{"id":"valid","content":"ok"}
not-json
["""  # JSONL
    config, con, source_id, _version_id = _source(
        tmp_path, "granola", "snapshot.jsonl", payload
    )
    try:
        result = ingest_mcp_sources(config, con)
        reviews = con.execute(
            "SELECT issue_type, source_id, status, proposed_result_json FROM review_item"
        ).fetchall()
        items = con.execute("SELECT COUNT(*) FROM mcp_item").fetchone()[0]
    finally:
        con.close()

    assert result["items"] == 1
    assert result["malformed"] == 2
    assert items == 1
    assert len(reviews) == 2
    assert all(row["issue_type"] == "mcp_malformed_item" for row in reviews)
    assert all(row["source_id"] == source_id for row in reviews)


def test_markdown_and_text_snapshots_are_local_evidence(tmp_path: Path):
    config, con, _source_id, _version_id = _source(
        tmp_path, "wispr_flow", "notes.md", "# Local capture\n\nFollow up with the team."
    )
    try:
        result = ingest_mcp_sources(config, con)
        row = con.execute("SELECT provider, external_record_id FROM mcp_item").fetchone()
        evidence = con.execute("SELECT derived_text_path FROM evidence_record").fetchone()
    finally:
        con.close()

    assert result["items"] == 1
    assert row["provider"] == "wispr_flow"
    assert row["external_record_id"] is None
    assert Path(evidence["derived_text_path"]).is_file()
