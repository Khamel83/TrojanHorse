from __future__ import annotations

import json
import importlib
import shutil
import sqlite3
import sys
from pathlib import Path
import zipfile
from typing import Optional

import pytest

import work_corpus.inventory as inventory_module
import work_corpus.normalize as normalize_module
from work_corpus.config import load_config
from work_corpus.db import connect
from work_corpus.util import provenance_header, scrub_derived_text, stable_evidence_id


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "inventory_tree"
EXTRACTION_FIXTURES = Path(__file__).parent / "fixtures" / "extraction"
NOTION_EXPORT = (
    "40b7a161-92e3-450d-8dab-c2bb4a080adf_"
    "ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2"
)
CAPACITIES_ARCHIVE = "Capacities (2026-09-03 14-19-01).zip"


def _parse(
    config,
    filename: str,
    *,
    source_system: str,
    kind: str = "document",
    extension: Optional[str] = None,
):
    path = EXTRACTION_FIXTURES / filename
    return normalize_module.parse_source(
        path,
        kind,
        extension or path.suffix,
        config,
        source_system=source_system,
        relative_path=f"data/{source_system}/{filename}",
    )


def _prepare_archive_tree(tmp_path: Path) -> Path:
    shutil.copytree(FIXTURE_ROOT, tmp_path, dirs_exist_ok=True)
    notes = tmp_path / "data" / "notes"
    with zipfile.ZipFile(notes / CAPACITIES_ARCHIVE, "w") as archive:
        archive.writestr("Notes/notion-roadmap.md", "# Capacity note\n")
        archive.writestr("Notes/archive-only.md", "# Archived copy\n")
    with zipfile.ZipFile(notes / f"{NOTION_EXPORT}.zip", "w") as archive:
        archive.writestr(f"{NOTION_EXPORT}/Project.html", "<h1>Notion project</h1>\n")
    return tmp_path


def _source_row(con: sqlite3.Connection, relative_path: str) -> sqlite3.Row:
    row = con.execute(
        "SELECT * FROM source_record WHERE relative_path=?",
        (relative_path,),
    ).fetchone()
    assert row is not None
    return row


def test_parser_specific_source_distinctions(tmp_path: Path):
    config = load_config(tmp_path)

    capacities_text, capacities_parser = _parse(
        config,
        "capacities-note.md",
        source_system="capacities",
    )
    capacities_csv, capacities_csv_parser = _parse(
        config,
        "capacities-records.csv",
        source_system="capacities",
        kind="table",
    )
    notion_html, notion_html_parser = _parse(
        config,
        "notion-page.html",
        source_system="notion",
    )
    notion_csv, notion_csv_parser = _parse(
        config,
        "notion-database.csv",
        source_system="notion",
        kind="table",
    )
    notion_transcript, notion_transcript_parser = _parse(
        config,
        "notion-transcript.txt",
        source_system="notion",
    )
    transcript_candidate, transcript_candidate_parser = _parse(
        config,
        "notion-transcript.txt",
        source_system="local_transcripts",
        kind="transcript_candidate",
    )
    zoom_transcript, zoom_transcript_parser = _parse(
        config,
        "zoom-transcript.vtt",
        source_system="zoom",
        kind="transcript",
    )

    assert capacities_parser == "capacities_markdown:v1"
    assert capacities_csv_parser == "capacities_csv:v1"
    assert notion_html_parser == "notion_html:v1"
    assert notion_csv_parser == "notion_database_csv:v1"
    assert notion_transcript_parser == "notion_transcript_txt:v1"
    assert transcript_candidate_parser == "transcript_txt:v1"
    assert zoom_transcript_parser == "zoom_transcript_vtt:v1"
    assert "Capacities Markdown" in capacities_text
    assert "capacity-1" in capacities_csv
    assert "Notion HTML" in notion_html
    assert "Local corpus" in notion_csv
    assert "own evidence unit" in notion_transcript
    assert transcript_candidate == notion_transcript
    assert "Synthetic Zoom transcript" in zoom_transcript


def test_formal_pdf_parser_keeps_page_locator(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    config = load_config(tmp_path)
    pdf = tmp_path / "performance-review.pdf"
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with pdf.open("wb") as handle:
        writer.write(handle)

    text, parser = normalize_module.parse_source(
        pdf,
        "document",
        ".pdf",
        config,
        source_system="formal_records",
        relative_path="data/formal-candidate/performance-review.pdf",
    )

    assert parser == "formal_pdf:v1"
    assert "## Page 1" in text


def test_provenance_header_contains_version_date_basis_and_locator():
    header = provenance_header(
        {
            "source_id": "source-1",
            "source_version_id": "version-1",
            "relative_path": "data/notes/record.md",
            "parser": "capacities_markdown:v1",
            "parser_version": "v1",
            "source_date_basis": "filename_hint",
            "locator": "document",
        }
    )

    assert 'source_version_id: "version-1"' in header
    assert 'parser_version: "v1"' in header
    assert 'source_date_basis: "filename_hint"' in header
    assert 'locator: "document"' in header


def test_capacities_pointer_only_record_is_missing_without_fetching_signed_url(
    tmp_path: Path,
):
    config = load_config(tmp_path)

    text, parser = _parse(
        config,
        "capacities-pointer.md",
        source_system="capacities",
    )

    assert parser == "capacities_markdown:v1"
    assert "payload_status: missing" in text
    assert "X-Amz-Signature" not in text
    assert "synthetic-signature" not in text


def test_capacities_quoted_pointer_metadata_is_missing_without_fetching_payload(
    tmp_path: Path,
):
    config = load_config(tmp_path)
    path = tmp_path / "capacities-pointer-quoted.md"
    path.write_text(
        "---\n"
        "type: 'File'\n"
        "media: https://files.example.test/file?sig=secret\n"
        "---\n"
        "\nUnavailable locally.\n",
        encoding="utf-8",
    )
    text, _parser = normalize_module.parse_source(
        path,
        "document",
        ".md",
        config,
        source_system="capacities",
        relative_path="data/capacities-pointer-quoted.md",
    )

    assert "payload_status: missing" in text
    assert "sig=secret" not in text


def test_normalize_records_provenance_evidence_and_scrubs_fts(tmp_path: Path):
    source_path = tmp_path / "data" / "notes" / "Notes" / "work-secure-note.md"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "# Secure work note\n"
        "Signed URL: https://files.example.test/item?X-Amz-Signature=secret-signature"
        "&X-Amz-Credential=secret-credential\n"
        "api_key = \"super-secret\"\n"
        "Authorization: Bearer bearer-secret\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "extraction.sqlite")
    try:
        inventory_module.inventory(config, con)
        result = normalize_module.normalize_all(config, con)
        row = _source_row(con, "data/notes/Notes/work-secure-note.md")
        normalized = con.execute(
            "SELECT * FROM normalized_document WHERE source_id=?",
            (row["source_id"],),
        ).fetchone()
        evidence = con.execute(
            "SELECT * FROM evidence_record WHERE source_version_id=?",
            (row["source_version_id"],),
        ).fetchall()
        fts = con.execute(
            "SELECT derived_text FROM derived_text_fts WHERE evidence_id=?",
            (evidence[0]["evidence_id"],),
        ).fetchone()
    finally:
        con.close()

    assert result["normalized"] == 1
    assert normalized["status"] == "normalized"
    assert normalized["parser"] == "capacities_markdown:v1"
    assert normalized["parser_version"] == "v1"
    assert len(evidence) == 1
    assert evidence[0]["locator"] == "document"
    output = Path(normalized["normalized_path"]).read_text(encoding="utf-8")
    assert f'source_id: "{row["source_id"]}"' in output
    assert f'source_version_id: "{row["source_version_id"]}"' in output
    assert 'relative_path: "data/notes/Notes/work-secure-note.md"' in output
    assert 'source_date_basis: "not_observed"' in output
    assert 'locator: "document"' in output
    assert "X-Amz-Signature" not in output
    assert "secret-signature" not in output
    assert "super-secret" not in output
    assert "bearer-secret" not in output
    assert "X-Amz-Signature" not in fts["derived_text"]
    assert "super-secret" not in fts["derived_text"]


def test_json_secret_keys_are_scrubbed_before_derived_output():
    value = '{"api_key": "json-secret", "token": "token-secret", "ok": "value"}'

    scrubbed = scrub_derived_text(value)

    assert "json-secret" not in scrubbed
    assert "token-secret" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_duplicate_transcript_locators_remain_distinct_evidence(tmp_path: Path):
    path = tmp_path / "duplicate-cues.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "00:00.000 --> 00:01.000\nFirst cue\n\n"
        "00:00.000 --> 00:02.000\nSecond cue\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)

    extracted = normalize_module.extract_source(
        path,
        "transcript",
        ".vtt",
        config,
        source_system="zoom",
        relative_path="data/Zoom/2026-09-01 Meeting/duplicate-cues.vtt",
    )

    locators = [part.locator for part in extracted.parts]
    assert len(locators) == 2
    assert len(set(locators)) == 2


def test_zoom_folder_date_has_explicit_date_basis(tmp_path: Path):
    path = tmp_path / "data" / "Zoom" / "2026-09-02 10.00.00 Team Sync" / "notes.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Meeting notes\n", encoding="utf-8")
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.local.json").write_text(
        json.dumps({"normalization": {"skip_classifications": []}}),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "date-basis.sqlite")
    try:
        inventory_module.inventory(config, con)
        normalize_module.normalize_all(config, con)
        row = _source_row(
            con,
            "data/Zoom/2026-09-02 10.00.00 Team Sync/notes.md",
        )
        normalized = con.execute(
            "SELECT normalized_path FROM normalized_document WHERE source_id=?",
            (row["source_id"],),
        ).fetchone()
    finally:
        con.close()

    assert normalized is not None
    output = Path(normalized["normalized_path"]).read_text(encoding="utf-8")
    assert 'source_date_basis: "meeting_folder"' in output


def test_parser_version_change_rebuilds_same_source_version(tmp_path: Path):
    path = tmp_path / "data" / "notes" / "Notes" / "versioned.md"
    path.parent.mkdir(parents=True)
    path.write_text("# Versioned note\n", encoding="utf-8")
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.local.json").write_text(
        json.dumps({"normalization": {"skip_classifications": []}}),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "parser-version.sqlite")
    try:
        inventory_module.inventory(config, con)
        first = normalize_module.normalize_all(config, con)
        row = _source_row(con, "data/notes/Notes/versioned.md")
        con.execute(
            "UPDATE normalized_document SET parser_version='old' WHERE source_id=?",
            (row["source_id"],),
        )
        con.commit()
        second = normalize_module.normalize_all(config, con)
    finally:
        con.close()

    assert first["normalized"] == 1
    assert second["normalized"] == 1
    assert second["skipped_unchanged"] == 0


def test_matching_archive_does_not_duplicate_directory_content(tmp_path: Path):
    root = _prepare_archive_tree(tmp_path)
    config_dir = root / "work-corpus"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.local.json").write_text(
        json.dumps({"normalization": {"skip_classifications": []}}),
        encoding="utf-8",
    )
    config = load_config(root)
    con = connect(config.state_dir / "archive.sqlite")
    try:
        inventory_module.inventory(config, con)
        builder = getattr(normalize_module, "build_archive_reference_map", None)
        assert builder is not None, "archive reference mapping is missing"
        references = builder(config, con)
        directory = _source_row(con, "data/notes/Notes/notion-roadmap.md")
        archive = _source_row(con, f"data/notes/{CAPACITIES_ARCHIVE}")
        result = normalize_module.normalize_all(config, con)
        normalized_archive = con.execute(
            "SELECT 1 FROM normalized_document WHERE source_id=?",
            (archive["source_id"],),
        ).fetchone()
    finally:
        con.close()

    matches = [
        item
        for item in references.values()
        if item["directory_relative_path"] == "data/notes/Notes/notion-roadmap.md"
    ]
    assert len(matches) == 1
    assert matches[0]["semantic_evidence_id"] == stable_evidence_id(
        directory["source_version_id"],
        "document",
    )
    assert set(matches[0]["source_references"]) == {
        directory["source_id"],
        archive["source_id"],
    }
    assert result["normalized"] >= 1
    assert normalized_archive is None
    assert (config.state_dir / "archive_reference_map.json").is_file()


def test_discovery_report_is_not_searchable_evidence(tmp_path: Path):
    root = _prepare_archive_tree(tmp_path)
    config = load_config(root)
    con = connect(config.state_dir / "discovery.sqlite")
    try:
        inventory_module.inventory(config, con)
        result = normalize_module.normalize_all(config, con)
        discovery = _source_row(
            con,
            "data/note-inventory-20260903-142816/scan.csv",
        )
        normalized = con.execute(
            "SELECT 1 FROM normalized_document WHERE source_id=?",
            (discovery["source_id"],),
        ).fetchone()
        evidence = con.execute(
            "SELECT 1 FROM evidence_record WHERE source_version_id=?",
            (discovery["source_version_id"],),
        ).fetchone()
        fts = con.execute(
            """
            SELECT 1
            FROM derived_text_fts
            WHERE evidence_id IN (
                SELECT evidence_id
                FROM evidence_record
                WHERE source_version_id=?
            )
            """,
            (discovery["source_version_id"],),
        ).fetchone()
    finally:
        con.close()

    assert discovery["kind"] == "discovery"
    assert result["normalized"] >= 0
    assert normalized is None
    assert evidence is None
    assert fts is None


def test_prior_good_normalized_output_survives_parser_failure(tmp_path: Path):
    source_path = tmp_path / "data" / "notes" / "Notes" / "work-parser-error.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_text('{"status": "good"}\n', encoding="utf-8")
    config = load_config(tmp_path)
    con = connect(config.state_dir / "prior-good.sqlite")
    try:
        inventory_module.inventory(config, con)
        first_result = normalize_module.normalize_all(config, con)
        first = _source_row(con, "data/notes/Notes/work-parser-error.json")
        first_normalized = con.execute(
            "SELECT * FROM normalized_document WHERE source_version_id=?",
            (first["source_version_id"],),
        ).fetchone()
        first_bytes = Path(first_normalized["normalized_path"]).read_bytes()

        source_path.write_text('{"status": \n', encoding="utf-8")
        inventory_module.inventory(config, con)
        second_result = normalize_module.normalize_all(config, con)
        second = _source_row(con, "data/notes/Notes/work-parser-error.json")
        old_after = con.execute(
            "SELECT status, normalized_path FROM normalized_document WHERE source_version_id=?",
            (first["source_version_id"],),
        ).fetchone()
        new_after = con.execute(
            "SELECT status, normalized_path, error FROM normalized_document WHERE source_version_id=?",
            (second["source_version_id"],),
        ).fetchone()
    finally:
        con.close()

    assert first_result["normalized"] == 1
    assert second_result["errors"] == 1
    assert old_after["status"] == "prior_good_retained"
    assert old_after["normalized_path"]
    assert Path(old_after["normalized_path"]).read_bytes() == first_bytes
    assert new_after["status"] == "error"
    assert new_after["normalized_path"] is None
    assert "JSONDecodeError" in new_after["error"]


def test_zoom_client_config_is_nonfailing_metadata_not_transcript(tmp_path: Path):
    config_path = tmp_path / "data" / "Zoom" / "2026-09-01 09.00.00 Team Sync"
    config_path.mkdir(parents=True)
    client_config = config_path / "client_config.json"
    client_config.write_text(
        '<?xml version="1.0"?><plist><dict/></plist>\n',
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom-metadata.sqlite")
    try:
        inventory_module.inventory(config, con)
        result = normalize_module.normalize_all(config, con)
        source = _source_row(
            con,
            "data/Zoom/2026-09-01 09.00.00 Team Sync/client_config.json",
        )
        normalized = con.execute(
            "SELECT * FROM normalized_document WHERE source_id=?",
            (source["source_id"],),
        ).fetchone()
        evidence = con.execute(
            "SELECT 1 FROM evidence_record WHERE source_version_id=?",
            (source["source_version_id"],),
        ).fetchone()
    finally:
        con.close()

    assert source["kind"] == "metadata"
    assert result["errors"] == 0
    assert normalized is None
    assert evidence is None


def test_onenote_is_blocked_without_local_converter_and_does_not_read_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("ONENOTE_CONVERTER_ROOT", raising=False)
    monkeypatch.delenv("ONENOTE_CONVERTER_COMMAND", raising=False)
    config = load_config(tmp_path)
    one_path = tmp_path / "data" / "notes" / "Backup" / "synthetic.one"
    one_path.parent.mkdir(parents=True)
    one_path.write_bytes(b"synthetic OneNote bytes must not be read")

    def fail_if_read(_self):
        raise AssertionError("blocked OneNote adapter read the .one payload")

    monkeypatch.setattr(Path, "read_bytes", fail_if_read)
    assert importlib.util.find_spec("work_corpus.onenote") is not None, (
        "OneNote adapter module is missing"
    )
    result = importlib.import_module("work_corpus.onenote").convert_one(config, one_path)

    assert result.status == "blocked"
    assert "converter" in result.error.casefold()
    assert result.text == ""


def test_onenote_local_command_returns_page_and_section_locators(tmp_path: Path):
    converter = tmp_path / "local_onenote_converter.py"
    converter.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[2]).write_text(\n"
        "    '# Synthetic notebook\\n\\n## Section: Planning\\n\\n'\n"
        "    '### Page 1\\n\\nLocal converted page.\\n',\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )
    config_dir = tmp_path / "work-corpus"
    config_dir.mkdir()
    (config_dir / "config.local.json").write_text(
        json.dumps(
            {
                "onenote": {
                    "converter_command": [
                        sys.executable,
                        str(converter),
                        "{input}",
                        "{output}",
                    ],
                    "converter_version": "synthetic-1",
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    one_path = tmp_path / "data" / "notes" / "Backup" / "synthetic.one"
    one_path.parent.mkdir(parents=True)
    one_path.write_bytes(b"synthetic OneNote bytes")

    assert importlib.util.find_spec("work_corpus.onenote") is not None, (
        "OneNote adapter module is missing"
    )
    result = importlib.import_module("work_corpus.onenote").convert_one(config, one_path)

    assert result.status == "succeeded"
    assert result.parser == "onenote_exporter:v1"
    assert result.converter["version"] == "synthetic-1"
    assert "Local converted page" in result.text
    assert "section:Planning" in result.locators
    assert "page:1" in result.locators
