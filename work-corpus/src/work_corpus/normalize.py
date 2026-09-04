from __future__ import annotations

import csv
import html
import io
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import Config, DEFAULT_SKIP_CLASSIFICATIONS
from .db import mark_noncurrent_normalized_documents_retained
from .util import (
    atomic_write_text,
    ensure_dir,
    html_to_text,
    now_iso,
    provenance_header,
    read_text_guess,
    sha256_text,
    vtt_or_srt_to_markdown,
)


def _output_path(config: Config, source_system: str, source_version_id: str) -> Path:
    return config.corpus_dir / "normalized" / source_system / f"{source_version_id}.md"


def _parse_csv(path: Path, delimiter: str, max_rows: int) -> str:
    text = read_text_guess(path)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    output: List[str] = []
    for index, row in enumerate(reader):
        if index >= max_rows:
            output.append("")
            output.append(f"[TRUNCATED AFTER {max_rows} ROWS]")
            break
        output.append("\t".join(cell.replace("\t", " ").replace("\r", " ").replace("\n", " ") for cell in row))
    return "\n".join(output) + "\n"


def _parse_json(path: Path) -> str:
    text = read_text_guess(path)
    if path.suffix.lower() == ".jsonl":
        lines = []
        for number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                lines.append(json.dumps(obj, ensure_ascii=False, sort_keys=True))
            except json.JSONDecodeError:
                lines.append(f"[UNPARSEABLE JSONL LINE {number}] {line}")
        return "\n".join(lines) + "\n"
    payload = json.loads(text)
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _parse_rtf(path: Path) -> str:
    text = read_text_guess(path)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", text)
    text = text.replace("{", "").replace("}", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip() + "\n"


def _parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError("optional dependency pypdf is not installed") from exc
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as exc:
            page_text = f"[PAGE {index} EXTRACTION ERROR: {exc}]"
        pages.append(f"## Page {index}\n\n{page_text.strip()}\n")
    return "\n".join(pages)


def _parse_docx(path: Path) -> str:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:
        raise RuntimeError("optional dependency python-docx is not installed") from exc
    document = Document(str(path))
    output: List[str] = []
    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            style = (paragraph.style.name or "").lower() if paragraph.style else ""
            if style.startswith("heading"):
                digits = re.findall(r"\d+", style)
                level = min(int(digits[0]), 6) if digits else 2
                output.append("#" * level + " " + paragraph.text.strip())
            else:
                output.append(paragraph.text)
    for table_index, table in enumerate(document.tables, start=1):
        output.append(f"\n## Table {table_index}\n")
        for row in table.rows:
            output.append("\t".join(cell.text.replace("\n", " ") for cell in row.cells))
    return "\n\n".join(output).strip() + "\n"


def _parse_pptx(path: Path) -> str:
    try:
        from pptx import Presentation  # type: ignore
    except ImportError as exc:
        raise RuntimeError("optional dependency python-pptx is not installed") from exc
    prs = Presentation(str(path))
    output: List[str] = []
    for index, slide in enumerate(prs.slides, start=1):
        output.append(f"# Slide {index}")
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False):
                text = shape.text.strip()
                if text:
                    output.append(text)
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    output.append("\t".join(cell.text.replace("\n", " ") for cell in row.cells))
        notes_slide = getattr(slide, "notes_slide", None)
        if notes_slide:
            note_parts = []
            for shape in notes_slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    value = shape.text.strip()
                    if value and value.lower() not in {"slide image", "text placeholder"}:
                        note_parts.append(value)
            if note_parts:
                output.append("## Speaker notes")
                output.extend(note_parts)
        output.append("")
    return "\n\n".join(output).strip() + "\n"


def _parse_xlsx(path: Path, max_rows: int) -> str:
    try:
        from openpyxl import load_workbook  # type: ignore
    except ImportError as exc:
        raise RuntimeError("optional dependency openpyxl is not installed") from exc
    workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    output: List[str] = []
    remaining = max_rows
    for sheet in workbook.worksheets:
        output.append(f"# Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            if remaining <= 0:
                output.append(f"[WORKBOOK TRUNCATED AFTER {max_rows} TOTAL ROWS]")
                return "\n".join(output) + "\n"
            output.append("\t".join("" if value is None else str(value).replace("\n", " ") for value in row))
            remaining -= 1
        output.append("")
    return "\n".join(output)


def _sqlite_cell(value: Any, max_chars: int = 10000) -> str:
    if value is None:
        return ""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"[BLOB {len(value)} bytes]"
    text = str(value).replace("\r", " ").replace("\n", "\\n").replace("\t", " ")
    if len(text) > max_chars:
        return text[:max_chars] + f"… [TRUNCATED {len(text) - max_chars} CHARS]"
    return text


def _parse_sqlite(path: Path, max_rows: int) -> str:
    output = [f"# SQLite read-only extraction: {path.name}", ""]
    uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    remaining = max_rows
    try:
        tables = con.execute(
            "SELECT name, type, sql FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        for name, obj_type, sql in tables:
            output.append(f"## {obj_type.title()}: {name}")
            output.append("")
            if sql:
                output.append("```sql")
                output.append(sql)
                output.append("```")
            escaped_name = name.replace('"', '""')
            count = None
            if obj_type == "table":
                try:
                    count = con.execute(f'SELECT COUNT(*) FROM "{escaped_name}"').fetchone()[0]
                    output.append(f"Rows: {count}")
                except Exception as exc:
                    output.append(f"Rows: [COUNT ERROR: {exc}]")
            try:
                cols = con.execute(f'PRAGMA table_info("{escaped_name}")').fetchall()
                column_names = [str(col[1]) for col in cols]
                if column_names:
                    output.append("")
                    output.append("Columns:")
                    for col in cols:
                        output.append(f"- {col[1]} ({col[2] or 'untyped'})")
            except Exception as exc:
                column_names = []
                output.append(f"- [COLUMN ERROR: {exc}]")

            if remaining <= 0:
                output.append("")
                output.append(f"[ROW EXTRACTION STOPPED AFTER {max_rows} TOTAL DATABASE ROWS]")
                continue

            # Read views and tables conservatively. Cell bodies are capped and BLOBs
            # are represented by length rather than copied into normalized text.
            try:
                cursor = con.execute(f'SELECT * FROM "{escaped_name}" LIMIT ?', (remaining,))
                headers = [description[0] for description in cursor.description or []]
                rows = cursor.fetchall()
                if headers:
                    output.append("")
                    output.append("### Extracted rows")
                    output.append("")
                    output.append("```tsv")
                    output.append("\t".join(_sqlite_cell(value) for value in headers))
                    for row in rows:
                        output.append("\t".join(_sqlite_cell(value) for value in row))
                    output.append("```")
                    remaining -= len(rows)
                    if count is not None and count > len(rows):
                        output.append(
                            f"[TABLE TRUNCATED: extracted {len(rows)} of {count} rows; "
                            f"database-wide limit is {max_rows}]"
                        )
            except Exception as exc:
                output.append(f"[ROW EXTRACTION ERROR: {exc}]")
            output.append("")
    finally:
        con.close()
    return "\n".join(output)


def _parse_zip(path: Path, max_entries: int) -> str:
    output = [f"# Archive inventory: {path.name}", ""]
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        output.append(f"Entries: {len(infos)}")
        output.append("")
        for index, info in enumerate(infos):
            if index >= max_entries:
                output.append(f"[TRUNCATED AFTER {max_entries} ENTRIES]")
                break
            encrypted = bool(info.flag_bits & 0x1)
            output.append(
                f"- `{info.filename}` — compressed {info.compress_size} bytes; "
                f"uncompressed {info.file_size} bytes; encrypted={str(encrypted).lower()}"
            )
    return "\n".join(output) + "\n"


def parse_source(path: Path, kind: str, extension: str, config: Config) -> Tuple[str, str]:
    max_text = int(config.get("normalization", "max_text_file_mb", 200)) * 1024 * 1024
    max_rows = int(config.get("normalization", "max_table_rows", 100000))
    ext = extension.lower()

    if ext in {".md", ".markdown", ".txt"}:
        return read_text_guess(path, max_bytes=max_text), "plain_text"
    if ext in {".html", ".htm"}:
        return html_to_text(read_text_guess(path, max_bytes=max_text)) + "\n", "html_to_text"
    if ext == ".rtf":
        return _parse_rtf(path), "rtf_basic"
    if ext == ".csv":
        return _parse_csv(path, ",", max_rows), "csv"
    if ext == ".tsv":
        return _parse_csv(path, "\t", max_rows), "tsv"
    if ext in {".json", ".jsonl"}:
        return _parse_json(path), "json"
    if ext in {".vtt", ".srt"}:
        return vtt_or_srt_to_markdown(read_text_guess(path, max_bytes=max_text), path.stem), "caption"
    if ext == ".pdf":
        return _parse_pdf(path), "pypdf"
    if ext == ".docx":
        return _parse_docx(path), "python-docx"
    if ext == ".pptx":
        return _parse_pptx(path), "python-pptx"
    if ext == ".xlsx":
        return _parse_xlsx(path, max_rows), "openpyxl"
    if ext in {".sqlite", ".sqlite3", ".db"}:
        return _parse_sqlite(path, max_rows), "sqlite_read_only"
    if ext == ".zip":
        max_entries = int(config.get("inventory", "max_archive_entries_to_list", 100000))
        return _parse_zip(path, max_entries), "zip_inventory"

    if ext in {".one", ".onepkg"}:
        raise RuntimeError("OneNote proprietary file: export to PDF, DOCX, HTML, or Markdown first")
    if ext == ".olm":
        raise RuntimeError("Outlook OLM archive: retain as raw evidence; convert/export to EML or use an approved adapter")
    if ext in {".pst", ".ost"}:
        raise RuntimeError("Outlook PST/OST archive: retain as raw evidence; convert with an approved local tool")
    if ext in {".doc", ".ppt", ".xls"}:
        raise RuntimeError("legacy Microsoft Office binary format requires conversion")
    raise RuntimeError(f"unsupported normalization format: {ext or '[no extension]'}")


def normalize_all(config: Config, con: sqlite3.Connection) -> Dict[str, int]:
    skip_classifications = set(
        config.get(
            "normalization",
            "skip_classifications",
            list(DEFAULT_SKIP_CLASSIFICATIONS),
        )
    )

    mark_noncurrent_normalized_documents_retained(con, now_iso())

    eligible = con.execute(
        """
        SELECT s.*
        FROM source_item s
        WHERE s.status = 'present'
          AND s.extraction_status = 'ready'
          AND s.content_sha256 IS NOT NULL
          AND s.content_sha256 <> ''
          AND s.source_version_id IS NOT NULL
          AND s.source_version_id <> ''
          AND EXISTS (
              SELECT 1
              FROM source_version v
              WHERE v.source_version_id=s.source_version_id
                AND v.source_id=s.source_id
                AND v.content_sha256=s.content_sha256
          )
          AND s.kind NOT IN ('media', 'email', 'email_data', 'mcp', 'unknown')
        ORDER BY s.source_system, s.relative_path
        """
    ).fetchall()
    rows = [row for row in eligible if (row["classification"] or "Unknown") not in skip_classifications]
    review_rows = [row for row in eligible if (row["classification"] or "Unknown") in skip_classifications]

    result = {
        "normalized": 0,
        "skipped_unchanged": 0,
        "review_required": len(review_rows),
        "unsupported": 0,
        "errors": 0,
    }

    for row in review_rows:
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, source_mtime_ns, status, error,
                updated_at
            ) VALUES (?, ?, ?, 'review_required', ?, ?)
            ON CONFLICT(source_version_id) DO UPDATE SET
                source_id=excluded.source_id,
                source_mtime_ns=excluded.source_mtime_ns,
                status='review_required',
                error=excluded.error,
                updated_at=excluded.updated_at
            """,
            (
                row["source_version_id"],
                row["source_id"],
                row["mtime_ns"],
                f"Skipped pending source review: classification={row['classification']}",
                now_iso(),
            ),
        )
    for row in rows:
        source_id = row["source_id"]
        source_version_id = row["source_version_id"]
        existing = con.execute(
            """
            SELECT status, normalized_path
            FROM normalized_document
            WHERE source_version_id = ?
            """,
            (source_version_id,),
        ).fetchone()
        if (
            existing
            and existing["status"] == "normalized"
            and existing["normalized_path"]
            and Path(existing["normalized_path"]).exists()
        ):
            result["skipped_unchanged"] += 1
            continue

        path = Path(row["absolute_path"])
        output = _output_path(config, row["source_system"], source_version_id)
        try:
            body, parser = parse_source(path, row["kind"], row["extension"], config)
            metadata = {
                "source_id": source_id,
                "source_version_id": source_version_id,
                "source_content_sha256": row["content_sha256"],
                "source_system": row["source_system"],
                "original_path": row["absolute_path"],
                "relative_path": row["relative_path"],
                "original_date": row["date_hint"] or "",
                "file_type": row["extension"] or row["kind"],
                "parser": parser,
                "generated_at": now_iso(),
            }
            text = provenance_header(metadata) + body.rstrip() + "\n"
            atomic_write_text(output, text)
            con.execute(
                """
                INSERT INTO normalized_document (
                    source_version_id, source_id, normalized_path, parser,
                    source_mtime_ns, char_count, line_count, content_sha256,
                    status, error, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'normalized', NULL, ?)
                ON CONFLICT(source_version_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    normalized_path=excluded.normalized_path,
                    parser=excluded.parser,
                    source_mtime_ns=excluded.source_mtime_ns,
                    char_count=excluded.char_count,
                    line_count=excluded.line_count,
                    content_sha256=excluded.content_sha256,
                    status='normalized',
                    error=NULL,
                    updated_at=excluded.updated_at
                """,
                (
                    source_version_id,
                    source_id,
                    str(output),
                    parser,
                    row["mtime_ns"],
                    len(text),
                    text.count("\n") + 1,
                    sha256_text(text),
                    now_iso(),
                ),
            )
            result["normalized"] += 1
        except RuntimeError as exc:
            con.execute(
                """
                INSERT INTO normalized_document (
                    source_version_id, source_id, source_mtime_ns, status,
                    error, updated_at
                ) VALUES (?, ?, ?, 'unsupported', ?, ?)
                ON CONFLICT(source_version_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    source_mtime_ns=excluded.source_mtime_ns,
                    status='unsupported',
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    source_version_id,
                    source_id,
                    row["mtime_ns"],
                    str(exc),
                    now_iso(),
                ),
            )
            result["unsupported"] += 1
        except Exception as exc:
            con.execute(
                """
                INSERT INTO normalized_document (
                    source_version_id, source_id, source_mtime_ns, status,
                    error, updated_at
                ) VALUES (?, ?, ?, 'error', ?, ?)
                ON CONFLICT(source_version_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    source_mtime_ns=excluded.source_mtime_ns,
                    status='error',
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    source_version_id,
                    source_id,
                    row["mtime_ns"],
                    f"{type(exc).__name__}: {exc}",
                    now_iso(),
                ),
            )
            result["errors"] += 1
    con.commit()
    return result
