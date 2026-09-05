from __future__ import annotations

from datetime import date

import pytest

from work_corpus.db import connect, current_tasks, record_evidence, record_source_version, upsert_source_record
from work_corpus.tasks import extract_task_proposals


RUN_DATE = date(2026, 9, 4)


def _evidence(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    con.execute(
        """
        INSERT INTO source_root (root_key, relative_path, source_system, precedence)
        VALUES ('synthetic', 'synthetic', 'synthetic', 1)
        """
    )
    source_id = upsert_source_record(
        con,
        root_key="synthetic",
        relative_path="synthetic/tasks.md",
        source_system="synthetic",
        kind="document",
        scope="Work",
        sensitivity="internal_review",
    )
    version_id = record_source_version(con, source_id, 12, 1, "c" * 64)
    evidence_id = record_evidence(
        con,
        version_id,
        "document",
        "corpus/tasks.md",
        "d" * 64,
        "derived",
        derived_text="synthetic tasks",
    )
    con.commit()
    return con, source_id, evidence_id


def test_only_explicit_assignment_creates_a_task_and_implied_language_is_ignored(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        proposals = extract_task_proposals(
            con,
            "Please send the agenda. We should discuss the budget.",
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-03",
            source_date_basis="meeting_date",
            run_date=RUN_DATE,
            scope="Work",
        )
        tasks = con.execute("SELECT action, source_date_basis FROM task").fetchall()
        reviews = con.execute(
            "SELECT issue_type, evidence_id FROM review_item ORDER BY issue_type"
        ).fetchall()
    finally:
        con.close()

    assert len(proposals) == 1
    assert proposals[0].status == "accepted"
    assert "send the agenda" in proposals[0].action.casefold()
    assert len(tasks) == 1
    assert tasks[0]["source_date_basis"] == "meeting_date"
    assert [(row["issue_type"], row["evidence_id"]) for row in reviews] == [
        ("task_proposal", evidence_id)
    ]


def test_future_event_is_current_and_has_deterministic_task_id(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        first = extract_task_proposals(
            con,
            "I will prepare the launch brief.",
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-20",
            source_date_basis="event_date",
            run_date=RUN_DATE,
            scope="Work",
        )
        second = extract_task_proposals(
            con,
            "I will prepare the launch brief.",
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-20",
            source_date_basis="event_date",
            run_date=RUN_DATE,
            scope="Work",
        )
        current = current_tasks(con, RUN_DATE)
        count = con.execute("SELECT COUNT(*) FROM task").fetchone()[0]
    finally:
        con.close()

    assert first[0].task_id == second[0].task_id
    assert first[0].status == "accepted"
    assert count == 1
    assert [row["task_id"] for row in current] == [first[0].task_id]


def test_current_tasks_fail_closed_without_an_explicit_date_basis(tmp_path):
    con, _source_id, evidence_id = _evidence(tmp_path)
    try:
        con.executemany(
            """
            INSERT INTO task (
                task_id, action, event_date, candidate_status, task_status,
                source_evidence_id, source_date_basis
            ) VALUES (?, ?, ?, 'accepted', 'open', ?, ?)
            """,
            [
                ("legacy-null-basis", "Do not surface null basis", "2026-09-03", evidence_id, None),
                ("legacy-empty-basis", "Do not surface empty basis", "2026-09-03", evidence_id, ""),
            ],
        )
        current = current_tasks(con, RUN_DATE)
    finally:
        con.close()

    assert current == []


def test_current_tasks_require_work_scoped_evidence_provenance(tmp_path):
    con, source_id, work_evidence_id = _evidence(tmp_path)
    try:
        personal_source_id = upsert_source_record(
            con,
            root_key="synthetic",
            relative_path="synthetic/personal.md",
            source_system="synthetic",
            kind="document",
            scope="Personal",
            sensitivity="personal",
        )
        personal_version_id = record_source_version(
            con, personal_source_id, 14, 1, "p" * 64
        )
        personal_evidence_id = record_evidence(
            con,
            personal_version_id,
            "document",
            "corpus/personal.md",
            "e" * 64,
            "derived",
        )
        con.executemany(
            """
            INSERT INTO task (
                task_id, action, source_event_date, source_date_basis,
                candidate_status, task_status, source_evidence_id
            ) VALUES (?, ?, '2026-09-03', 'meeting_date', 'accepted', 'open', ?)
            """,
            [
                ("work-task", "Prepare the work brief", work_evidence_id),
                ("personal-task", "Plan the personal trip", personal_evidence_id),
            ],
        )
        con.commit()
        current = current_tasks(con, RUN_DATE)
    finally:
        con.close()

    assert [row["task_id"] for row in current] == ["work-task"]
    assert "scope" not in current[0].keys()
    assert source_id != personal_source_id


def test_current_tasks_fail_closed_when_task_provenance_is_missing(tmp_path):
    con, _source_id, _evidence_id = _evidence(tmp_path)
    try:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute(
            """
            INSERT INTO task (
                task_id, action, source_event_date, source_date_basis,
                candidate_status, task_status, source_evidence_id
            ) VALUES ('orphan-task', 'Do not surface this', '2026-09-03',
                      'meeting_date', 'accepted', 'open', 'missing-evidence')
            """
        )
        con.commit()
        con.execute("PRAGMA foreign_keys=ON")
        current = current_tasks(con, RUN_DATE)
    finally:
        con.close()

    assert current == []


def test_future_state_claim_is_ignored_but_explicit_promise_is_preserved(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        proposals = extract_task_proposals(
            con,
            "I will be promoted next year. I will prepare the launch brief.",
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-20",
            source_date_basis="event_date",
            run_date=RUN_DATE,
            scope="Work",
        )
        tasks = con.execute("SELECT action FROM task").fetchall()
    finally:
        con.close()

    assert [proposal.action for proposal in proposals] == ["prepare the launch brief"]
    assert [row["action"] for row in tasks] == ["prepare the launch brief"]


@pytest.mark.parametrize(
    "claim",
    ["I will earn a promotion.", "I will advance my career."],
)
def test_career_claims_are_ignored_without_persisting_tasks(tmp_path, claim):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        proposals = extract_task_proposals(
            con,
            claim,
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-20",
            source_date_basis="event_date",
            run_date=RUN_DATE,
            scope="Work",
        )
        task_count = con.execute("SELECT COUNT(*) FROM task").fetchone()[0]
    finally:
        con.close()

    assert proposals == []
    assert task_count == 0


def test_boundary_old_export_and_missing_dates_are_not_current_tasks(tmp_path):
    cases = [
        ("2026-08-21", "meeting_date", "accepted", True),
        ("2026-08-20", "meeting_date", "historical", False),
        ("2026-09-03", "export_date", "review", False),
        (None, "missing", "review", False),
    ]
    for index, (event_date, basis, expected_status, expected_current) in enumerate(cases):
        con, source_id, evidence_id = _evidence(tmp_path / str(index))
        try:
            proposals = extract_task_proposals(
                con,
                "Follow up with the project owner.",
                source_id=source_id,
                source_evidence_id=evidence_id,
                source_event_date=event_date,
                source_date_basis=basis,
                run_date=RUN_DATE,
                scope="Work",
            )
            current = current_tasks(con, RUN_DATE)
            review = con.execute(
                "SELECT issue_type, evidence_id FROM review_item"
            ).fetchone()
        finally:
            con.close()

        assert proposals[0].status == expected_status
        assert bool(current) is expected_current
        if expected_current:
            assert review["issue_type"] == "task_proposal"
        else:
            assert review["issue_type"] in {"task_date_review", "task_proposal"}
            assert review["evidence_id"] == evidence_id


def test_non_work_scope_requires_review_and_never_creates_current_task(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        proposals = extract_task_proposals(
            con,
            "Please send the personnel update.",
            source_id=source_id,
            source_evidence_id=evidence_id,
            source_event_date="2026-09-03",
            source_date_basis="meeting_date",
            run_date=RUN_DATE,
            scope="Mixed",
        )
        task_count = con.execute("SELECT COUNT(*) FROM task").fetchone()[0]
        review = con.execute(
            "SELECT issue_type, evidence_id, status FROM review_item"
        ).fetchone()
    finally:
        con.close()

    assert proposals[0].status == "review"
    assert task_count == 0
    assert review["issue_type"] == "task_scope_review"
    assert review["evidence_id"] == evidence_id
    assert review["status"] == "pending"
