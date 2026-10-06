"""Deterministic work-task events, separate from historical extraction proposals.

Call initialize() explicitly on a caller-owned SQLite connection. apply_event()
uses a savepoint and leaves transaction commit/rollback to the caller. Events
must already have resolved identities and source provenance; this module does
not resolve names, infer dates, validate an LLM's claims against source text,
extract commitments, or write to Reminders. An upstream trusted validator must
set authority/evidence fields; untrusted pasted text cannot authorize itself.

owner_id identifies the person responsible for delivery. person_id is the fixed
requester/accountability context of this task, NOT the speaker or author of an
individual source event. person_id and project_id can be null when unknown;
task creation does not require a project directory. Context is fixed; changes
need a separate explicit migration. Unknown source-only terminal events require
review. Explicit owner completion can create a completed shell without inventing
an assignment, because the owner's statement itself establishes the task/state.
Later explicit outstanding-work evidence can move completed work to
evidence_needed. A matched confirmation clears that state; this module never
assesses the quality of the deliverable.
For confirmed events, occurred_at is the time confirmation was supplied; retain
the underlying email/message time separately as source_occurred_at. Importing
an old message is not itself permission to emit a new confirmation event.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

KINDS = {"assigned", "completed", "confirmed", "cancelled", "reopened", "due_changed", "outstanding"}
_REQUIRED = {
    "event_id", "task_id", "source_id", "source_version_id", "locator",
    "occurred_at", "captured_at", "owner_id", "person_id", "project_id",
    "kind", "authority",
}
_OPTIONAL = {"due_date", "matched_task", "evidence_quality", "title", "source_occurred_at"}


def _timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("event dates must be explicit ISO strings")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO event date") from exc
    if result.tzinfo is None:
        raise ValueError("event timestamps require a timezone")
    return result.astimezone(timezone.utc)


def initialize(con: sqlite3.Connection, *, omar_owner_id: str) -> None:
    """Create only work_* tables and bind the self/delegated identity once."""
    if not isinstance(omar_owner_id, str) or not omar_owner_id.strip():
        raise ValueError("omar_owner_id is required")
    con.execute("CREATE TABLE IF NOT EXISTS work_state_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    prior = con.execute("SELECT value FROM work_state_config WHERE key='omar_owner_id'").fetchone()
    if prior and prior[0] != omar_owner_id:
        raise ValueError("changing the configured owner requires an explicit migration")
    con.execute("INSERT OR IGNORE INTO work_state_config VALUES ('omar_owner_id', ?)", (omar_owner_id,))
    con.execute("""CREATE TABLE IF NOT EXISTS work_task_events (
        event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
        payload_json TEXT NOT NULL, decision TEXT NOT NULL, reason TEXT NOT NULL
    )""")
    con.execute("CREATE INDEX IF NOT EXISTS work_task_events_task ON work_task_events(task_id)")
    con.execute("""CREATE TABLE IF NOT EXISTS work_tasks (
        task_id TEXT PRIMARY KEY, projection_json TEXT NOT NULL
    )""")


def _validated(event: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(event)
    if _REQUIRED - payload.keys() or payload.keys() - (_REQUIRED | _OPTIONAL):
        raise ValueError("missing or unknown event fields")
    for key in _REQUIRED:
        if key in {"person_id", "project_id"} and payload[key] is None:
            continue
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError("event field %s must be a nonempty string" % key)
    _timestamp(payload["occurred_at"])
    _timestamp(payload["captured_at"])
    if "source_occurred_at" in payload and payload["source_occurred_at"] is not None:
        _timestamp(payload["source_occurred_at"])
    if payload["kind"] == "confirmed" and "source_occurred_at" not in payload:
        raise ValueError("confirmed requires the underlying source time, or null if unknown")
    if payload["kind"] not in KINDS:
        raise ValueError("unknown event kind")
    if payload["authority"] not in {"owner_explicit", "source_explicit", "model_inferred"}:
        raise ValueError("unknown authority")
    if "matched_task" in payload and type(payload["matched_task"]) is not bool:
        raise ValueError("matched_task must be a boolean")
    if "evidence_quality" in payload and payload["evidence_quality"] not in {"direct", "strong", "indirect", "ambiguous"}:
        raise ValueError("unknown evidence quality")
    if "title" in payload and (not isinstance(payload["title"], str) or not payload["title"].strip()):
        raise ValueError("title must be a nonempty string")
    if "due_date" in payload and payload["due_date"] is not None:
        value = payload["due_date"]
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("due_date must be an explicit YYYY-MM-DD date or null")
        _timestamp(value)
    if payload["kind"] == "due_changed" and "due_date" not in payload:
        raise ValueError("due_changed requires due_date, including null to clear it")
    return payload


def _decision(payload: Dict[str, Any]) -> tuple:
    if payload["kind"] == "reopened" and payload["authority"] != "owner_explicit":
        return "review", "reopening requires explicit owner authority"
    if payload["authority"] == "owner_explicit":
        return "accepted", "explicit owner instruction"
    if payload["authority"] == "model_inferred":
        return "review", "inferred event requires review"
    if payload["kind"] in {"completed", "confirmed", "cancelled", "outstanding"}:
        if payload.get("matched_task") is not True or payload.get("evidence_quality") not in {"direct", "strong"}:
            return "review", "state change requires an explicit task match and direct or strong source evidence"
    return "accepted", "validated source event"


def get_task(con: sqlite3.Connection, task_id: str) -> Optional[Dict[str, Any]]:
    row = con.execute("SELECT projection_json FROM work_tasks WHERE task_id=?", (task_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_tasks(con: sqlite3.Connection, *, status: Optional[str] = None) -> list:
    """Return durable tasks without age filtering; no task silently expires."""
    tasks = [json.loads(row[0]) for row in con.execute("SELECT projection_json FROM work_tasks ORDER BY task_id")]
    return [task for task in tasks if status is None or task["status"] == status]


def _project(con: sqlite3.Connection, task_id: str, omar_owner_id: str) -> Optional[Dict[str, Any]]:
    events = [json.loads(row[0]) for row in con.execute(
        "SELECT payload_json FROM work_task_events WHERE task_id=? AND decision='accepted'", (task_id,)
    )]
    events.sort(key=lambda e: (_timestamp(e["occurred_at"]), e["authority"] == "owner_explicit", e["event_id"]))
    state = None
    for event in events:
        kind = event["kind"]
        # Only an explicit owner completion can establish a task without an
        # assignment. Source-only unknown events are retained for review.
        if state is None:
            if kind != "assigned" and not (kind == "completed" and event["authority"] == "owner_explicit"):
                continue
            state = {
                "task_id": task_id, "owner_id": event["owner_id"],
                "person_id": event["person_id"], "project_id": event["project_id"],
                "list": "mine" if event["owner_id"] == omar_owner_id else "delegated",
                "title": event.get("title"), "status": "completed" if kind == "completed" else "open", "due_date": event.get("due_date"),
                "created_event_id": event["event_id"],
            }
        elif kind == "assigned":
            # Repeated promises or late imports do not resurrect completed work.
            continue
        elif kind in {"completed", "confirmed"}:
            state["status"] = "completed"
        elif kind == "outstanding":
            # A later explicit contradiction requests confirmation. Repeated
            # mentions/assignments alone cannot overturn an owner checkbox.
            if state["status"] not in {"completed", "evidence_needed"}:
                continue
            state["status"] = "evidence_needed"
        elif kind == "cancelled":
            state["status"] = "cancelled"
        elif kind == "reopened":
            state["status"] = "open"
        elif kind == "due_changed":
            state["due_date"] = event["due_date"]
        if kind in {"assigned", "completed", "confirmed", "cancelled", "reopened", "outstanding"}:
            state["status_event_id"] = event["event_id"]
            state["status_authority"] = event["authority"]
            state["status_occurred_at"] = event["occurred_at"]
            state["status_source"] = {key: event[key] for key in ("source_id", "source_version_id", "locator")}
            if "source_occurred_at" in event:
                state["status_source"]["occurred_at"] = event["source_occurred_at"]
        state["last_event_id"] = event["event_id"]
        state["occurred_at"] = event["occurred_at"]
        state["authority"] = event["authority"]
        state["source"] = {key: event[key] for key in ("source_id", "source_version_id", "locator")}
    if state:
        con.execute("INSERT OR REPLACE INTO work_tasks VALUES (?, ?)", (task_id, json.dumps(state, sort_keys=True)))
    return state


def apply_event(con: sqlite3.Connection, event: Mapping[str, Any]) -> Dict[str, Any]:
    """Retain an event exactly once and atomically rebuild its task projection.

    Event identity collisions raise ValueError. Rejected evidence is retained
    as review rather than silently discarded. Occurrence order, never capture
    order, controls state. Stable IDs and resolved task identity are upstream
    responsibilities. This API deliberately cannot guess that two tasks match.
    """
    payload = _validated(event)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    config = con.execute("SELECT value FROM work_state_config WHERE key='omar_owner_id'").fetchone()
    if not config:
        raise ValueError("initialize work state first")
    prior = con.execute("SELECT payload_json, decision, reason FROM work_task_events WHERE event_id=?", (payload["event_id"],)).fetchone()
    if prior:
        if prior[0] != encoded:
            raise ValueError("event ID already exists with a different payload")
        return {"status": "duplicate", "decision": prior[1], "reason": prior[2], "task": get_task(con, payload["task_id"])}
    identity = con.execute("SELECT payload_json FROM work_task_events WHERE task_id=? LIMIT 1", (payload["task_id"],)).fetchone()
    if identity:
        old = json.loads(identity[0])
        if any(old[key] != payload[key] for key in ("owner_id", "person_id", "project_id")):
            raise ValueError("task identity differs; reassignment requires an explicit migration")
    decision, reason = _decision(payload)
    known_task = get_task(con, payload["task_id"])
    if decision == "accepted" and known_task is None and payload["kind"] != "assigned":
        if not (payload["kind"] == "completed" and payload["authority"] == "owner_explicit"):
            decision, reason = "review", "no existing task; resolve association before applying event"
    if not con.in_transaction:
        con.execute("BEGIN")
    con.execute("SAVEPOINT work_event_apply")
    try:
        con.execute("INSERT INTO work_task_events VALUES (?, ?, ?, ?, ?)", (payload["event_id"], payload["task_id"], encoded, decision, reason))
        task = _project(con, payload["task_id"], config[0])
        con.execute("RELEASE SAVEPOINT work_event_apply")
    except Exception:
        con.execute("ROLLBACK TO SAVEPOINT work_event_apply")
        con.execute("RELEASE SAVEPOINT work_event_apply")
        raise
    return {"status": decision, "decision": decision, "reason": reason, "task": task}
