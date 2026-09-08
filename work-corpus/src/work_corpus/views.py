"""Deterministic, source-backed evidence views.

The views are replaceable projections of SQLite provenance.  They do not add
claims, promote historical tasks, or include source text.  Every emitted row
must retain a present source, source version, evidence unit, and locator.
"""

from __future__ import annotations

from datetime import date
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .config import Config
from .db import current_tasks
from .util import (
    atomic_write_json,
    atomic_write_text,
    ensure_dir,
    now_iso,
    scrub_derived_text,
    write_csv,
)


PROJECT_FIELDS = [
    "project_entity_id",
    "project_name",
    "relationship_id",
    "relationship_type",
    "relationship_status",
    "relationship_confidence",
    "source_id",
    "source_version_id",
    "evidence_id",
    "source_path",
    "source_system",
    "locator",
    "source_date",
    "date_basis",
    "claim_status",
]

TASK_FIELDS = [
    "task_id",
    "review_id",
    "action",
    "view_status",
    "candidate_status",
    "task_status",
    "source_event_date",
    "source_date_basis",
    "source_date",
    "date_basis",
    "reason",
    "resolution",
    "project_name",
    "source_id",
    "source_version_id",
    "evidence_id",
    "source_path",
    "source_system",
    "locator",
]

CAREER_FIELDS = [
    "career_value",
    "operations_value",
    "classification",
    "project_names",
    "source_id",
    "source_version_id",
    "evidence_id",
    "source_path",
    "source_system",
    "locator",
    "source_date",
    "date_basis",
    "claim_status",
    "external_use",
]


_EVIDENCE_SELECT = """
    SELECT e.evidence_id, e.source_version_id, e.locator,
           e.derived_text_path, v.source_id,
           s.relative_path, s.source_system, s.classification,
           s.career_value, s.operations_value, s.date_hint,
           COALESCE((
               SELECT d.date_value
               FROM date_observation d
               WHERE d.evidence_id=e.evidence_id
                  OR (d.evidence_id IS NULL
                      AND d.source_version_id=e.source_version_id)
               ORDER BY CASE WHEN d.evidence_id=e.evidence_id THEN 0 ELSE 1 END,
                        COALESCE(d.confidence, 0) DESC, d.observation_id
               LIMIT 1
           ), s.date_hint) AS observed_date,
           (
               SELECT d.basis
               FROM date_observation d
               WHERE d.evidence_id=e.evidence_id
                  OR (d.evidence_id IS NULL
                      AND d.source_version_id=e.source_version_id)
               ORDER BY CASE WHEN d.evidence_id=e.evidence_id THEN 0 ELSE 1 END,
                        COALESCE(d.confidence, 0) DESC, d.observation_id
               LIMIT 1
           ) AS observed_basis
"""
_EVIDENCE_FROM = """
    FROM evidence_record e
    JOIN source_version v ON v.source_version_id=e.source_version_id
    JOIN source_record s ON s.source_id=v.source_id
"""
_PROJECT_SELECT = _EVIDENCE_SELECT.replace(
    "SELECT",
    "SELECT r.relationship_id, r.relationship_type, r.from_record_id, "
    "r.status, r.confidence, ",
    1,
)
_PROJECT_SELECT = _PROJECT_SELECT.replace(
    "s.relative_path,",
    "s.relative_path, p.canonical_name,",
    1,
)
_TASK_SELECT = _EVIDENCE_SELECT.replace(
    "SELECT",
    "SELECT t.task_id, t.action, t.source_event_date, t.event_date, "
    "t.candidate_status, t.task_status, t.source_date_basis, t.status, "
    "p.canonical_name, ",
    1,
)
_REVIEW_SELECT = _EVIDENCE_SELECT.replace(
    "SELECT",
    "SELECT r.review_id, r.issue_type, r.proposed_result_json, "
    "r.reason, r.resolution, ",
    1,
)


def _text(value: Any) -> str:
    return scrub_derived_text(str(value or "")).strip()


def _date_fields(row: sqlite3.Row) -> tuple[str, str]:
    source_date = _text(row["observed_date"] or row["date_hint"])
    date_basis = _text(row["observed_basis"])
    if not date_basis:
        date_basis = "filename_hint" if source_date else "not_observed"
    return source_date, date_basis


def _provenance(row: sqlite3.Row) -> Dict[str, str]:
    source_date, date_basis = _date_fields(row)
    return {
        "source_id": _text(row["source_id"]),
        "source_version_id": _text(row["source_version_id"]),
        "evidence_id": _text(row["evidence_id"]),
        "source_path": _text(row["relative_path"]),
        "source_system": _text(row["source_system"]),
        "locator": _text(row["locator"]),
        "source_date": source_date,
        "date_basis": date_basis,
    }


def _has_provenance(row: Mapping[str, Any]) -> bool:
    return all(
        str(row.get(field) or "").strip()
        for field in ("source_id", "source_version_id", "evidence_id", "source_path", "locator")
    )


def _project_rows(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in con.execute(
        _PROJECT_SELECT
        + _EVIDENCE_FROM
        + """
        JOIN relationship r ON r.evidence_id=e.evidence_id
        JOIN entity p ON p.entity_id=r.from_record_id
        WHERE p.entity_type='project'
          AND r.from_record_type='entity'
          AND r.to_record_type='evidence'
          AND r.relationship_type IN ('entity_evidence', 'project_evidence')
          AND LOWER(r.status) IN ('confirmed', 'accepted', 'approved', 'valid', 'canonical')
        ORDER BY LOWER(p.canonical_name), p.entity_id, e.evidence_id,
                 r.relationship_id
        """
    ):
        item = {
            "project_entity_id": _text(row["from_record_id"]),
            "project_name": _text(row["canonical_name"]),
            "relationship_id": _text(row["relationship_id"]),
            "relationship_type": _text(row["relationship_type"]),
            "relationship_status": _text(row["status"]),
            "relationship_confidence": row["confidence"],
            **_provenance(row),
            "claim_status": "evidence_only",
        }
        if _has_provenance(item):
            rows.append(item)
    return rows


def _project_names_by_evidence(con: sqlite3.Connection) -> Dict[str, str]:
    names: Dict[str, set[str]] = {}
    for row in con.execute(
        """
        SELECT r.evidence_id, p.canonical_name
        FROM relationship r
        JOIN entity p ON p.entity_id=r.from_record_id
        JOIN evidence_record e ON e.evidence_id=r.evidence_id
        JOIN source_version v ON v.source_version_id=e.source_version_id
        JOIN source_record s ON s.source_id=v.source_id
        WHERE p.entity_type='project'
          AND r.from_record_type='entity'
          AND r.to_record_type='evidence'
          AND r.relationship_type IN ('entity_evidence', 'project_evidence')
          AND LOWER(r.status) IN ('confirmed', 'accepted', 'approved', 'valid', 'canonical')
          AND s.status='present'
        ORDER BY r.evidence_id, LOWER(p.canonical_name), p.entity_id
        """
    ):
        names.setdefault(_text(row["evidence_id"]), set()).add(_text(row["canonical_name"]))
    return {
        evidence_id: "; ".join(sorted(values, key=str.casefold))
        for evidence_id, values in names.items()
    }


def _task_rows(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    current_ids = {
        _text(row["task_id"])
        for row in current_tasks(con, date.today())
    }
    rows: List[Dict[str, Any]] = []
    for row in con.execute(
        _TASK_SELECT
        + _EVIDENCE_FROM
        + """
        JOIN task t ON t.source_evidence_id=e.evidence_id
        LEFT JOIN entity p ON p.entity_id=t.project_entity_id
        WHERE s.status='present' AND TRIM(t.action) <> ''
        ORDER BY LOWER(t.action), t.task_id, e.evidence_id
        """
    ):
        task_id = _text(row["task_id"])
        source_event_date = _text(row["source_event_date"] or row["event_date"])
        source_basis = _text(row["source_date_basis"])
        source_date, date_basis = _date_fields(row)
        if source_event_date:
            source_date = source_event_date
        if source_basis:
            date_basis = source_basis
        item = {
            "task_id": task_id,
            "review_id": "",
            "action": _text(row["action"]),
            "view_status": "current" if task_id in current_ids else "historical",
            "candidate_status": _text(row["candidate_status"]),
            "task_status": _text(row["task_status"] or row["status"]),
            "source_event_date": source_event_date,
            "source_date_basis": source_basis,
            "source_date": source_date,
            "date_basis": date_basis,
            "reason": "Stored task row",
            "resolution": "",
            "project_name": _text(row["canonical_name"]),
            **_provenance(row),
        }
        if _has_provenance(item):
            rows.append(item)

    for row in con.execute(
        _REVIEW_SELECT
        + _EVIDENCE_FROM
        + """
        JOIN review_item r ON r.evidence_id=e.evidence_id
        WHERE s.status='present'
          AND r.issue_type IN ('task_date_review', 'task_scope_review')
        ORDER BY r.issue_type, LOWER(COALESCE(r.reason, '')),
                 r.review_id, e.evidence_id
        """
    ):
        try:
            proposal = json.loads(row["proposed_result_json"] or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            proposal = {}
        if not isinstance(proposal, dict):
            proposal = {}
        action = _text(proposal.get("action"))
        if not action:
            continue
        source_date, date_basis = _date_fields(row)
        proposed_date = _text(proposal.get("source_event_date"))
        proposed_basis = _text(proposal.get("source_date_basis"))
        item = {
            "task_id": "",
            "review_id": _text(row["review_id"]),
            "action": action,
            "view_status": (
                "scope_review"
                if row["issue_type"] == "task_scope_review"
                else "historical"
            ),
            "candidate_status": _text(proposal.get("eligibility_status")) or "review",
            "task_status": "",
            "source_event_date": proposed_date,
            "source_date_basis": proposed_basis,
            "source_date": proposed_date or source_date,
            "date_basis": proposed_basis or date_basis,
            "reason": _text(row["reason"]),
            "resolution": _text(row["resolution"]),
            "project_name": "",
            **_provenance(row),
        }
        if _has_provenance(item):
            rows.append(item)
    return rows


def _career_rows(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    project_names = _project_names_by_evidence(con)
    rows: List[Dict[str, Any]] = []
    for row in con.execute(
        _EVIDENCE_SELECT
        + _EVIDENCE_FROM
        + """
        WHERE s.status='present'
          AND LOWER(COALESCE(s.career_value, '')) IN ('medium', 'high')
        ORDER BY LOWER(COALESCE(s.career_value, '')), e.evidence_id
        """
    ):
        item = {
            "career_value": _text(row["career_value"]),
            "operations_value": _text(row["operations_value"]),
            "classification": _text(row["classification"]),
            "project_names": project_names.get(_text(row["evidence_id"]), ""),
            **_provenance(row),
            "claim_status": "evidence_only",
            "external_use": "review_required",
        }
        if _has_provenance(item):
            rows.append(item)
    return rows


def _markdown_cell(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _write_markdown(
    path: Path,
    title: str,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> None:
    lines = [f"# {title}", "", f"Rows: {len(rows)}", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    lines.extend(
        "| " + " | ".join(_markdown_cell(row.get(field)) for field in fields) + " |"
        for row in rows
    )
    atomic_write_text(path, "\n".join(lines) + "\n")


def _write_view_files(
    config: Config,
    name: str,
    title: str,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> Dict[str, str]:
    reports = ensure_dir(config.corpus_dir / "reports")
    paths = {
        "csv": reports / f"{name}.csv",
        "json": reports / f"{name}.json",
        "md": reports / f"{name}.md",
    }
    for path in paths.values():
        config.assert_derived_path(path)
    write_csv(paths["csv"], rows, list(fields))
    atomic_write_json(paths["json"], list(rows))
    _write_markdown(paths["md"], title, rows, fields)
    return {key: str(path) for key, path in paths.items()}


def build_views(config: Config, con: sqlite3.Connection) -> Dict[str, Any]:
    """Rebuild deterministic project, task, and career evidence views."""
    project_rows = _project_rows(con)
    task_rows = _task_rows(con)
    career_rows = _career_rows(con)
    outputs = {
        "project_evidence": _write_view_files(
            config, "project_evidence", "Project Evidence", project_rows, PROJECT_FIELDS
        ),
        "task_candidates": _write_view_files(
            config, "task_candidates", "Task Candidates", task_rows, TASK_FIELDS
        ),
        "career_evidence_ledger": _write_view_files(
            config,
            "career_evidence_ledger",
            "Career Evidence Ledger",
            career_rows,
            CAREER_FIELDS,
        ),
    }
    acceptance_path = config.state_dir / "views_acceptance.json"
    config.assert_derived_path(acceptance_path)
    acceptance = {
        "schema_version": 1,
        "generated_at": now_iso(),
        "counts": {
            "project_evidence": len(project_rows),
            "task_candidates": len(task_rows),
            "career_evidence": len(career_rows),
        },
        "outputs": outputs,
        "source_scope": {
            "projects": "present sources with confirmed entity_evidence relationships",
            "tasks": "present sources with stored task rows or nonblank task review proposals",
            "career": "present sources marked career_value medium or high",
        },
        "provenance": {
            "blank_provenance_rows": 0,
            "claims_generated": False,
            "raw_data_modified": False,
            "external_use": "review_required",
        },
    }
    atomic_write_json(acceptance_path, acceptance)
    return {
        "counts": acceptance["counts"],
        "outputs": outputs,
        "acceptance_path": str(acceptance_path),
    }
