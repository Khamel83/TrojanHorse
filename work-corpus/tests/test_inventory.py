from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import zipfile

import pytest

import work_corpus.inventory as inventory_module
from work_corpus.config import load_config
from work_corpus.db import connect
from work_corpus.util import detect_source_system


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "inventory_tree"
NOTION_EXPORT = (
    "40b7a161-92e3-450d-8dab-c2bb4a080adf_"
    "ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2"
)
CAPACITIES_ARCHIVE = "Capacities (2026-09-03 14-19-01).zip"


def _prepare_tree(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE_ROOT, tmp_path, dirs_exist_ok=True)
    notes = tmp_path / "data" / "notes"
    with zipfile.ZipFile(notes / CAPACITIES_ARCHIVE, "w") as archive:
        archive.writestr("Notes/notion-roadmap.md", "# Capacity note\n")
        archive.writestr("Notes/archive-only.md", "# Archived copy\n")
    with zipfile.ZipFile(notes / f"{NOTION_EXPORT}.zip", "w") as archive:
        archive.writestr(f"{NOTION_EXPORT}/Project.html", "<h1>Notion project</h1>\n")
    return tmp_path


def _classifier():
    classifier = getattr(inventory_module, "classify_root", None)
    assert classifier is not None, "the explicit SourceRoot classifier is missing"
    return classifier


def _scope_classifier():
    classifier = getattr(inventory_module, "classify_scope", None)
    assert classifier is not None, "the scope-proposal classifier is missing"
    return classifier


def _row(con: sqlite3.Connection, relative_path: str) -> tuple[sqlite3.Row, dict]:
    row = con.execute(
        "SELECT * FROM source_item WHERE relative_path=?",
        (relative_path,),
    ).fetchone()
    assert row is not None, f"manifest row not found: {relative_path}"
    return row, json.loads(row["metadata_json"])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize(
    ("relative_path", "root_key", "source_system", "match_kind"),
    [
        (
            f"data/notes/{NOTION_EXPORT}/Project.html",
            "notion_export",
            "notion",
            "source",
        ),
        (
            "data/notes/Notes/notion-roadmap.md",
            "capacities_markdown",
            "capacities",
            "source",
        ),
        (
            "data/notes/Backup/Notebook/Section/Planning.one",
            "onenote_backup",
            "onenote",
            "source",
        ),
        (
            "data/note-inventory-20260903-142816/scan.csv",
            "inventory_discovery",
            "inventory_discovery",
            "discovery",
        ),
        (
            f"data/notes/{CAPACITIES_ARCHIVE}",
            "capacities_archive",
            "capacities",
            "archive",
        ),
    ],
)
def test_explicit_source_roots_classify_fixture_paths(
    tmp_path: Path,
    relative_path: str,
    root_key: str,
    source_system: str,
    match_kind: str,
):
    config = load_config(tmp_path)

    match = _classifier()(relative_path, config.source_roots)

    assert match.root is not None
    assert match.root.key == root_key
    assert match.root.source_system == source_system
    assert match.relative_path == relative_path
    assert match.kind == match_kind


def test_root_precedence_does_not_use_filename_heuristics(tmp_path: Path):
    relative_path = "data/notes/Notes/notion-quarterly-plan.md"
    legacy_result = detect_source_system(relative_path)
    classifier = getattr(inventory_module, "classify_root", None)
    assert classifier is not None, (
        "explicit classifier missing; bootstrap filename heuristic returned "
        f"{legacy_result!r} for a Capacities-root file"
    )

    match = classifier(relative_path, load_config(tmp_path).source_roots)

    assert match.root is not None
    assert match.root.key == "capacities_markdown"
    assert match.root.source_system == "capacities"


def test_nested_non_onenote_file_remains_a_residual(tmp_path: Path):
    match = _classifier()(
        "data/notes/Backup/Notebook/readme.txt",
        load_config(tmp_path).source_roots,
    )

    assert match.root is None
    assert match.kind == "residual"


def test_source_and_version_identity_rules(tmp_path: Path):
    root = _prepare_tree(tmp_path)
    config = load_config(root)
    con = connect(config.state_dir / "identity.sqlite")
    relative_path = "data/notes/Notes/notion-roadmap.md"
    source_path = root / relative_path
    try:
        inventory_module.inventory(config, con)
        first_row, first_metadata = _row(con, relative_path)
        first_source_id = first_row["source_id"]
        first_version_id = first_metadata["source_version_id"]
        first_content_hash = first_row["content_sha256"]

        initial_stat = source_path.stat()
        os.utime(
            source_path,
            ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns + 1_000_000_000),
        )
        inventory_module.inventory(config, con)
        touched_row, touched_metadata = _row(con, relative_path)

        source_path.write_text("# Capacity note changed without a rename\n", encoding="utf-8")
        inventory_module.inventory(config, con)
        changed_row, changed_metadata = _row(con, relative_path)
    finally:
        con.close()

    expected_source_id = hashlib.sha256(
        f"source-file:v1:capacities_markdown:{relative_path}".encode("utf-8")
    ).hexdigest()
    expected_first_version_id = hashlib.sha256(
        f"source-version:v1:{expected_source_id}:{first_content_hash}".encode("utf-8")
    ).hexdigest()

    assert first_source_id == expected_source_id
    assert first_version_id == expected_first_version_id
    assert touched_row["source_id"] == first_source_id
    assert touched_metadata["source_version_id"] == first_version_id
    assert changed_row["source_id"] == first_source_id
    assert changed_metadata["source_version_id"] != first_version_id
    assert changed_row["content_sha256"] != first_content_hash


def test_inventory_keeps_discovery_and_finder_metadata_excluded(tmp_path: Path):
    root = _prepare_tree(tmp_path)
    physical_files = sum(path.is_file() for path in (root / "data").rglob("*"))
    config = load_config(root)
    con = connect(config.state_dir / "manifest.sqlite")
    try:
        result = inventory_module.inventory(config, con)
        discovery_row, discovery_metadata = _row(
            con,
            "data/note-inventory-20260903-142816/scan.csv",
        )
        finder_row, finder_metadata = _row(
            con,
            "data/Zoom/2026-09-01 09.00.00 Team Sync/.DS_Store",
        )
    finally:
        con.close()

    assert result["files_present"] == physical_files
    assert result["finder_metadata_files"] == 1
    assert result["substantive_files"] == physical_files - 1
    assert result["zoom_dated_folders"] == 1
    assert discovery_row["source_system"] == "inventory_discovery"
    assert discovery_row["kind"] == "discovery"
    assert discovery_metadata["extraction_status"] == "excluded"
    assert finder_row["kind"] == "metadata"
    assert finder_metadata["extraction_status"] == "excluded"


def test_matching_archives_are_accounted_without_semantic_duplication(tmp_path: Path):
    root = _prepare_tree(tmp_path)
    physical_files = sum(path.is_file() for path in (root / "data").rglob("*"))
    config = load_config(root)
    con = connect(config.state_dir / "archives.sqlite")
    try:
        result = inventory_module.inventory(config, con)
        capacities_row, capacities_metadata = _row(
            con,
            f"data/notes/{CAPACITIES_ARCHIVE}",
        )
        notion_row, notion_metadata = _row(
            con,
            f"data/notes/{NOTION_EXPORT}.zip",
        )
        source_row_count = con.execute(
            "SELECT COUNT(*) FROM source_item WHERE status='present'"
        ).fetchone()[0]
    finally:
        con.close()

    assert source_row_count == physical_files
    assert result["archive_members_listed"] == 3
    assert capacities_row["kind"] == "archive"
    assert notion_row["kind"] == "archive"
    assert capacities_metadata["archive_member_count"] == 2
    assert notion_metadata["archive_member_count"] == 1
    assert capacities_metadata["archive_matches_extracted_root"] is True
    assert notion_metadata["archive_matches_extracted_root"] is True
    assert capacities_metadata["extraction_status"] == "excluded"
    assert notion_metadata["extraction_status"] == "excluded"

    member_rows = _read_csv(config.corpus_dir / "reports" / "archive_members.csv")
    assert len(member_rows) == 3
    assert {row["semantic_status"] for row in member_rows} == {
        "duplicate_of_extracted"
    }


def test_scope_proposals_do_not_promote_uncertain_content():
    classify_scope = _scope_classifier()

    unknown = classify_scope("data/notes/Notes/Untitled.md", "capacities")
    personal = classify_scope("data/notes/Notes/therapy-journal.md", "capacities")
    mixed = classify_scope("data/notes/Notes/work-therapy-plan.md", "capacities")
    formal = classify_scope("data/approved/review.pdf", "formal_records")

    assert (unknown.scope, personal.scope, mixed.scope, formal.scope) == (
        "Unknown",
        "Personal",
        "Mixed",
        "Work",
    )
    assert all(proposal.reason for proposal in (unknown, personal, mixed, formal))


def test_manifest_report_is_derived_and_preserves_reviewed_inventory(tmp_path: Path):
    root = _prepare_tree(tmp_path)
    reviewed_manifest = root / "01_INVENTORY" / "source_manifest.csv"
    reviewed_manifest.parent.mkdir()
    reviewed_manifest.write_text("reviewed,do-not-overwrite\n", encoding="utf-8")
    before = reviewed_manifest.read_bytes()
    config = load_config(root)
    con = connect(config.state_dir / "report.sqlite")
    try:
        result = inventory_module.inventory(config, con)
    finally:
        con.close()

    manifest_path = config.corpus_dir / "reports" / "source_manifest.csv"
    assert Path(result["manifest"]) == manifest_path
    assert manifest_path.is_file()
    assert not (config.corpus_dir / "source_manifest.csv").exists()
    assert reviewed_manifest.read_bytes() == before

    manifest_rows = _read_csv(manifest_path)
    assert manifest_rows
    assert {
        "source_id",
        "source_version_id",
        "source_root_key",
        "relative_path",
        "source_system",
        "kind",
        "scope_proposal",
        "scope_reason",
        "extraction_status",
        "archive_member_count",
    }.issubset(manifest_rows[0])

    residual_rows = _read_csv(
        config.corpus_dir / "reports" / "source_root_residuals.csv"
    )
    assert {row["relative_path"] for row in residual_rows} == {
        "data/formal-candidate/performance-review.pdf",
        "data/notes/Backup/Notebook/readme.txt",
    }
    assert {row["source_system"] for row in residual_rows} == {"unclassified"}
