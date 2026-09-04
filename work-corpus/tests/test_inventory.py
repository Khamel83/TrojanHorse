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
import work_corpus.transcription as transcription_module
from work_corpus.config import load_config
from work_corpus.db import connect
from work_corpus.normalize import normalize_all
from work_corpus.transcription import transcribe_jobs
from work_corpus.util import (
    detect_source_system,
    stable_source_id,
    stable_source_version_id,
    stable_evidence_id,
)
from work_corpus.zoom import scan_zoom


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
        "SELECT * FROM source_record WHERE relative_path=?",
        (relative_path,),
    ).fetchone()
    assert row is not None, f"manifest row not found: {relative_path}"
    return row, json.loads(row["metadata_json"])


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _legacy_source_id(
    relative_path: str,
    size_bytes: int,
    mtime_ns: int,
    content_hash: str,
) -> str:
    basis = f"{relative_path}\0{size_bytes}\0{mtime_ns}\0{content_hash}"
    return "src_" + hashlib.blake2b(
        basis.encode("utf-8"),
        digest_size=16,
    ).hexdigest()


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


@pytest.mark.parametrize(
    ("relative_path", "expected_root"),
    [
        ("data/Zoom/2026-09-01 09.00.00 Team Sync/audio.m4a", "zoom"),
        ("data/notes/Notes/quarterly-plan.md", "capacities_markdown"),
        (f"data/notes/{NOTION_EXPORT}/Project.html", "notion_export"),
        ("data/notes/Backup/Notebook/Planning.one", "onenote_backup"),
        ("data/note-inventory-20260903-142816/scan.csv", "inventory_discovery"),
    ],
)
def test_known_roots_precede_overlapping_configured_formal_root(
    tmp_path: Path,
    relative_path: str,
    expected_root: str,
):
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "source_roots": {
                    "formal_records": {
                        "path": "data",
                        "source_system": "formal_records",
                        "precedence": -100,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_config(tmp_path)

    known_match = _classifier()(relative_path, config.source_roots)
    residual_match = _classifier()(
        "data/formal-candidate/performance-review.pdf",
        config.source_roots,
    )

    assert known_match.root is not None
    assert known_match.root.key == expected_root
    assert residual_match.root is not None
    assert residual_match.root.key == "formal_records"


def test_zoom_example_uses_canonical_path_spelling(tmp_path: Path):
    default_zoom = load_config(tmp_path).source_root("zoom")
    shipped_path = Path(__file__).parents[1] / "config.json"
    example_path = Path(__file__).parents[1] / "config.local.example.json"
    shipped = json.loads(shipped_path.read_text(encoding="utf-8"))
    example = json.loads(example_path.read_text(encoding="utf-8"))

    assert default_zoom.relative_path == "data/Zoom"
    assert shipped["source_roots"]["zoom"] == "data/Zoom"
    assert example["source_roots"]["zoom"] == "data/Zoom"


def test_nested_non_onenote_file_remains_a_residual(tmp_path: Path):
    match = _classifier()(
        "data/notes/Backup/Notebook/readme.txt",
        load_config(tmp_path).source_roots,
    )

    assert match.root is None
    assert match.kind == "residual"


def test_residual_work_proposal_requires_explicit_root_before_normalization(
    tmp_path: Path,
):
    source_path = tmp_path / "data" / "residual" / "performance-review.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("# Synthetic residual work proposal\n", encoding="utf-8")
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"normalization": {"skip_classifications": []}}),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "residual-scope.sqlite")
    try:
        inventory_module.inventory(config, con)
        source, metadata = _row(
            con,
            "data/residual/performance-review.md",
        )
        result = normalize_all(config, con)
        normalized = con.execute(
            "SELECT status, normalized_path FROM normalized_document WHERE source_id=?",
            (source["source_id"],),
        ).fetchone()
    finally:
        con.close()

    assert source["classification"] == "Work"
    assert metadata["root_match_kind"] == "residual"
    assert result["normalized"] == 0
    assert result["review_required"] == 1
    assert normalized["status"] == "review_required"
    assert normalized["normalized_path"] is None


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


def test_source_version_and_normalized_history_survive_changed_bytes(tmp_path: Path):
    root = _prepare_tree(tmp_path)
    relative_path = "data/notes/Notes/work-project-roadmap.md"
    source_path = root / relative_path
    source_path.write_text("# Work project roadmap\n", encoding="utf-8")
    config = load_config(root)
    con = connect(config.state_dir / "version-history.sqlite")
    try:
        inventory_module.inventory(config, con)
        first_row, first_metadata = _row(con, relative_path)
        first_version_id = first_metadata["source_version_id"]
        normalize_all(config, con)
        first_normalized = con.execute(
            """
            SELECT source_version_id, normalized_path, status
            FROM normalized_document
            WHERE source_id=?
            """,
            (first_row["source_id"],),
        ).fetchone()
        assert first_normalized is not None
        first_output = Path(first_normalized["normalized_path"])
        first_output_bytes = first_output.read_bytes()

        initial_stat = source_path.stat()
        os.utime(
            source_path,
            ns=(initial_stat.st_atime_ns, initial_stat.st_mtime_ns + 1_000_000_000),
        )
        inventory_module.inventory(config, con)
        normalize_all(config, con)

        source_path.write_text(
            "# Capacity note changed without a rename\n",
            encoding="utf-8",
        )
        inventory_module.inventory(config, con)
        changed_row, changed_metadata = _row(con, relative_path)
        normalize_all(config, con)

        version_rows = con.execute(
            """
            SELECT source_version_id, content_sha256
            FROM source_version
            WHERE source_id=?
            ORDER BY first_seen, source_version_id
            """,
            (first_row["source_id"],),
        ).fetchall()
        normalized_rows = con.execute(
            """
            SELECT source_version_id, normalized_path, status
            FROM normalized_document
            WHERE source_id=?
            ORDER BY source_version_id
            """,
            (first_row["source_id"],),
        ).fetchall()
    finally:
        con.close()

    assert first_row["source_version_id"] == first_version_id
    assert first_row["extraction_status"] == "ready"
    assert changed_row["source_id"] == first_row["source_id"]
    assert changed_metadata["source_version_id"] != first_version_id
    assert {row["source_version_id"] for row in version_rows} == {
        first_version_id,
        changed_metadata["source_version_id"],
    }
    assert len(version_rows) == 2
    assert len(normalized_rows) == 2
    statuses_by_version = {
        row["source_version_id"]: row["status"] for row in normalized_rows
    }
    assert statuses_by_version == {
        first_version_id: "prior_good_retained",
        changed_metadata["source_version_id"]: "normalized",
    }
    assert len({row["normalized_path"] for row in normalized_rows}) == 2
    assert first_output.read_bytes() == first_output_bytes
    assert all(Path(row["normalized_path"]).is_file() for row in normalized_rows)


@pytest.mark.parametrize(
    ("file_name", "expected_scope"),
    [
        ("therapy-journal.md", "Personal"),
        ("work-therapy-plan.md", "Mixed"),
        ("untitled.md", "Unknown"),
    ],
)
def test_default_normalization_fails_closed_for_canonical_non_work_scopes(
    tmp_path: Path,
    file_name: str,
    expected_scope: str,
):
    relative_path = f"data/notes/Notes/{file_name}"
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text("Private synthetic journal entry.\n", encoding="utf-8")
    config = load_config(tmp_path)
    con = connect(config.state_dir / "scope-boundary.sqlite")
    try:
        inventory_module.inventory(config, con)
        source, metadata = _row(con, relative_path)

        result = normalize_all(config, con)
        normalized_rows = con.execute(
            """
            SELECT normalized_path, status
            FROM normalized_document
            WHERE source_id=?
            """,
            (source["source_id"],),
        ).fetchall()
    finally:
        con.close()

    assert source["classification"] == expected_scope
    assert source["content_sha256"]
    assert source["source_version_id"]
    assert metadata["extraction_status"] == "ready"
    assert result == {
        "normalized": 0,
        "skipped_unchanged": 0,
        "review_required": 1,
        "unsupported": 0,
        "errors": 0,
    }
    assert len(normalized_rows) == 1
    assert normalized_rows[0]["status"] == "review_required"
    assert normalized_rows[0]["normalized_path"] is None
    assert not list((config.corpus_dir / "normalized").rglob("*.md"))


@pytest.mark.parametrize(
    "config_name",
    ["config.json", "config.local.example.json"],
)
def test_shipped_config_keeps_canonical_non_work_scopes_fail_closed(
    config_name: str,
):
    config_path = Path(__file__).parents[1] / config_name
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert {"Personal", "Mixed", "Unknown"} <= set(
        payload["normalization"]["skip_classifications"]
    )


def test_zoom_personal_indicator_precedes_trusted_work_source(tmp_path: Path):
    relative_path = (
        "data/Zoom/2026-09-01 09.00.00 Therapy Session/"
        "therapy-transcript.vtt"
    )
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nSynthetic private session.\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom-scope.sqlite")
    try:
        inventory_module.inventory(config, con)
        source, metadata = _row(con, relative_path)
        result = normalize_all(config, con)
        zoom_result = scan_zoom(config, con)
        normalized = con.execute(
            """
            SELECT normalized_path, status
            FROM normalized_document
            WHERE source_id=?
            """,
            (source["source_id"],),
        ).fetchone()
        meeting_group = con.execute(
            "SELECT status FROM meeting_group"
        ).fetchone()
    finally:
        con.close()

    assert source["source_system"] == "zoom"
    assert source["classification"] == "Mixed"
    assert metadata["scope_proposal"] == "Mixed"
    assert result == {
        "normalized": 0,
        "skipped_unchanged": 0,
        "review_required": 1,
        "unsupported": 0,
        "errors": 0,
    }
    assert zoom_result["meeting_folders"] == 1
    assert zoom_result["with_existing_transcript"] == 0
    assert zoom_result["queued_for_transcription"] == 0
    assert meeting_group["status"] == "needs_review"
    assert normalized["status"] == "review_required"
    assert normalized["normalized_path"] is None
    assert not list((config.corpus_dir / "transcripts" / "zoom").rglob("*.md"))


def test_zoom_scope_gate_blocks_sibling_media_and_pending_job(tmp_path: Path):
    folder = "data/Zoom/2026-09-02 10.00.00 Team Sync"
    media_path = tmp_path / folder / "meeting.m4a"
    transcript_path = tmp_path / folder / "therapy-transcript.vtt"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"synthetic media bytes")
    transcript_path.write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nPrivate synthetic session.\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom-group-scope.sqlite")
    try:
        inventory_module.inventory(config, con)
        media, _ = _row(con, f"{folder}/meeting.m4a")
        scan_result = scan_zoom(config, con)
        group = con.execute(
            "SELECT group_id, status, media_source_id, transcript_source_id "
            "FROM meeting_group"
        ).fetchone()
        job_id = "synthetic-pending-job"
        con.execute(
            """
            INSERT INTO transcription_job (
                job_id, group_id, media_source_id, output_stem,
                engine, model, status, error, created_at
            ) VALUES (?, ?, ?, ?, NULL, NULL, 'pending', NULL, ?)
            """,
            (
                job_id,
                group["group_id"],
                media["source_id"],
                str(config.corpus_dir / "transcripts" / "zoom" / "generated" / group["group_id"]),
                "2026-09-04T00:00:00Z",
            ),
        )
        con.commit()
        tx_result = transcribe_jobs(config, con)
        job = con.execute(
            "SELECT status, error FROM transcription_job WHERE job_id=?",
            (job_id,),
        ).fetchone()
    finally:
        con.close()

    assert scan_result["meeting_folders"] == 1
    assert scan_result["queued_for_transcription"] == 0
    assert group["status"] == "needs_review"
    assert group["media_source_id"] == media["source_id"]
    assert group["transcript_source_id"]
    assert tx_result == {"attempted": 0, "complete": 0, "errors": 0}
    assert job["status"] == "needs_review"
    assert job["error"]


def test_zoom_meeting_boundary_blocks_nested_personal_sibling(tmp_path: Path):
    meeting = "data/Zoom/2026-09-03 10.00.00 Team Sync"
    media_path = tmp_path / meeting / "audio" / "meeting.m4a"
    transcript_path = tmp_path / meeting / "notes" / "therapy-transcript.vtt"
    media_path.parent.mkdir(parents=True)
    transcript_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"synthetic nested media bytes")
    transcript_path.write_text(
        "WEBVTT\n\n00:00.000 --> 00:01.000\nPrivate nested session.\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom-nested-scope.sqlite")
    try:
        inventory_module.inventory(config, con)
        result = scan_zoom(config, con)
        groups = con.execute(
            "SELECT folder_relative_path, status FROM meeting_group"
        ).fetchall()
        jobs = con.execute(
            "SELECT status FROM transcription_job"
        ).fetchall()
    finally:
        con.close()

    assert result["meeting_folders"] == 1
    assert result["queued_for_transcription"] == 0
    assert len(groups) == 1
    assert groups[0]["folder_relative_path"] == meeting
    assert groups[0]["status"] == "needs_review"
    assert jobs == []


def test_transcribe_jobs_processes_eligible_media(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    meeting = "data/Zoom/2026-09-04 11.00.00 Team Sync"
    media_path = tmp_path / meeting / "meeting.m4a"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"synthetic eligible media bytes")
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom-positive.sqlite")
    try:
        inventory_module.inventory(config, con)
        scan_result = scan_zoom(config, con)

        def fake_engine(_config, _requested):
            return "custom", ""

        def fake_custom(_config, _media_path, output_stem):
            vtt_path = Path(str(output_stem) + ".vtt")
            txt_path = Path(str(output_stem) + ".txt")
            vtt_path.parent.mkdir(parents=True, exist_ok=True)
            vtt_path.write_text(
                "WEBVTT\n\n00:00.000 --> 00:01.000\nSynthetic work meeting.\n",
                encoding="utf-8",
            )
            txt_path.write_text("Synthetic work meeting.\n", encoding="utf-8")
            return vtt_path, txt_path

        monkeypatch.setattr(
            transcription_module,
            "_engine_available",
            fake_engine,
        )
        monkeypatch.setattr(
            transcription_module,
            "_transcribe_custom",
            fake_custom,
        )
        tx_result = transcribe_jobs(config, con, requested_engine="custom")
        job = con.execute(
            "SELECT status FROM transcription_job"
        ).fetchone()
        group = con.execute(
            "SELECT status, transcript_path FROM meeting_group"
        ).fetchone()
    finally:
        con.close()

    assert scan_result["queued_for_transcription"] == 1
    assert tx_result == {"attempted": 1, "complete": 1, "errors": 0}
    assert job["status"] == "complete"
    assert group["status"] == "generated_transcript"
    assert group["transcript_path"]


def test_explicit_scope_override_remains_active(tmp_path: Path):
    relative_path = "data/notes/Notes/untitled.md"
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text("# Explicit synthetic override\n", encoding="utf-8")
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"normalization": {"skip_classifications": []}}),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "scope-override.sqlite")
    try:
        inventory_module.inventory(config, con)
        source, _ = _row(con, relative_path)
        first_result = normalize_all(config, con)
        inventory_module.inventory(config, con)
        normalized = con.execute(
            """
            SELECT status, normalized_path
            FROM normalized_document
            WHERE source_id=?
            """,
            (source["source_id"],),
        ).fetchone()
        database = config.state_dir / "scope-override.sqlite"
        con.close()
        con = connect(
            database,
            skip_classifications=config.get(
                "normalization",
                "skip_classifications",
            ),
        )
        reopened = con.execute(
            "SELECT status FROM normalized_document WHERE source_id=?",
            (source["source_id"],),
        ).fetchone()
    finally:
        if con:
            con.close()

    assert source["classification"] == "Unknown"
    assert first_result["normalized"] == 1
    assert normalized["status"] == "normalized"
    assert normalized["normalized_path"]
    assert reopened["status"] == "normalized"


def test_ineligible_rescan_retires_prior_normalized_output(tmp_path: Path):
    relative_path = "data/notes/Notes/work-project-retrospective.md"
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_text("# Work project retrospective\n", encoding="utf-8")
    config = load_config(tmp_path)
    con = connect(config.state_dir / "ineligible-transition.sqlite")
    try:
        inventory_module.inventory(config, con)
        initial_source, _ = _row(con, relative_path)
        initial_version_id = initial_source["source_version_id"]
        first_result = normalize_all(config, con)
        initial_normalized = con.execute(
            """
            SELECT source_version_id, normalized_path, status
            FROM normalized_document
            WHERE source_id=?
            """,
            (initial_source["source_id"],),
        ).fetchone()
        assert initial_normalized is not None
        retained_path = Path(initial_normalized["normalized_path"])
        retained_bytes = retained_path.read_bytes()

        config_dir = tmp_path / "work-corpus"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps({"inventory": {"hash_files_up_to_mb": 0}}),
            encoding="utf-8",
        )
        ineligible_config = load_config(tmp_path)
        inventory_module.inventory(ineligible_config, con)

        current_source, current_metadata = _row(con, relative_path)
        rows_after_scan = con.execute(
            """
            SELECT source_version_id, normalized_path, status, error
            FROM normalized_document
            WHERE source_id=?
            """,
            (initial_source["source_id"],),
        ).fetchall()
        version_count = con.execute(
            """
            SELECT COUNT(*)
            FROM source_version
            WHERE source_id=? AND source_version_id=?
            """,
            (initial_source["source_id"], initial_version_id),
        ).fetchone()[0]

        second_result = normalize_all(ineligible_config, con)
        active_after_normalize = con.execute(
            """
            SELECT COUNT(*)
            FROM normalized_document
            WHERE source_id=? AND status='normalized'
            """,
            (initial_source["source_id"],),
        ).fetchone()[0]
    finally:
        con.close()

    assert first_result["normalized"] == 1
    assert initial_normalized["status"] == "normalized"
    assert initial_normalized["source_version_id"] == initial_version_id
    assert current_source["content_sha256"] is None
    assert current_source["source_version_id"] is None
    assert current_metadata["extraction_status"] == "inventory_only"
    assert len(rows_after_scan) == 1
    assert rows_after_scan[0]["status"] == "prior_good_retained"
    assert rows_after_scan[0]["error"]
    assert Path(rows_after_scan[0]["normalized_path"]) == retained_path
    assert retained_path.read_bytes() == retained_bytes
    assert version_count == 1
    assert second_result == {
        "normalized": 0,
        "skipped_unchanged": 0,
        "review_required": 0,
        "unsupported": 0,
        "errors": 0,
    }
    assert active_after_normalize == 0


def test_normalization_excludes_non_evidence_and_unhashed_inventory_rows(
    tmp_path: Path,
):
    root = _prepare_tree(tmp_path)
    config_dir = root / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"inventory": {"hash_files_up_to_mb": 0}}),
        encoding="utf-8",
    )
    config = load_config(root)
    con = connect(config.state_dir / "normalization-boundary.sqlite")
    try:
        inventory_module.inventory(config, con)
        rows = con.execute(
            "SELECT source_id, relative_path, content_sha256, metadata_json FROM source_record"
        ).fetchall()
        blocked = {
            row["source_id"]: json.loads(row["metadata_json"])["extraction_status"]
            for row in rows
        }
        result = normalize_all(config, con)
        normalized_source_ids = {
            row[0] for row in con.execute("SELECT source_id FROM normalized_document")
        }
    finally:
        con.close()

    assert set(blocked.values()) <= {"excluded", "inventory_only"}
    assert any(status == "excluded" for status in blocked.values())
    assert any(status == "inventory_only" for status in blocked.values())
    assert all(row["content_sha256"] is None for row in rows)
    assert normalized_source_ids.isdisjoint(blocked)
    assert result == {
        "normalized": 0,
        "skipped_unchanged": 0,
        "review_required": 0,
        "unsupported": 0,
        "errors": 0,
    }


def test_connect_migrates_versioned_normalization_without_losing_legacy_row(
    tmp_path: Path,
):
    database = tmp_path / "legacy.sqlite"
    relative_path = "data/Zoom/2026-09-01 09.00.00 Team Sync/legacy.md"
    content_hash = hashlib.sha256(b"legacy source bytes").hexdigest()
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"legacy source bytes")
    os.utime(source_path, ns=(123, 123))
    source_id = _legacy_source_id(
        relative_path,
        source_path.stat().st_size,
        123,
        content_hash,
    )
    expected_version_id = stable_source_version_id(source_id, content_hash)
    normalized_path = tmp_path / "legacy-normalized.md"
    normalized_path.write_text("legacy normalized bytes\n", encoding="utf-8")
    raw = sqlite3.connect(database)
    try:
        raw.executescript(
            """
            CREATE TABLE source_record (
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
            CREATE TABLE normalized_document (
                source_id TEXT PRIMARY KEY REFERENCES source_record(source_id),
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
            """
        )
        raw.execute(
            """
            INSERT INTO source_record (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, content_sha256,
                classification, status, first_seen, last_seen, metadata_json
                ) VALUES (?, ?, ?, 'zoom', 'document', '.md', 19, 123, ?,
                      'Unknown', 'present', '2026-09-04T00:00:00Z',
                      '2026-09-04T00:00:00Z', ?)
            """,
            (
                source_id,
                relative_path,
                str(source_path),
                content_hash,
                json.dumps({}),
            ),
        )
        raw.execute(
            """
            INSERT INTO normalized_document (
                source_id, normalized_path, parser, source_mtime_ns,
                char_count, line_count, content_sha256, status, updated_at
            ) VALUES (?, ?, 'plain_text', 123, 24, 2, ?, 'normalized',
                      '2026-09-04T00:00:00Z')
            """,
            (source_id, str(normalized_path), hashlib.sha256(b"derived").hexdigest()),
        )
        raw.commit()
    finally:
        raw.close()

    con = connect(database)
    try:
        source = con.execute(
            "SELECT source_version_id, extraction_status FROM source_record"
        ).fetchone()
        version = con.execute("SELECT * FROM source_version").fetchone()
        normalized = con.execute("SELECT * FROM normalized_document").fetchone()
        normalized_columns = {
            row["name"]: row["pk"]
            for row in con.execute("PRAGMA table_info(normalized_document)")
        }
        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, media_source_id,
                transcript_source_id, transcript_path, status,
                duration_seconds, updated_at
            ) VALUES (
                'legacy-group', 'data/Zoom/2026-09-01 09.00.00 Team Sync',
                ?, ?, NULL, 'existing_transcript', NULL, '2026-09-04T00:00:00Z'
            )
            """,
            (source_id, source_id),
        )
        con.execute(
            """
            INSERT INTO transcription_job (
                job_id, group_id, media_source_id, output_stem,
                engine, model, status, error, created_at
            ) VALUES (
                'legacy-job', 'legacy-group', ?, 'legacy-output',
                NULL, NULL, 'error', 'legacy fixture', '2026-09-04T00:00:00Z'
            )
            """,
            (source_id,),
        )
        con.commit()
        config = load_config(tmp_path)
        inventory_module.inventory(config, con)
        current_source = con.execute(
            "SELECT * FROM source_record WHERE relative_path=?",
            (relative_path,),
        ).fetchone()
        current_version = con.execute(
            "SELECT * FROM source_version WHERE source_id=?",
            (current_source["source_id"],),
        ).fetchone()
        current_normalized = con.execute(
            "SELECT * FROM normalized_document WHERE source_id=?",
            (current_source["source_id"],),
        ).fetchone()
        zoom_group_refs = con.execute(
            "SELECT media_source_id, transcript_source_id FROM meeting_group "
            "WHERE group_id='legacy-group'"
        ).fetchone()
        transcription_ref = con.execute(
            "SELECT media_source_id FROM transcription_job "
            "WHERE job_id='legacy-job'"
        ).fetchone()
    finally:
        con.close()

    assert expected_version_id is not None
    assert source["source_version_id"] == expected_version_id
    assert source["extraction_status"] == "inventory_only"
    assert version["source_version_id"] == expected_version_id
    assert version["source_id"] == source_id
    assert normalized["source_version_id"] == expected_version_id
    assert normalized["source_id"] == source_id
    assert normalized["normalized_path"] == str(normalized_path)
    assert normalized["status"] == "prior_good_retained"
    assert normalized_columns["source_version_id"] == 1
    assert normalized_columns["source_id"] == 0

    canonical_source_id = stable_source_id(
        "zoom",
        relative_path,
    )
    canonical_version_id = stable_source_version_id(
        canonical_source_id,
        content_hash,
    )
    assert current_source["source_id"] == canonical_source_id
    assert current_source["relative_path"] == relative_path
    assert current_source["source_version_id"] == canonical_version_id
    assert current_version["source_version_id"] == canonical_version_id
    assert current_version["source_id"] == canonical_source_id
    assert current_normalized["source_version_id"] == canonical_version_id
    assert current_normalized["source_id"] == canonical_source_id
    assert current_normalized["normalized_path"] == str(normalized_path)
    assert current_normalized["status"] == "prior_good_retained"
    assert zoom_group_refs["media_source_id"] == canonical_source_id
    assert zoom_group_refs["transcript_source_id"] == canonical_source_id
    assert transcription_ref["media_source_id"] == canonical_source_id


def test_connect_drops_obsolete_intermediate_legacy_table(tmp_path: Path):
    database = tmp_path / "intermediate.sqlite"
    con = connect(database)
    con.close()

    raw = sqlite3.connect(database)
    try:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.execute(
            "CREATE TABLE normalized_document_legacy ("
            "source_id TEXT PRIMARY KEY REFERENCES source_record(source_id))"
        )
        raw.commit()
    finally:
        raw.close()

    con = connect(database)
    try:
        legacy_table = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='normalized_document_legacy'"
        ).fetchone()
    finally:
        con.close()

    assert legacy_table is None


def test_connect_preserves_hashless_legacy_normalized_output(tmp_path: Path):
    database = tmp_path / "legacy-unhashed.sqlite"
    normalized_path = tmp_path / "legacy-unhashed.md"
    normalized_path.write_text("legacy hashless output\n", encoding="utf-8")
    raw = sqlite3.connect(database)
    try:
        raw.executescript(
            """
            CREATE TABLE source_record (
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
            CREATE TABLE normalized_document (
                source_id TEXT PRIMARY KEY REFERENCES source_record(source_id),
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
            """
        )
        raw.execute(
            """
            INSERT INTO source_record (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, classification,
                status, first_seen, last_seen, metadata_json
            ) VALUES (
                'legacy-unhashed', 'data/notes/Notes/unhashed.md', '', 'capacities',
                'document', '.md', 0, 123, 'Unknown', 'present',
                '2026-09-04T00:00:00Z', '2026-09-04T00:00:00Z', '{}'
            )
            """
        )
        raw.execute(
            """
            INSERT INTO normalized_document (
                source_id, normalized_path, parser, source_mtime_ns,
                char_count, line_count, content_sha256, status, updated_at
            ) VALUES (
                'legacy-unhashed', ?, 'plain_text', 123, 24, 2, NULL,
                'normalized', '2026-09-04T00:00:00Z'
            )
            """,
            (str(normalized_path),),
        )
        raw.commit()
    finally:
        raw.close()

    con = connect(database)
    try:
        current = con.execute(
            "SELECT COUNT(*) FROM normalized_document"
        ).fetchone()[0]
        legacy = con.execute(
            "SELECT normalized_path, status FROM normalized_document_legacy"
        ).fetchone()
    finally:
        con.close()

    assert current == 0
    assert legacy["normalized_path"] == str(normalized_path)
    assert legacy["status"] == "normalized"


def test_connect_retains_nonempty_intermediate_legacy_table(tmp_path: Path):
    database = tmp_path / "intermediate-nonempty.sqlite"
    con = connect(database)
    con.close()

    normalized_path = tmp_path / "intermediate-legacy.md"
    normalized_path.write_text("intermediate legacy output\n", encoding="utf-8")
    raw = sqlite3.connect(database)
    try:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.execute(
            """
            INSERT INTO source_record (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, status, first_seen, last_seen
            ) VALUES (
                'intermediate-source', 'data/notes/Notes/intermediate.md', '',
                'capacities', 'document', '.md', 0, 123, 'present',
                '2026-09-04T00:00:00Z', '2026-09-04T00:00:00Z'
            )
            """
        )
        raw.execute(
            """
            CREATE TABLE normalized_document_legacy (
                source_id TEXT PRIMARY KEY REFERENCES source_record(source_id),
                normalized_path TEXT,
                parser TEXT,
                source_mtime_ns INTEGER,
                char_count INTEGER,
                line_count INTEGER,
                content_sha256 TEXT,
                status TEXT NOT NULL,
                error TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        raw.execute(
            """
            INSERT INTO normalized_document_legacy (
                source_id, normalized_path, parser, source_mtime_ns,
                char_count, line_count, content_sha256, status, updated_at
            ) VALUES (
                'intermediate-source', ?, 'plain_text', 123, 28, 2, NULL,
                'normalized', '2026-09-04T00:00:00Z'
            )
            """,
            (str(normalized_path),),
        )
        raw.commit()
    finally:
        raw.close()

    con = connect(database)
    try:
        legacy = con.execute(
            "SELECT normalized_path, status FROM normalized_document_legacy"
        ).fetchone()
    finally:
        con.close()

    assert legacy["normalized_path"] == str(normalized_path)
    assert legacy["status"] == "normalized"


def test_connect_preserves_conflicting_intermediate_legacy_row(tmp_path: Path):
    database = tmp_path / "intermediate-conflict.sqlite"
    source_id = "intermediate-conflict-source"
    content_hash = hashlib.sha256(b"source bytes").hexdigest()
    version_id = stable_source_version_id(source_id, content_hash)
    current_path = tmp_path / "current-normalized.md"
    legacy_path = tmp_path / "legacy-normalized.md"
    current_path.write_text("current output\n", encoding="utf-8")
    legacy_path.write_text("legacy output\n", encoding="utf-8")

    con = connect(database)
    try:
        con.execute(
            """
            INSERT INTO source_record (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, content_sha256,
                source_version_id, classification, extraction_status,
                status, first_seen, last_seen, metadata_json
            ) VALUES (
                ?, 'data/notes/Notes/conflict.md', '', 'capacities', 'document',
                '.md', 12, 123, ?, ?, 'Work', 'ready', 'present',
                '2026-09-04T00:00:00Z', '2026-09-04T00:00:00Z', '{}'
            )
            """,
            (source_id, content_hash, version_id),
        )
        con.execute(
            """
            INSERT INTO source_version (
                source_version_id, source_id, content_sha256, size_bytes,
                mtime_ns, first_seen, last_seen
            ) VALUES (?, ?, ?, 12, 123, '2026-09-04T00:00:00Z',
                      '2026-09-04T00:00:00Z')
            """,
            (version_id, source_id, content_hash),
        )
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, normalized_path, parser,
                source_mtime_ns, char_count, line_count, content_sha256,
                status, error, updated_at
            ) VALUES (?, ?, ?, 'plain_text', 123, 14, 2, ?, 'normalized',
                      NULL, '2026-09-04T00:00:00Z')
            """,
            (
                version_id,
                source_id,
                str(current_path),
                hashlib.sha256(b"current output\n").hexdigest(),
            ),
        )
        con.commit()
    finally:
        con.close()

    raw = sqlite3.connect(database)
    try:
        raw.execute("PRAGMA foreign_keys=ON")
        raw.execute(
            """
            CREATE TABLE normalized_document_legacy (
                source_id TEXT PRIMARY KEY REFERENCES source_record(source_id),
                normalized_path TEXT,
                parser TEXT,
                source_mtime_ns INTEGER,
                char_count INTEGER,
                line_count INTEGER,
                content_sha256 TEXT,
                status TEXT NOT NULL,
                error TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        raw.execute(
            """
            INSERT INTO normalized_document_legacy (
                source_id, normalized_path, parser, source_mtime_ns,
                char_count, line_count, content_sha256, status, updated_at
            ) VALUES (?, ?, 'plain_text', 123, 13, 2, ?, 'normalized',
                      '2026-09-04T00:00:00Z')
            """,
            (
                source_id,
                str(legacy_path),
                hashlib.sha256(b"legacy output\n").hexdigest(),
            ),
        )
        raw.commit()
    finally:
        raw.close()

    con = connect(database)
    try:
        current = con.execute(
            "SELECT normalized_path FROM normalized_document "
            "WHERE source_version_id=?",
            (version_id,),
        ).fetchone()
        legacy = con.execute(
            "SELECT normalized_path FROM normalized_document_legacy "
            "WHERE source_id=?",
            (source_id,),
        ).fetchone()
    finally:
        con.close()

    assert current["normalized_path"] == str(current_path)
    assert legacy["normalized_path"] == str(legacy_path)


def test_rekey_preserves_conflicting_normalized_output(tmp_path: Path):
    database = tmp_path / "rekey-conflict.sqlite"
    old_source_id = "legacy-rekey-source"
    new_source_id = "canonical-rekey-source"
    content_hash = hashlib.sha256(b"rekey source bytes").hexdigest()
    old_version_id = stable_source_version_id(old_source_id, content_hash)
    new_version_id = stable_source_version_id(new_source_id, content_hash)
    old_output = tmp_path / "old-output.md"
    current_output = tmp_path / "current-output.md"
    old_output.write_text("old output\n", encoding="utf-8")
    current_output.write_text("current output\n", encoding="utf-8")

    con = connect(database)
    try:
        for source_id, relative_path, version_id in (
            (
                old_source_id,
                "data/Zoom/2026-09-04 12.00.00 Team Sync/meeting.md",
                old_version_id,
            ),
            (
                new_source_id,
                "data/Zoom/other-meeting/meeting.md",
                new_version_id,
            ),
        ):
            con.execute(
                """
                INSERT INTO source_record (
                    source_id, relative_path, absolute_path, source_system, kind,
                    extension, size_bytes, mtime_ns, content_sha256,
                    source_version_id, classification, extraction_status, status,
                    first_seen, last_seen, metadata_json
                ) VALUES (?, ?, '', 'zoom', 'document', '.md', 18, 123, ?, ?,
                          'Work', 'ready', 'present',
                          '2026-09-04T00:00:00Z', '2026-09-04T00:00:00Z', '{}')
                """,
                (source_id, relative_path, content_hash, version_id),
            )
            con.execute(
                """
                INSERT INTO source_version (
                    source_version_id, source_id, content_sha256, size_bytes,
                    mtime_ns, first_seen, last_seen
                ) VALUES (?, ?, ?, 18, 123, '2026-09-04T00:00:00Z',
                          '2026-09-04T00:00:00Z')
                """,
                (version_id, source_id, content_hash),
            )
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, normalized_path, parser,
                source_mtime_ns, char_count, line_count, content_sha256,
                status, error, updated_at
            ) VALUES (?, ?, ?, 'plain_text', 123, 11, 2, ?, 'normalized',
                      NULL, '2026-09-04T00:00:00Z')
            """,
            (
                old_version_id,
                old_source_id,
                str(old_output),
                hashlib.sha256(b"old output\n").hexdigest(),
            ),
        )
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, normalized_path, parser,
                source_mtime_ns, char_count, line_count, content_sha256,
                status, error, updated_at
            ) VALUES (?, ?, ?, 'plain_text', 123, 15, 2, ?, 'normalized',
                      NULL, '2026-09-04T00:00:00Z')
            """,
            (
                new_version_id,
                new_source_id,
                str(current_output),
                hashlib.sha256(b"current output\n").hexdigest(),
            ),
        )
        con.commit()
        inventory_module._rekey_legacy_source(con, old_source_id, new_source_id)
        con.commit()
        current = con.execute(
            "SELECT normalized_path FROM normalized_document WHERE source_version_id=?",
            (new_version_id,),
        ).fetchone()
        legacy = con.execute(
            "SELECT normalized_path FROM normalized_document_rekey_conflict "
            "WHERE old_source_id=? AND new_source_id=?",
            (old_source_id, new_source_id),
        ).fetchone()
    finally:
        con.close()

    assert current["normalized_path"] == str(current_output)
    assert legacy["normalized_path"] == str(old_output)


def test_evidence_identity_requires_version_and_locator():
    source_version_id = "version-for-evidence"
    locator = "line:12"
    expected = hashlib.sha256(
        f"evidence:v1:{source_version_id}:{locator}".encode("utf-8")
    ).hexdigest()

    assert stable_evidence_id(source_version_id, locator) == expected
    with pytest.raises(ValueError, match="source version"):
        stable_evidence_id("", locator)


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
            "SELECT COUNT(*) FROM source_record WHERE status='present'"
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
