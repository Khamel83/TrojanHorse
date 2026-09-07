from __future__ import annotations

import hashlib
import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.cli import _parser
from work_corpus.db import (
    connect,
    record_evidence,
    record_review_item,
    record_source_version,
    upsert_source_record,
)
from work_corpus.organization import (
    _reconcile_malformed_reviews,
    _record_sensitivity_reviews,
    organize_all,
    reconcile_capacities_payloads,
)
from work_corpus.util import sha256_text


def test_cli_exposes_the_resumable_organization_pass():
    args = _parser().parse_args(["organize", "--run-date", "2026-09-07"])

    assert args.command == "organize"
    assert args.run_date == "2026-09-07"


def _source(
    tmp_path: Path,
    con,
    *,
    root_key: str,
    relative_path: str,
    content: bytes,
    source_system: str = "capacities",
    kind: str = "document",
    scope: str = "Work",
    sensitivity: str = "unknown",
):
    con.execute(
        "INSERT OR IGNORE INTO source_root "
        "(root_key, relative_path, source_system, precedence) VALUES (?, ?, ?, 1)",
        (root_key, relative_path.rsplit("/", 1)[0], source_system),
    )
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    source_id = upsert_source_record(
        con,
        root_key=root_key,
        relative_path=relative_path,
        source_system=source_system,
        kind=kind,
        scope=scope,
        sensitivity=sensitivity,
    )
    digest = hashlib.sha256(content).hexdigest()
    version_id = record_source_version(
        con,
        source_id,
        len(content),
        path.stat().st_mtime_ns,
        digest,
    )
    con.execute(
        "UPDATE source_record SET absolute_path=?, extension=?, classification=?, "
        "extraction_status='ready' WHERE source_id=?",
        (str(path), path.suffix.lower(), scope, source_id),
    )
    return source_id, version_id, path


def test_reconcile_capacities_links_same_content_copies_and_is_idempotent(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        pointer_text = (
            "---\n"
            "type: Image\n"
            "title: image (1)\n"
            "mimeType: image/png\n"
            "fileSize: 4\n"
            "url: null\n"
            "---\n"
        ).encode()
        pointer_id, pointer_version, pointer_path = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/Images/image (1).md",
            content=pointer_text,
        )
        evidence_id = record_evidence(
            con,
            pointer_version,
            "document",
            "work-corpus/corpus/normalized/pointer.md",
            sha256_text(pointer_text.decode()),
            "derived",
            derived_text=pointer_text.decode(),
        )
        target_one, _, _ = _source(
            tmp_path,
            con,
            root_key="capacities_icloud_20250920",
            relative_path="data/notes/Capacities iCloud 2025-09-20/Notes/Images/Media/image (1).png",
            content=b"DATA",
            kind="unknown",
        )
        target_two, _, _ = _source(
            tmp_path,
            con,
            root_key="capacities_icloud_20250806",
            relative_path="data/notes/Capacities iCloud 2025-08-06/MediaFiles/Images/image (1).png",
            content=b"DATA",
            kind="unknown",
        )
        con.commit()

        first = reconcile_capacities_payloads(config, con)
        second = reconcile_capacities_payloads(config, con)
        relationships = con.execute(
            "SELECT from_record_id, to_record_id, evidence_id, status "
            "FROM relationship WHERE relationship_type='capacities_payload' "
            "ORDER BY to_record_id"
        ).fetchall()
        reviews = con.execute(
            "SELECT issue_type, source_id, evidence_id, status FROM review_item "
            "WHERE issue_type='capacities_payload_match'"
        ).fetchall()
    finally:
        con.close()

    assert first["pointer_count"] == 1
    assert first["matched_pointer_count"] == 1
    assert first["unresolved_pointer_count"] == 0
    assert first["target_payload_record_count"] == 2
    assert second["relationship_count"] == first["relationship_count"] == 2
    assert {(row["from_record_id"], row["to_record_id"], row["evidence_id"]) for row in relationships} == {
        (pointer_id, target_one, evidence_id),
        (pointer_id, target_two, evidence_id),
    }
    assert all(row["status"] == "confirmed" for row in relationships)
    assert reviews == []

    state = json.loads(
        (config.state_dir / "capacities_payload_reconciliation.json").read_text()
    )
    assert state["records"][0]["pointer_source_id"] == pointer_id
    assert "url:" not in (config.state_dir / "capacities_payload_reconciliation.json").read_text()
    assert pointer_path.exists()


def test_reconcile_capacities_records_missing_metadata_as_a_specific_residual(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        pointer_id, pointer_version, _ = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/PDFs/Untitled.md",
            content=(
                "---\n"
                "type: PDF\n"
                "title: Untitled\n"
                "mimeType: application/pdf\n"
                "url: https://provider.invalid/signed?sig=secret\n"
                "---\n"
            ).encode(),
        )
        evidence_id = record_evidence(
            con,
            pointer_version,
            "document",
            "work-corpus/corpus/normalized/untitled.md",
            "e" * 64,
            "derived",
        )
        con.commit()
        result = reconcile_capacities_payloads(config, con)
        review = con.execute(
            "SELECT issue_type, source_id, evidence_id, reason, status "
            "FROM review_item WHERE issue_type='capacities_payload_match'"
        ).fetchone()
    finally:
        con.close()

    assert result["unresolved_pointer_count"] == 1
    assert result["unresolved_by_reason"] == {"pointer_missing_file_size": 1}
    assert review["source_id"] == pointer_id
    assert review["evidence_id"] == evidence_id
    assert review["status"] == "pending"
    assert "file size" in review["reason"].lower()
    state_text = (config.state_dir / "capacities_payload_reconciliation.json").read_text()
    assert "secret" not in state_text


def test_reconcile_resolves_stale_pointer_review_after_provenance_is_available(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        pointer_id, pointer_version, _ = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/Images/image.md",
            content=(
                "type: Image\n"
                "title: image\n"
                "mimeType: image/png\n"
                "fileSize: 4\n"
                "url: null\n"
            ).encode(),
        )
        record_evidence(
            con,
            pointer_version,
            "document",
            "work-corpus/corpus/normalized/image.md",
            "e" * 64,
            "derived",
        )
        target_id, _, _ = _source(
            tmp_path,
            con,
            root_key="capacities_icloud_20250920",
            relative_path="data/notes/Capacities iCloud 2025-09-20/Notes/Images/Media/image.png",
            content=b"DATA",
            kind="unknown",
        )
        stale_id = record_review_item(
            con,
            issue_type="capacities_payload_match",
            source_id=pointer_id,
            proposed_result={"action": "old_provenance_gap", "source_id": pointer_id},
            reason="old run",
            status="pending",
        )
        con.commit()
        result = reconcile_capacities_payloads(config, con)
        stale = con.execute(
            "SELECT status, resolution FROM review_item WHERE review_id=?",
            (stale_id,),
        ).fetchone()
    finally:
        con.close()

    assert result["matched_pointer_count"] == 1
    assert stale["status"] == "resolved"
    assert "normalized provenance" in stale["resolution"]
    assert target_id


def test_reconcile_malformed_review_accepts_zero_error_repeat_imports(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        source_id, _, _ = _source(
            tmp_path,
            con,
            root_key="mcp_granola",
            relative_path="data/mcp/granola/snapshot.json",
            content=b"{}",
            source_system="granola",
            kind="mcp",
        )
        review_id = record_review_item(
            con,
            issue_type="mcp_malformed_item",
            source_id=source_id,
            proposed_result={"action": "inspect"},
            reason="old malformed row",
        )
        (config.state_dir / "granola_acceptance.json").write_text(
            json.dumps(
                {
                    "repeat_import_runs": [
                        {"malformed": 0, "errors": 0},
                        {"malformed": 0, "errors": 0},
                    ]
                }
            ),
            encoding="utf-8",
        )
        con.commit()
        resolved = _reconcile_malformed_reviews(config, con)
        row = con.execute(
            "SELECT status, resolution FROM review_item WHERE review_id=?",
            (review_id,),
        ).fetchone()
    finally:
        con.close()

    assert resolved == 1
    assert row["status"] == "resolved"
    assert "zero malformed" in row["resolution"]


def test_sensitivity_review_supersedes_unanchored_row_when_evidence_arrives(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        source_id, source_version, _ = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/Private/Review.md",
            content=b"private review",
            scope="Personal",
            sensitivity="potential_restricted",
        )
        con.commit()
        first_count, first_resolved = _record_sensitivity_reviews(con)
        stale_id = con.execute(
            "SELECT review_id FROM review_item WHERE issue_type='sensitivity_review'"
        ).fetchone()[0]
        record_evidence(
            con,
            source_version,
            "document",
            "work-corpus/corpus/normalized/review.md",
            "e" * 64,
            "derived",
        )
        second_count, second_resolved = _record_sensitivity_reviews(con)
        rows = con.execute(
            "SELECT status, evidence_id FROM review_item "
            "WHERE issue_type='sensitivity_review' ORDER BY created_at, review_id"
        ).fetchall()
    finally:
        con.close()

    assert first_count == second_count == 1
    assert first_resolved == 0
    assert second_resolved == 1
    assert {row["status"] for row in rows} == {"pending", "resolved"}
    assert [row for row in rows if row["status"] == "resolved"][0]["evidence_id"] is None
    assert [row for row in rows if row["status"] == "pending"][0]["evidence_id"]
    assert stale_id


def test_organize_all_creates_only_explicit_project_entities_and_repeats_cleanly(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "organization.sqlite")
    try:
        project_id, project_version, _ = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/Projects/Project Alpha.md",
            content=(
                "---\n"
                "type: Project\n"
                "title: Project Alpha\n"
                "---\n"
                "Project evidence.\n"
            ).encode(),
        )
        project_evidence = record_evidence(
            con,
            project_version,
            "document",
            "work-corpus/corpus/normalized/project-alpha.md",
            "a" * 64,
            "derived",
            derived_text="Project Alpha",
        )
        page_id, page_version, _ = _source(
            tmp_path,
            con,
            root_key="capacities_markdown",
            relative_path="data/notes/Notes/Pages/1-1 Christina.md",
            content=(
                "---\n"
                "type: Page\n"
                "title: 1:1 Christina\n"
                "---\n"
            ).encode(),
        )
        record_evidence(
            con,
            page_version,
            "document",
            "work-corpus/corpus/normalized/christina.md",
            "b" * 64,
            "derived",
            derived_text="1:1 Christina",
        )
        con.commit()

        first = organize_all(config, con)
        second = organize_all(config, con)
        entity_count = con.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
        alias_count = con.execute("SELECT COUNT(*) FROM entity_alias").fetchone()[0]
        mention_count = con.execute("SELECT COUNT(*) FROM entity_mention").fetchone()[0]
        project_relationships = con.execute(
            "SELECT COUNT(*) FROM relationship WHERE relationship_type='entity_evidence'"
        ).fetchone()[0]
        page_reviews = con.execute(
            "SELECT COUNT(*) FROM review_item WHERE issue_type='entity_candidate_review'"
        ).fetchone()[0]
    finally:
        con.close()

    assert first["entities_created"] == 1
    assert first["project_sources_linked"] == 1
    assert first["candidate_review_items"] == 1
    assert second["entities_created"] == 1
    assert second["project_sources_linked"] == 1
    assert entity_count == alias_count == mention_count == project_relationships == 1
    assert page_reviews == 1
    assert project_id != page_id
    state = json.loads((config.state_dir / "organization_acceptance.json").read_text())
    assert state["entity_counts"]["project"] == 1
    assert state["entity_counts"]["person"] == 0
    assert state["entity_counts"]["organization"] == 0
