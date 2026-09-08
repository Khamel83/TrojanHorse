from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import (
    connect,
    record_evidence,
    record_review_item,
    record_source_version,
    upsert_source_record,
)
from work_corpus.entities import create_entity
from work_corpus.views import build_views


def _source_with_evidence(
    tmp_path: Path,
    con: sqlite3.Connection,
    *,
    name: str,
    career_value: str = "none",
) -> tuple[str, str, str]:
    root_key = f"synthetic_{name.replace('.', '_')}"
    con.execute(
        "INSERT INTO source_root (root_key, relative_path, source_system, precedence) "
        "VALUES (?, ?, 'synthetic', 1)",
        (root_key, f"data/{name.rsplit('/', 1)[0]}"),
    )
    path = tmp_path / "data" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    content = f"evidence for {name}".encode()
    path.write_bytes(content)
    source_id = upsert_source_record(
        con,
        root_key=root_key,
        relative_path=f"data/{name}",
        source_system="synthetic",
        kind="document",
        scope="Work",
        sensitivity="internal",
    )
    version_id = record_source_version(
        con,
        source_id,
        len(content),
        path.stat().st_mtime_ns,
        hashlib.sha256(content).hexdigest(),
    )
    con.execute(
        "UPDATE source_record SET absolute_path=?, classification='Work', "
        "extraction_status='ready', career_value=? WHERE source_id=?",
        (str(path), career_value, source_id),
    )
    evidence_id = record_evidence(
        con,
        version_id,
        "document",
        "work-corpus/corpus/normalized/synthetic.md",
        hashlib.sha256(content).hexdigest(),
        "derived",
        derived_text="safe evidence text",
    )
    return source_id, version_id, evidence_id


def test_views_are_source_backed_deterministic_and_preserve_task_proposals(tmp_path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "views.sqlite")
    try:
        source_id, version_id, evidence_id = _source_with_evidence(
            tmp_path,
            con,
            name="work/project-alpha.md",
            career_value="high",
        )
        project_id = create_entity(con, "project", "alpha", "Project Alpha")
        con.execute(
            """
            INSERT INTO relationship (
                relationship_id, relationship_type, from_record_type,
                from_record_id, to_record_type, to_record_id, evidence_id,
                status, confidence
            ) VALUES ('project-link', 'entity_evidence', 'entity', ?,
                      'evidence', ?, ?, 'confirmed', 0.9)
            """,
            (project_id, evidence_id, evidence_id),
        )
        con.execute(
            """
            INSERT INTO task (
                task_id, action, source_event_date, event_date,
                candidate_status, task_status, source_evidence_id,
                source_date_basis
            ) VALUES ('current-task', 'Prepare the brief', ?, ?,
                      'accepted', 'open', ?, 'event_date')
            """,
            (
                (date.today() + timedelta(days=1)).isoformat(),
                (date.today() + timedelta(days=1)).isoformat(),
                evidence_id,
            ),
        )
        record_review_item(
            con,
            "task_date_review",
            {
                "action": "Review the old archive",
                "source_event_date": "2020-01-01",
                "source_date_basis": "meeting_date",
                "eligibility_status": "historical",
            },
            source_id=source_id,
            evidence_id=evidence_id,
            reason="Historical proposal from signed URL https://example.test/?sig=secret-value",
            status="resolved",
        )
        record_review_item(
            con,
            "task_scope_review",
            {
                "action": "Confirm the project owner",
                "source_event_date": None,
                "source_date_basis": "not_observed",
                "eligibility_status": "review",
            },
            source_id=source_id,
            evidence_id=evidence_id,
            reason="Scope needs review",
        )
        con.commit()

        first = build_views(config, con)
        report_dir = config.corpus_dir / "reports"
        first_bytes = {
            name: (report_dir / name).read_bytes()
            for name in (
                "project_evidence.csv",
                "project_evidence.json",
                "project_evidence.md",
                "task_candidates.csv",
                "task_candidates.json",
                "task_candidates.md",
                "career_evidence_ledger.csv",
                "career_evidence_ledger.json",
                "career_evidence_ledger.md",
            )
        }
        second = build_views(config, con)
        second_bytes = {
            name: (report_dir / name).read_bytes() for name in first_bytes
        }
        project_rows = json.loads((report_dir / "project_evidence.json").read_text())
        task_rows = json.loads((report_dir / "task_candidates.json").read_text())
        career_rows = json.loads(
            (report_dir / "career_evidence_ledger.json").read_text()
        )
        acceptance = json.loads(
            (config.state_dir / "views_acceptance.json").read_text()
        )
    finally:
        con.close()

    assert first["counts"] == second["counts"]
    assert first_bytes == second_bytes
    assert project_rows[0]["project_name"] == "Project Alpha"
    assert project_rows[0]["source_id"] == source_id
    assert project_rows[0]["source_version_id"] == version_id
    assert project_rows[0]["evidence_id"] == evidence_id
    assert project_rows[0]["locator"] == "document"
    assert {row["view_status"] for row in task_rows} == {
        "current",
        "historical",
        "scope_review",
    }
    assert any(row["action"] == "Prepare the brief" for row in task_rows)
    assert any(row["action"] == "Review the old archive" for row in task_rows)
    assert career_rows[0]["claim_status"] == "evidence_only"
    assert career_rows[0]["external_use"] == "review_required"
    assert career_rows[0]["project_names"] == "Project Alpha"
    assert acceptance["counts"] == first["counts"]
    for row in project_rows + task_rows + career_rows:
        assert row["source_id"]
        assert row["source_version_id"]
        assert row["evidence_id"]
        assert row["source_path"]
        assert row["locator"]
        assert "secret-value" not in json.dumps(row)
        assert "https://" not in json.dumps(row)
