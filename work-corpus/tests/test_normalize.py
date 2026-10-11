"""Focused normalization tests for live, consumer-visible parsing behavior.

The extraction fixtures in ``test_extraction.py`` cover the Capacities, Notion,
Zoom, e-mail and OneNote paths. These tests pin the remaining local format
adapters that the normalizer dispatches to: JSONL, RTF, read-only SQLite and ZIP
inventories, caption cues, the generic HTML/CSV/JSON/VTT branches, the Zoom
client-config/chat boundaries, and the optional document imports.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from work_corpus.config import load_config
import work_corpus.normalize as normalize_module


def _extract(config, path: Path, *, source_system: str, kind: str = "document"):
    return normalize_module.extract_source(
        path,
        kind,
        path.suffix,
        config,
        source_system=source_system,
        relative_path=f"data/{source_system}/{path.name}",
    )


def test_jsonl_keeps_parseable_lines_and_flags_unparseable_ones(tmp_path: Path):
    config = load_config(tmp_path)
    path = tmp_path / "records.jsonl"
    path.write_text('{"b": 1, "a": 2}\nnot json\n', encoding="utf-8")

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "json:v1"
    assert result.text == '{"a": 2, "b": 1}\n[UNPARSEABLE JSONL LINE 2] not json\n'


def test_rtf_strips_control_words_and_escapes(tmp_path: Path):
    config = load_config(tmp_path)
    path = tmp_path / "note.rtf"
    path.write_text(r"{\rtf1\ansi Hello \'e9 world}", encoding="utf-8")

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "rtf_basic:v1"
    assert result.text == "Hello world\n"


def test_sqlite_extraction_is_read_only_and_reports_rows_and_blobs(tmp_path: Path):
    config = load_config(tmp_path)
    path = tmp_path / "content.sqlite"
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE t(a TEXT, b BLOB)")
        con.execute("INSERT INTO t VALUES(?, ?)", ("hi", b"\x00\x01\x02\x03"))
        con.execute("INSERT INTO t VALUES(?, ?)", (None, None))
        con.commit()
    finally:
        con.close()

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "sqlite_read_only:v1"
    assert result.parts[0].locator == "database"
    assert "Rows: 2" in result.text
    assert "[BLOB 4 bytes]" in result.text
    assert "### Extracted rows" in result.text


def test_sqlite_extraction_reports_database_wide_row_limit(tmp_path: Path):
    config = load_config(tmp_path)
    config.payload["normalization"] = {"max_table_rows": 1}
    path = tmp_path / "limited.sqlite"
    con = sqlite3.connect(path)
    try:
        con.execute("CREATE TABLE t(a TEXT)")
        con.execute("INSERT INTO t VALUES('one')")
        con.execute("INSERT INTO t VALUES('two')")
        con.commit()
    finally:
        con.close()

    result = _extract(config, path, source_system="local_transcripts")

    assert "TABLE TRUNCATED: extracted 1 of 2 rows" in result.text


def test_zip_inventory_lists_members_and_records_truncation(tmp_path: Path):
    config = load_config(tmp_path)
    config.payload["inventory"] = {"max_archive_entries_to_list": 2}
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name in ("one.txt", "two.txt", "three.txt"):
            archive.writestr(name, "x")

    result = _extract(config, path, source_system="local_transcripts", kind="archive")

    assert result.parser == "zip_inventory:v1"
    assert [part.locator for part in result.parts] == [
        "archive:member:1",
        "archive:member:2",
        "archive:truncated",
    ]
    assert "[TRUNCATED AFTER 2 ENTRIES]" in result.text


def test_caption_cues_skip_numbers_and_metadata_lines(tmp_path: Path):
    config = load_config(tmp_path)
    path = tmp_path / "captions.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "1\n"
        "00:00:00.000 --> 00:00:01.000\n"
        "Kind: captions\n"
        "Language: en\n"
        "Hello world\n",
        encoding="utf-8",
    )

    result = _extract(config, path, source_system="zoom", kind="transcript")

    assert result.parser == "zoom_transcript_vtt:v1"
    assert [part.locator for part in result.parts] == ["timestamp:00:00:00.000"]
    assert "Hello world" in result.text
    assert "Kind:" not in result.text
    assert "Language:" not in result.text


def test_generic_extension_dispatch_uses_local_format_parsers(tmp_path: Path):
    config = load_config(tmp_path)

    html = tmp_path / "page.html"
    html.write_text("<h1>Heading</h1><p>Body</p>", encoding="utf-8")
    csv_path = tmp_path / "table.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
    json_path = tmp_path / "record.json"
    json_path.write_text('{"k": 1}', encoding="utf-8")
    vtt_path = tmp_path / "transcript.vtt"
    vtt_path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nspoken\n", encoding="utf-8")

    assert _extract(config, html, source_system="local_transcripts").parser == "html_to_text:v1"
    assert _extract(config, csv_path, source_system="local_transcripts").parser == "csv:v1"
    assert _extract(config, json_path, source_system="local_transcripts").parser == "json:v1"
    generic_vtt = _extract(config, vtt_path, source_system="local_transcripts")
    assert generic_vtt.parser == "transcript_vtt:v1"
    assert "spoken" in generic_vtt.text


def test_capacities_json_source_uses_capacities_json_parser(tmp_path: Path):
    config = load_config(tmp_path)
    path = tmp_path / "capacities.json"
    path.write_text('{"title": "note"}', encoding="utf-8")

    result = _extract(config, path, source_system="capacities")

    assert result.parser == "capacities_json:v1"
    assert '"title": "note"' in result.text


def test_zoom_client_config_and_meeting_chat_are_metadata_not_transcripts(tmp_path: Path):
    config = load_config(tmp_path)

    client_config = tmp_path / "client_config.json"
    client_config.write_text("{}", encoding="utf-8")
    config_result = _extract(config, client_config, source_system="zoom")
    assert config_result.parser == "zoom_client_config:v1"
    assert config_result.status == "metadata"

    transcript = tmp_path / "meeting transcript.txt"
    transcript.write_text("captured words", encoding="utf-8")
    transcript_result = _extract(config, transcript, source_system="zoom")
    assert transcript_result.parser == "zoom_transcript_txt:v1"
    assert transcript_result.status == "normalized"

    chat = tmp_path / "meeting chat.txt"
    chat.write_text("chat words", encoding="utf-8")
    chat_result = _extract(config, chat, source_system="zoom", kind="meeting_chat")
    assert chat_result.parser == "zoom_meeting_chat:v1"
    assert chat_result.status == "metadata"


@pytest.mark.parametrize(
    ("suffix", "message"),
    [
        (".olm", "proprietary archive"),
        (".doc", "legacy Microsoft Office"),
        (".bin", "unsupported normalization format"),
    ],
)
def test_proprietary_and_unknown_formats_raise_without_parsing(
    tmp_path: Path, suffix: str, message: str
):
    config = load_config(tmp_path)
    path = tmp_path / f"source{suffix}"
    path.write_text("raw", encoding="utf-8")

    with pytest.raises(RuntimeError, match=message):
        _extract(config, path, source_system="local_transcripts")


def test_formal_docx_parts_keep_heading_levels_and_tables(tmp_path: Path):
    docx = pytest.importorskip("docx")
    config = load_config(tmp_path)
    document = docx.Document()
    document.add_heading("Title", level=1)
    document.add_paragraph("Body text")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "key"
    table.rows[0].cells[1].text = "value"
    path = tmp_path / "report.docx"
    document.save(path)

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "formal_docx:v1"
    assert [part.locator for part in result.parts] == [
        "paragraph:1",
        "paragraph:2",
        "table:1:row:1",
    ]
    assert "# Title" in result.text


def test_formal_xlsx_truncates_rows_per_configured_limit(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    config = load_config(tmp_path)
    config.payload["normalization"] = {"max_table_rows": 2}
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["h1", "h2"])
    sheet.append(["r1", "r2"])
    sheet.append(["r3", "r4"])
    path = tmp_path / "sheet.xlsx"
    workbook.save(path)

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "formal_xlsx:v1"
    assert "sheet:Sheet:truncated" in [part.locator for part in result.parts]
    assert "[SHEET TRUNCATED AFTER 2 ROWS]" in result.text


def test_formal_pptx_parts_group_content_by_slide(tmp_path: Path):
    pptx = pytest.importorskip("pptx")
    config = load_config(tmp_path)
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Deck title"
    path = tmp_path / "deck.pptx"
    presentation.save(path)

    result = _extract(config, path, source_system="local_transcripts")

    assert result.parser == "formal_pptx:v1"
    assert [part.locator for part in result.parts] == ["slide:1"]
    assert "Deck title" in result.text


def test_corrupt_metadata_treats_source_root_as_unapproved(tmp_path: Path):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    try:
        row = con.execute("SELECT ? AS metadata_json", ("{not-json",)).fetchone()
        empty = con.execute("SELECT ? AS metadata_json", (None,)).fetchone()
    finally:
        con.close()

    assert normalize_module._has_explicit_source_root(row) is False
    assert normalize_module._has_explicit_source_root(empty) is False
    assert normalize_module._row_metadata(row) == {}


def test_metadata_json_declaring_source_root_is_accepted(tmp_path: Path):
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT ? AS metadata_json",
            (json.dumps({"root_match_kind": "source"}),),
        ).fetchone()
    finally:
        con.close()

    assert normalize_module._has_explicit_source_root(row) is True
