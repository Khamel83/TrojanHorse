from __future__ import annotations

from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Tuple

from .config import Config
from .util import atomic_write_json, atomic_write_text, ensure_dir, human_bytes, now_iso, write_csv


MANIFEST_FIELDS = [
    "source_id",
    "source_version_id",
    "source_root_key",
    "root_match_kind",
    "relative_path",
    "absolute_path",
    "source_system",
    "kind",
    "extension",
    "size_bytes",
    "mtime_ns",
    "content_sha256",
    "date_hint",
    "scope_proposal",
    "scope_reason",
    "classification",
    "sensitivity",
    "parse_readiness",
    "extraction_status",
    "career_value",
    "operations_value",
    "duplicate_group_id",
    "archive_member_count",
    "archive_semantic_status",
    "archive_extracted_root_key",
    "status",
    "first_seen",
    "last_seen",
]
ARCHIVE_MEMBER_FIELDS = [
    "source_id",
    "archive_path",
    "source_system",
    "member_path",
    "size_bytes",
    "compressed_size_bytes",
    "is_directory",
    "encrypted",
    "semantic_status",
    "extracted_root_key",
]
RESIDUAL_FIELDS = [
    "relative_path",
    "absolute_path",
    "source_id",
    "source_system",
    "kind",
    "extension",
    "size_bytes",
    "mtime_ns",
    "scope_proposal",
    "scope_reason",
    "status",
]


def write_manifest_reports(config: Config, rows: List[Dict[str, Any]]) -> Path:
    """Write derived manifest views without touching the reviewed inventory."""
    reports = ensure_dir(config.corpus_dir / "reports")
    manifest_path = reports / "source_manifest.csv"
    archive_path = reports / "archive_members.csv"
    residual_path = reports / "source_root_residuals.csv"
    for path in (manifest_path, archive_path, residual_path):
        config.assert_derived_path(path)

    archive_rows: List[Dict[str, Any]] = []
    residual_rows: List[Dict[str, Any]] = []
    for row in rows:
        if row.get("root_match_kind") == "residual" and row.get("status") == "present":
            residual_rows.append(row)
        for member in row.get("archive_members") or []:
            archive_rows.append(
                {
                    "source_id": row.get("source_id", ""),
                    "archive_path": row.get("relative_path", ""),
                    "source_system": row.get("source_system", ""),
                    "member_path": member.get("member_path", ""),
                    "size_bytes": member.get("size_bytes", 0),
                    "compressed_size_bytes": member.get("compressed_size_bytes", 0),
                    "is_directory": member.get("is_directory", False),
                    "encrypted": member.get("encrypted", False),
                    "semantic_status": row.get("archive_semantic_status", ""),
                    "extracted_root_key": row.get("archive_extracted_root_key", ""),
                }
            )

    write_csv(manifest_path, rows, MANIFEST_FIELDS)
    write_csv(archive_path, archive_rows, ARCHIVE_MEMBER_FIELDS)
    write_csv(residual_path, residual_rows, RESIDUAL_FIELDS)
    return manifest_path


def _count_phrase(count: int, singular: str, plural: str = "") -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _scalar(con: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    row = con.execute(query, params).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _coverage(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = []
    systems = [row[0] for row in con.execute(
        "SELECT DISTINCT source_system FROM source_item WHERE status='present' ORDER BY source_system"
    )]
    for system in systems:
        count = _scalar(
            con,
            "SELECT COUNT(*) FROM source_item WHERE status='present' AND source_system=?",
            (system,),
        )
        total = _scalar(
            con,
            "SELECT COALESCE(SUM(size_bytes),0) FROM source_item WHERE status='present' AND source_system=?",
            (system,),
        )
        dates = [
            row[0]
            for row in con.execute(
                """
                SELECT date_hint FROM source_item
                WHERE status='present' AND source_system=? AND date_hint IS NOT NULL AND date_hint<>''
                ORDER BY date_hint
                """,
                (system,),
            )
        ]
        rows.append({
            "source_system": system,
            "files": count,
            "bytes": total,
            "human_size": human_bytes(total),
            "earliest_date_hint": dates[0] if dates else "",
            "latest_date_hint": dates[-1] if dates else "",
        })
    return rows


def _unsupported(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = []
    for row in con.execute(
        """
        SELECT s.source_system, s.extension, n.status, n.error, COUNT(*) AS count
        FROM normalized_document n
        JOIN source_item s ON s.source_id=n.source_id
        WHERE n.status IN ('unsupported','error')
        GROUP BY s.source_system, s.extension, n.status, n.error
        ORDER BY count DESC, s.source_system, s.extension
        """
    ):
        rows.append(dict(row))
    return rows


def _duplicates(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT duplicate_group_id, content_sha256, COUNT(*) AS file_count,
                   SUM(size_bytes) AS total_bytes,
                   GROUP_CONCAT(relative_path, ' | ') AS paths
            FROM source_item
            WHERE status='present' AND duplicate_group_id IS NOT NULL
            GROUP BY duplicate_group_id, content_sha256
            ORDER BY file_count DESC, duplicate_group_id
            """
        )
    ]


def _version_family_key(relative_path: str) -> str:
    path = Path(relative_path)
    stem = path.stem.lower()
    stem = re.sub(r"(?<![a-z])20\d{2}[-_. ]?\d{0,2}[-_. ]?\d{0,2}(?![a-z])", " ", stem)
    stem = re.sub(r"\b(?:final|draft|copy|revised|updated|new|old|latest|clean|redline|edit|edited)\b", " ", stem)
    stem = re.sub(r"\b(?:v|ver|version|rev|revision)[-_. ]?\d+(?:[._-]\d+)*\b", " ", stem)
    stem = re.sub(r"\(\d+\)$", " ", stem)
    stem = re.sub(r"[-_. ]+", " ", stem).strip()
    if len(stem) < 5:
        return ""
    return stem + path.suffix.lower()


def _version_families(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    groups: Dict[tuple, List[str]] = defaultdict(list)
    for row in con.execute(
        "SELECT source_system, relative_path FROM source_item WHERE status='present'"
    ):
        key = _version_family_key(row["relative_path"])
        if key:
            groups[(row["source_system"], key)].append(row["relative_path"])
    output = []
    for (system, key), paths in groups.items():
        if len(paths) < 2:
            continue
        output.append({
            "source_system": system,
            "family_key": key,
            "file_count": len(paths),
            "paths": " | ".join(sorted(paths)),
        })
    return sorted(output, key=lambda row: (-row["file_count"], row["source_system"], row["family_key"]))


def _sensitive_review(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT source_id, relative_path, source_system, classification,
                   sensitivity, parse_readiness, career_value, operations_value
            FROM source_item
            WHERE status='present'
              AND (
                  classification IN (
                      'potential_personal', 'mixed_or_review',
                      'Personal', 'Mixed', 'Unknown'
                  )
                  OR sensitivity='potential_restricted'
              )
            ORDER BY classification, sensitivity, relative_path
            """
        )
    ]


def _largest(con: sqlite3.Connection, limit: int = 30) -> List[Dict[str, Any]]:
    return [
        dict(row)
        for row in con.execute(
            """
            SELECT relative_path, source_system, kind, extension, size_bytes
            FROM source_item
            WHERE status='present'
            ORDER BY size_bytes DESC
            LIMIT ?
            """,
            (limit,),
        )
    ]


def build_report(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    reports = config.corpus_dir / "reports"
    config.assert_derived_path(reports)
    reports = ensure_dir(reports)
    coverage = _coverage(con)
    unsupported = _unsupported(con)
    largest = _largest(con)
    duplicates = _duplicates(con)
    version_families = _version_families(con)
    sensitive_review = _sensitive_review(con)

    source_count = _scalar(con, "SELECT COUNT(*) FROM source_item WHERE status='present'")
    source_bytes = _scalar(con, "SELECT COALESCE(SUM(size_bytes),0) FROM source_item WHERE status='present'")
    normalized = _scalar(con, "SELECT COUNT(*) FROM normalized_document WHERE status='normalized'")
    normalize_errors = _scalar(con, "SELECT COUNT(*) FROM normalized_document WHERE status='error'")
    normalize_unsupported = _scalar(con, "SELECT COUNT(*) FROM normalized_document WHERE status='unsupported'")
    email_count = _scalar(con, "SELECT COUNT(*) FROM email_message")
    mcp_count = _scalar(con, "SELECT COUNT(*) FROM mcp_item")
    zoom_total = _scalar(con, "SELECT COUNT(*) FROM zoom_group")
    zoom_existing = _scalar(con, "SELECT COUNT(*) FROM zoom_group WHERE status='existing_transcript'")
    zoom_generated = _scalar(con, "SELECT COUNT(*) FROM zoom_group WHERE status='generated_transcript'")
    zoom_missing = _scalar(con, "SELECT COUNT(*) FROM zoom_group WHERE status='needs_transcription'")
    tx_pending = _scalar(con, "SELECT COUNT(*) FROM transcription_job WHERE status='pending'")
    tx_errors = _scalar(con, "SELECT COUNT(*) FROM transcription_job WHERE status='error'")

    summary = {
        "generated_at": now_iso(),
        "source_files": source_count,
        "source_bytes": source_bytes,
        "source_size": human_bytes(source_bytes),
        "normalized_documents": normalized,
        "normalization_errors": normalize_errors,
        "normalization_unsupported": normalize_unsupported,
        "email_messages": email_count,
        "mcp_items": mcp_count,
        "zoom_meeting_folders": zoom_total,
        "zoom_existing_transcripts": zoom_existing,
        "zoom_generated_transcripts": zoom_generated,
        "zoom_missing_transcripts": zoom_missing,
        "transcription_jobs_pending": tx_pending,
        "transcription_jobs_error": tx_errors,
        "exact_duplicate_groups": len(duplicates),
        "likely_version_families": len(version_families),
        "sensitive_review_candidates": len(sensitive_review),
        "coverage": coverage,
        "unsupported": unsupported,
    }
    atomic_write_json(reports / "status.json", summary)

    write_csv(
        reports / "coverage.csv",
        coverage,
        ["source_system", "files", "bytes", "human_size", "earliest_date_hint", "latest_date_hint"],
    )
    write_csv(
        reports / "unsupported_and_errors.csv",
        unsupported,
        ["source_system", "extension", "status", "error", "count"],
    )
    write_csv(
        reports / "largest_files.csv",
        largest,
        ["relative_path", "source_system", "kind", "extension", "size_bytes"],
    )
    write_csv(
        reports / "duplicate_groups.csv",
        duplicates,
        ["duplicate_group_id", "content_sha256", "file_count", "total_bytes", "paths"],
    )
    write_csv(
        reports / "likely_version_families.csv",
        version_families,
        ["source_system", "family_key", "file_count", "paths"],
    )
    write_csv(
        reports / "excluded_or_sensitive_review.csv",
        sensitive_review,
        [
            "source_id", "relative_path", "source_system", "classification",
            "sensitivity", "parse_readiness", "career_value", "operations_value",
        ],
    )

    needs: List[str] = []
    if source_count == 0:
        needs.append("No raw source files are currently present under `data/`.")
    if not any(row["source_system"] == "capacities" for row in coverage):
        needs.append("No Capacities export has been identified.")
    if not any(row["source_system"] == "notion" for row in coverage):
        needs.append("No Notion export has been identified.")
    if not any(row["source_system"] == "onenote" for row in coverage):
        needs.append("No OneNote export has been identified.")
    if not any(row["source_system"] == "granola" for row in coverage):
        needs.append("No durable Granola dump has been identified; MCP access alone is not a raw archive.")
    if not any(row["source_system"] == "wispr_flow" for row in coverage):
        needs.append("No durable Wispr Flow dump has been identified.")
    if email_count == 0:
        needs.append("No parseable email messages have been ingested.")
    if zoom_missing:
        needs.append(f"{zoom_missing} Zoom meeting folders still need local transcription.")
    if normalize_unsupported:
        needs.append(f"{normalize_unsupported} files require conversion or an optional parser.")
    if normalize_errors:
        needs.append(f"{normalize_errors} files produced parsing errors.")
    if tx_errors:
        needs.append(f"{tx_errors} local transcription jobs failed and need review.")
    if duplicates:
        needs.append(f"{_count_phrase(len(duplicates), 'exact duplicate group')} detected among hashed files.")
    if version_families:
        needs.append(f"{_count_phrase(len(version_families), 'likely version family', 'likely version families')} need review; they were not merged.")
    if sensitive_review:
        needs.append(f"{_count_phrase(len(sensitive_review), 'filename/path', 'filenames/paths')} flagged for personal or restricted-content review.")

    next_steps = []
    missing_note_sources = [
        name for name in ("capacities", "notion", "onenote")
        if not any(row["source_system"] == name for row in coverage)
    ]
    if missing_note_sources:
        next_steps.append(
            "Add or export the missing note sources under `data/notes/`: "
            + ", ".join(missing_note_sources)
            + "."
        )
    if not any(row["source_system"] == "inventory_discovery" for row in coverage):
        next_steps.append(
            "When the separate note-inventory finishes, place its unpacked report folder under `data/note-inventory-20260903-142816/` and rerun."
        )
    if tx_pending:
        next_steps.append(
            "Review `state/transcription_queue.csv`, configure a local Whisper engine, and run a small transcription batch."
        )
    if email_count == 0:
        next_steps.append(
            "Run `RUN_EMAIL_ACCESS_PROBE.command`, then choose EML/MBOX, legacy Outlook local export, or permitted Graph Mail.Read."
        )
    if mcp_count == 0:
        next_steps.append(
            "Use the MCP capture prompts to persist a small Granola and Wispr Flow sample under `data/mcp/`."
        )
    if normalize_unsupported:
        next_steps.append(
            "Review `unsupported_and_errors.csv`; install optional document parsers or export proprietary formats."
        )
    if not next_steps:
        next_steps.append("The mechanical evidence layer is ready for project/task/career extraction.")

    md = [
        "# What We Have and What We Need",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Current corpus",
        "",
        f"- Raw source files: **{source_count:,}** ({human_bytes(source_bytes)})",
        f"- Normalized documents: **{normalized:,}**",
        f"- Email messages: **{email_count:,}**",
        f"- Granola/Wispr MCP items: **{mcp_count:,}**",
        f"- Zoom meeting folders: **{zoom_total:,}**",
        f"- Existing Zoom transcripts: **{zoom_existing:,}**",
        f"- Locally generated Zoom transcripts: **{zoom_generated:,}**",
        f"- Zoom folders still missing transcripts: **{zoom_missing:,}**",
        f"- Exact duplicate groups: **{len(duplicates):,}**",
        f"- Likely version families: **{len(version_families):,}**",
        f"- Sensitive-review candidates: **{len(sensitive_review):,}**",
        "",
        "## Coverage by source",
        "",
        "| Source | Files | Size | Earliest hint | Latest hint |",
        "|---|---:|---:|---|---|",
    ]
    for row in coverage:
        md.append(
            f"| {row['source_system']} | {row['files']:,} | {row['human_size']} | "
            f"{row['earliest_date_hint']} | {row['latest_date_hint']} |"
        )
    md.extend(["", "## Gaps and unresolved items", ""])
    md.extend(f"- {item}" for item in needs or ["No mechanical gaps detected."])
    md.extend(["", "## Recommended next steps", ""])
    md.extend(f"{index}. {item}" for index, item in enumerate(next_steps, start=1))
    md.extend([
        "",
        "## Interpretation boundary",
        "",
        "This report establishes storage, format, date, transcript, and ingestion coverage. "
        "It does not establish that every historical note is current, every email is authorized "
        "for external use, or every apparent accomplishment belongs on a résumé.",
        "",
    ])
    atomic_write_text(reports / "what_we_have_and_need.md", "\n".join(md))

    coverage_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['source_system']))}</td>"
        f"<td>{row['files']:,}</td>"
        f"<td>{html.escape(row['human_size'])}</td>"
        f"<td>{html.escape(str(row['earliest_date_hint']))}</td>"
        f"<td>{html.escape(str(row['latest_date_hint']))}</td>"
        "</tr>"
        for row in coverage
    )
    needs_html = "".join(f"<li>{html.escape(item)}</li>" for item in needs) or "<li>No mechanical gaps detected.</li>"
    steps_html = "".join(f"<li>{html.escape(item)}</li>" for item in next_steps)
    unsupported_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['source_system']))}</td>"
        f"<td>{html.escape(str(row['extension']))}</td>"
        f"<td>{html.escape(str(row['status']))}</td>"
        f"<td>{row['count']}</td>"
        f"<td>{html.escape(str(row['error']))}</td>"
        "</tr>"
        for row in unsupported[:200]
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Work Corpus Status</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; line-height: 1.45; max-width: 1400px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap: 12px; }}
.card {{ border: 1px solid #ccc; border-radius: 8px; padding: 14px; }}
.card strong {{ font-size: 1.5rem; display: block; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 0.9rem; }}
th, td {{ border: 1px solid #ccc; padding: 7px; text-align: left; vertical-align: top; }}
th {{ background: #eee; }}
.notice {{ background: #f4f4f4; border-left: 5px solid #666; padding: 12px; }}
</style>
</head>
<body>
<h1>Work Corpus Status</h1>
<p>Generated {html.escape(summary['generated_at'])}</p>
<div class="cards">
<div class="card"><strong>{source_count:,}</strong>raw files<br>{html.escape(human_bytes(source_bytes))}</div>
<div class="card"><strong>{normalized:,}</strong>normalized documents</div>
<div class="card"><strong>{email_count:,}</strong>email messages</div>
<div class="card"><strong>{mcp_count:,}</strong>MCP items</div>
<div class="card"><strong>{zoom_total:,}</strong>Zoom folders</div>
<div class="card"><strong>{zoom_missing:,}</strong>Zoom transcripts missing</div>
<div class="card"><strong>{len(duplicates):,}</strong>exact duplicate groups</div>
<div class="card"><strong>{len(sensitive_review):,}</strong>sensitive-review candidates</div>
</div>

<h2>Coverage</h2>
<table>
<thead><tr><th>Source</th><th>Files</th><th>Size</th><th>Earliest hint</th><th>Latest hint</th></tr></thead>
<tbody>{coverage_rows}</tbody>
</table>

<h2>What is still needed</h2>
<ul>{needs_html}</ul>

<h2>Recommended next steps</h2>
<ol>{steps_html}</ol>

<h2>Unsupported formats and errors</h2>
<table>
<thead><tr><th>Source</th><th>Extension</th><th>Status</th><th>Count</th><th>Reason</th></tr></thead>
<tbody>{unsupported_rows}</tbody>
</table>

<div class="notice">
The raw archive remains authoritative. This report is a mechanical inventory, not a
determination that every item is current, accurate, externally safe, or résumé-worthy.
</div>
</body>
</html>
"""
    atomic_write_text(reports / "status.html", document)
    atomic_write_text(reports / "inventory.html", document)
    atomic_write_text(reports / "coverage_and_gaps.md", "\n".join(md))

    plan_lines = [
        "# Ingestion Plan",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Recommended sequence",
        "",
    ]
    for index, item in enumerate(next_steps, start=1):
        plan_lines.append(f"{index}. {item}")
    plan_lines.extend([
        "",
        "## Guardrails",
        "",
        "- Keep `data/` unchanged and append new raw capture batches.",
        "- Review sensitive candidates before broad model access.",
        "- Validate three Zoom transcripts before bulk transcription.",
        "- Backfill email once; use read-only deltas thereafter.",
        "- Backfill Granola/Wispr in bounded windows and persist raw responses.",
        "- Build current tasks only after historical evidence is separated from active commitments.",
        "",
    ])
    atomic_write_text(reports / "ingestion_plan.md", "\n".join(plan_lines))
    return summary
