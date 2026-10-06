import json
import sqlite3

import pytest

from work_corpus.reminders_bridge import deliver, initialize, owner_completion_changes


class Fake:
    def __init__(self):
        self.items = []
        self.calls = []
        self.timeout_after_create = False
        self.mismatch_readback = False

    def call(self, action, payload):
        self.calls.append(action)
        if action == "snapshot":
            return self.items.copy()
        if action == "create":
            item = {"id": "r1", "account_id": payload["account_id"], "list_id": payload["list_id"],
                    "title": payload["title"], "body": payload["body"], "completed": False, "due_date": None}
            self.items.append(item)
            if self.timeout_after_create:
                raise TimeoutError()
            return item
        if action == "get":
            item = next(x for x in self.items if x["id"] == payload["reminder_id"]).copy()
            if self.mismatch_readback:
                item["title"] = "Changed"
            return item
        raise AssertionError(action)


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    initialize(c)
    yield c
    c.close()


def task():
    return {"task_id": "t1", "account_id": "account", "list_id": "mine", "title": "Send report",
            "body": "Source: meeting\nBusiness context only", "source": {
                "source_id": "meeting", "source_version_id": "hash", "locator": "chars:2-30",
                "excerpt_sha256": "excerpt-hash", "event_date": "2026-10-05"}}


def test_reservation_precedes_native_create_and_readback(con):
    class ReservedFake(Fake):
        def call(self, action, payload):
            assert con.execute("SELECT status FROM reminder_effects").fetchone()
            return super().call(action, payload)
    backend = ReservedFake()
    result = deliver(con, backend, task())
    assert backend.calls == ["snapshot", "create", "get"]
    assert result["status"] == "verified"
    assert result["native"]["due_date"] is None
    assert result["source"]["locator"] == "chars:2-30"
    assert json.loads(con.execute("SELECT receipt_json FROM reminder_effects").fetchone()[0]) == result


def test_retry_after_timeout_reconciles_actual_create(con):
    backend = Fake()
    backend.timeout_after_create = True
    assert deliver(con, backend, task())["status"] == "uncertain"
    backend.timeout_after_create = False
    result = deliver(con, backend, task())
    assert result["status"] == "verified"
    assert result["created_now"] is False
    assert len(backend.items) == 1
    assert backend.calls.count("create") == 1


def test_duplicate_retry_never_creates_twice(con):
    backend = Fake()
    deliver(con, backend, task())
    assert deliver(con, backend, task())["status"] == "verified"
    assert len(backend.items) == 1


def test_multiple_marker_matches_remain_uncertain(con):
    backend = Fake()
    deliver(con, backend, task())
    backend.items.append({**backend.items[0], "id": "r2"})
    result = deliver(con, backend, task())
    assert result["status"] == "uncertain"
    assert backend.calls.count("create") == 1


def test_unmarked_same_title_is_pending_not_claimed(con):
    backend = Fake()
    backend.items = [{"id": "personal", "title": "Send report", "body": "User item"}]
    assert deliver(con, backend, task())["status"] == "pending"
    assert backend.calls == ["snapshot"]
    assert backend.items[0]["body"] == "User item"


def test_readback_mismatch_not_delivered_and_retry_not_duplicate(con):
    backend = Fake()
    backend.mismatch_readback = True
    assert deliver(con, backend, task())["status"] == "uncertain"
    assert len(backend.items) == 1
    assert deliver(con, backend, task())["status"] == "uncertain"
    assert len(backend.items) == 1


def test_owner_edits_are_never_overwritten(con):
    backend = Fake()
    deliver(con, backend, task())
    backend.items[0]["title"] = "Owner's preferred title"
    assert deliver(con, backend, task())["status"] == "uncertain"
    assert backend.items[0]["title"] == "Owner's preferred title"


def test_checkbox_observation_never_reopens_native_item(con):
    backend = Fake()
    deliver(con, backend, task())
    backend.items[0]["completed"] = True
    backend.items[0]["body"] += "\nOwner note"
    result = owner_completion_changes(con, backend)
    assert result == [{"task_id": "t1", "completed": True, "reminder_id": "r1", "owner_fields_changed": True}]
    assert backend.items[0]["completed"] is True
    assert backend.calls[-1] == "get"


def test_changed_payload_requires_explicit_update_operation(con):
    backend = Fake()
    deliver(con, backend, task())
    assert deliver(con, backend, {**task(), "title": "Something else"})["status"] == "conflict"
    assert len(backend.items) == 1


def test_provenance_required_before_reservation(con):
    with pytest.raises(ValueError):
        deliver(con, Fake(), {**task(), "source": {}})
    assert con.execute("SELECT COUNT(*) FROM reminder_effects").fetchone()[0] == 0
