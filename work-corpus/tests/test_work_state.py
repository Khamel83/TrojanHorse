from __future__ import annotations

import sqlite3

import pytest

from work_corpus.work_state import apply_event, get_task, initialize, list_tasks


@pytest.fixture
def con():
    connection = sqlite3.connect(":memory:")
    initialize(connection, omar_owner_id="omar")
    connection.commit()
    yield connection
    connection.close()


def event(event_id="assignment", **changes):
    value = {
        "event_id": event_id, "task_id": "report", "source_id": "meeting",
        "source_version_id": "meeting-v1", "locator": "lines:14-18",
        "occurred_at": "2026-10-06", "captured_at": "2026-10-06T19:00:00Z",
        "owner_id": "omar", "person_id": "omar", "project_id": "metrics",
        "kind": "assigned", "authority": "source_explicit", "title": "Send report",
    }
    value.update(changes)
    return value


def test_tuesday_promise_thursday_explicit_matched_evidence(con):
    apply_event(con, event(due_date="2026-10-08"))
    result = apply_event(con, event("boss-thanks", kind="completed", occurred_at="2026-10-08",
                                   captured_at="2026-10-09T01:00:00Z", matched_task=True,
                                   evidence_quality="direct", source_id="email", locator="paragraph:2"))
    assert result["task"]["status"] == "completed"
    assert result["task"]["source"] == {"source_id": "email", "source_version_id": "meeting-v1", "locator": "paragraph:2"}
    assert result["task"]["list"] == "mine"


def test_owner_done_survives_old_events_new_capture_and_later_assignment(con):
    apply_event(con, event())
    apply_event(con, event("owner-done", kind="completed", authority="owner_explicit", occurred_at="2026-10-08"))
    apply_event(con, event("stale", occurred_at="2026-10-07", captured_at="2026-11-10T00:00:00Z"))
    apply_event(con, event("repeated-promise", occurred_at="2026-10-09"))
    apply_event(con, event("stale-cancellation", kind="cancelled", occurred_at="2026-10-07",
                           matched_task=True, evidence_quality="strong"))
    task = get_task(con, "report")
    assert task["status"] == "completed"
    assert task["last_event_id"] == "owner-done"


def test_only_explicit_owner_can_reopen_and_old_completion_cannot_reclose(con):
    apply_event(con, event())
    apply_event(con, event("done", kind="completed", authority="owner_explicit", occurred_at="2026-10-08"))
    result = apply_event(con, event("implicit-reopen", kind="reopened", occurred_at="2026-10-09"))
    assert result["status"] == "review"
    assert result["task"]["status"] == "completed"
    apply_event(con, event("reopen", kind="reopened", authority="owner_explicit", occurred_at="2026-10-10"))
    apply_event(con, event("old-done", kind="completed", occurred_at="2026-10-09",
                           captured_at="2026-11-10", matched_task=True, evidence_quality="strong"))
    assert get_task(con, "report")["status"] == "open"
    assert get_task(con, "report")["last_event_id"] == "reopen"


def test_retry_duplicate_and_event_identity_conflict(con):
    assert apply_event(con, event())["status"] == "accepted"
    assert apply_event(con, event())["status"] == "duplicate"
    with pytest.raises(ValueError, match="different payload"):
        apply_event(con, event(title="Different obligation"))
    assert con.execute("SELECT COUNT(*) FROM work_task_events").fetchone()[0] == 1


def test_delegated_task_does_not_complete_same_named_own_task(con):
    apply_event(con, event())
    apply_event(con, event("delegation", task_id="employee-report", owner_id="employee", person_id="employee"))
    result = apply_event(con, event("delegated-done", task_id="employee-report", owner_id="employee",
                                   person_id="employee", kind="completed", authority="owner_explicit"))
    assert result["task"]["list"] == "delegated"
    assert get_task(con, "report")["status"] == "open"
    assert len(list_tasks(con)) == 2


def test_old_open_task_has_no_fourteen_day_expiry(con):
    apply_event(con, event(occurred_at="2022-01-01", captured_at="2026-10-05"))
    assert [task["task_id"] for task in list_tasks(con, status="open")] == ["report"]


@pytest.mark.parametrize("changes", [
    {"matched_task": True, "evidence_quality": "ambiguous"},
    {"matched_task": False, "evidence_quality": "direct"},
    {"matched_task": True, "evidence_quality": "strong", "authority": "model_inferred"},
    {},
])
def test_ambiguous_thanks_and_inferred_completion_retained_for_review(con, changes):
    apply_event(con, event())
    result = apply_event(con, event("thanks", kind="completed", **changes))
    assert result["status"] == "review"
    assert result["task"]["status"] == "open"
    assert con.execute("SELECT decision FROM work_task_events WHERE event_id='thanks'").fetchone()[0] == "review"


@pytest.mark.parametrize("changes", [
    {"locator": ""}, {"source_version_id": ""}, {"occurred_at": "Tuesday"},
    {"captured_at": "2026-10-05T12:00:00"}, {"due_date": "2026-02-30"},
    {"matched_task": "yes"}, {"evidence_quality": "excellent"},
])
def test_provenance_and_explicit_valid_dates_required(con, changes):
    with pytest.raises(ValueError):
        apply_event(con, event(**changes))
    assert not list_tasks(con)


def test_due_change_clear_and_cancellation(con):
    apply_event(con, event(due_date="2026-10-08"))
    apply_event(con, event("new-due", kind="due_changed", due_date="2026-10-10", occurred_at="2026-10-07"))
    assert get_task(con, "report")["due_date"] == "2026-10-10"
    apply_event(con, event("clear-due", kind="due_changed", due_date=None, occurred_at="2026-10-08"))
    assert get_task(con, "report")["due_date"] is None
    apply_event(con, event("cancel", kind="cancelled", authority="owner_explicit", occurred_at="2026-10-09"))
    assert get_task(con, "report")["status"] == "cancelled"


def test_replayed_order_is_deterministic_and_owner_wins_same_occurrence(con):
    apply_event(con, event("owner-done", kind="completed", authority="owner_explicit", occurred_at="2026-10-08"))
    apply_event(con, event("source-cancel", kind="cancelled", occurred_at="2026-10-08",
                           matched_task=True, evidence_quality="direct"))
    apply_event(con, event())
    assert get_task(con, "report")["status"] == "completed"


def test_identity_changes_and_owner_config_changes_require_migration(con):
    apply_event(con, event())
    with pytest.raises(ValueError, match="identity differs"):
        apply_event(con, event("reassign", owner_id="employee"))
    with pytest.raises(ValueError, match="migration"):
        initialize(con, omar_owner_id="different")


def test_caller_can_rollback_without_implicit_commit(con):
    apply_event(con, event())
    con.rollback()
    assert get_task(con, "report") is None
    assert con.execute("SELECT COUNT(*) FROM work_task_events").fetchone()[0] == 0


def test_explicit_owner_completion_establishes_shell_that_new_assignment_cannot_reopen(con):
    result = apply_event(con, event("owner-done", kind="completed", authority="owner_explicit"))
    assert result["task"]["status"] == "completed"
    assert result["task"]["created_event_id"] == "owner-done"
    apply_event(con, event("later-assignment", occurred_at="2026-10-08"))
    assert get_task(con, "report")["status"] == "completed"


def test_source_completion_without_task_is_retained_for_review(con):
    result = apply_event(con, event("unassociated-done", kind="completed", matched_task=True, evidence_quality="direct"))
    assert result["status"] == "review"
    assert result["task"] is None
    assert "no existing task" in result["reason"]
    apply_event(con, event("later-assignment", occurred_at="2026-10-08"))
    assert get_task(con, "report")["status"] == "open"


def test_owner_completion_same_occurrence_wins_independent_of_capture_time_and_id(con):
    apply_event(con, event())
    apply_event(con, event("aaa-owner", kind="completed", authority="owner_explicit", occurred_at="2026-10-08",
                           captured_at="2026-10-08"))
    apply_event(con, event("zzz-source", kind="cancelled", occurred_at="2026-10-08",
                           captured_at="2026-10-10", matched_task=True, evidence_quality="direct"))
    assert get_task(con, "report")["status_event_id"] == "aaa-owner"
    assert get_task(con, "report")["status"] == "completed"


def test_due_change_preserves_completion_authority_and_provenance(con):
    apply_event(con, event())
    apply_event(con, event("owner-done", kind="completed", authority="owner_explicit", occurred_at="2026-10-08"))
    apply_event(con, event("reschedule", kind="due_changed", due_date="2026-10-11", occurred_at="2026-10-09"))
    task = get_task(con, "report")
    assert task["last_event_id"] == "reschedule"
    assert task["status_event_id"] == "owner-done"
    assert task["status_authority"] == "owner_explicit"


def test_checkbox_then_later_outstanding_then_pasted_confirmation(con):
    apply_event(con, event())
    apply_event(con, event("checkbox", kind="completed", authority="owner_explicit",
                           occurred_at="2026-10-08"))
    result = apply_event(con, event("still-outstanding", kind="outstanding",
                                   occurred_at="2026-10-12", matched_task=True,
                                   evidence_quality="direct", source_id="later-meeting"))
    assert result["status"] == "accepted"
    assert result["task"]["status"] == "evidence_needed"
    assert result["task"]["task_id"] == "report"
    assert len(list_tasks(con)) == 1
    result = apply_event(con, event("confirmation", kind="completed",
                                   occurred_at="2026-10-13", source_id="pasted-slack",
                                   locator="message:1", matched_task=True,
                                   evidence_quality="direct"))
    assert result["task"]["status"] == "completed"
    assert result["task"]["status_source"]["source_id"] == "pasted-slack"
    assert con.execute("SELECT COUNT(*) FROM work_task_events").fetchone()[0] == 4


def test_old_outstanding_imported_later_cannot_undo_checkbox(con):
    apply_event(con, event())
    apply_event(con, event("checkbox", kind="completed", authority="owner_explicit",
                           occurred_at="2026-10-10"))
    apply_event(con, event("old-outstanding", kind="outstanding", occurred_at="2026-10-08",
                           captured_at="2026-10-20", matched_task=True, evidence_quality="direct"))
    assert get_task(con, "report")["status"] == "completed"
    assert get_task(con, "report")["status_event_id"] == "checkbox"


@pytest.mark.parametrize("changes", [
    {"matched_task": False, "evidence_quality": "direct"},
    {"matched_task": True, "evidence_quality": "ambiguous"},
    {"matched_task": True, "evidence_quality": "strong", "authority": "model_inferred"},
])
def test_unclear_future_mention_does_not_request_confirmation(con, changes):
    apply_event(con, event())
    apply_event(con, event("checkbox", kind="completed", authority="owner_explicit"))
    result = apply_event(con, event("unclear", kind="outstanding", occurred_at="2026-10-12", **changes))
    assert result["status"] == "review"
    assert result["task"]["status"] == "completed"


def test_employee_confirmation_does_not_clear_omars_evidence_needed(con):
    apply_event(con, event())
    apply_event(con, event("checkbox", kind="completed", authority="owner_explicit"))
    apply_event(con, event("outstanding", kind="outstanding", occurred_at="2026-10-12",
                           matched_task=True, evidence_quality="direct"))
    apply_event(con, event("employee-assignment", task_id="employee-report",
                           owner_id="employee", person_id="employee"))
    apply_event(con, event("employee-confirmation", task_id="employee-report",
                           owner_id="employee", person_id="employee", kind="completed",
                           authority="owner_explicit"))
    assert get_task(con, "report")["status"] == "evidence_needed"


def test_cancelled_work_is_not_reopened_by_an_outstanding_mention(con):
    apply_event(con, event())
    apply_event(con, event("cancel", kind="cancelled", authority="owner_explicit"))
    apply_event(con, event("outstanding", kind="outstanding", occurred_at="2026-10-12",
                           matched_task=True, evidence_quality="direct"))
    assert get_task(con, "report")["status"] == "cancelled"


def test_pasted_older_email_can_confirm_after_newer_meeting_contradiction(con):
    apply_event(con, event())
    apply_event(con, event("checkbox", kind="completed", authority="owner_explicit",
                           occurred_at="2026-10-08"))
    apply_event(con, event("outstanding", kind="outstanding", occurred_at="2026-10-12",
                           matched_task=True, evidence_quality="direct"))
    result = apply_event(con, event("pasted-confirmation", kind="confirmed",
                                   occurred_at="2026-10-13", captured_at="2026-10-13",
                                   source_occurred_at="2026-10-08", source_id="old-email",
                                   matched_task=True, evidence_quality="direct"))
    assert result["task"]["status"] == "completed"
    assert result["task"]["status_occurred_at"] == "2026-10-13"
    assert result["task"]["status_source"]["occurred_at"] == "2026-10-08"
    assert apply_event(con, event("pasted-confirmation", kind="confirmed",
                                 occurred_at="2026-10-13", captured_at="2026-10-13",
                                 source_occurred_at="2026-10-08", source_id="old-email",
                                 matched_task=True, evidence_quality="direct"))["status"] == "duplicate"


def test_confirmation_source_date_cannot_be_silently_replaced_with_paste_date(con):
    with pytest.raises(ValueError, match="underlying source time"):
        apply_event(con, event("confirmation", kind="confirmed",
                               matched_task=True, evidence_quality="direct"))


def test_confirmation_with_unknown_email_date_does_not_require_guessing(con):
    apply_event(con, event())
    result = apply_event(con, event("confirmation", kind="confirmed",
                                   occurred_at="2026-10-13", source_occurred_at=None,
                                   matched_task=True, evidence_quality="direct"))
    assert result["task"]["status"] == "completed"
    assert result["task"]["status_source"]["occurred_at"] is None


def test_plain_todo_does_not_require_project_or_requester_classification(con):
    result = apply_event(con, event(project_id=None, person_id=None))
    assert result["task"]["status"] == "open"
    assert result["task"]["list"] == "mine"
    assert result["task"]["project_id"] is None
