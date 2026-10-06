"""Project-owned Reminders effects with reservation and native readback.

Sources and task matching are supplied by the caller. This module never deletes,
renames, moves, or claims an unmarked reminder. Run under a single writer lock.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from typing import Any, Dict


JXA = r'''
function run(argv) {
  var app = Application('Reminders');
  var action = argv[0], p = JSON.parse(argv[1]);
  var account = app.accounts.byId(p.account_id);
  if (account.id() !== p.account_id) throw Error('account_identity_unresolved');
  if (action === 'lists') return JSON.stringify(account.lists().map(function(l) {
    return {id:l.id(), name:l.name(), account_id:account.id()};
  }));
  if (action === 'ensure_list') {
    var matches = account.lists().filter(function(l) { return l.name() === p.name; });
    if (matches.length > 1) throw Error('duplicate_list_names');
    if (!matches.length) {
      account.lists.push(new app.List({name:p.name}));
      matches = account.lists().filter(function(l) { return l.name() === p.name; });
    }
    if (matches.length !== 1) throw Error('list_readback_failed');
    return JSON.stringify({id:matches[0].id(), name:matches[0].name(), account_id:account.id()});
  }
  var list = account.lists.byId(p.list_id);
  if (list.id() !== p.list_id) throw Error('list_identity_unresolved');
  function info(r) {
    var properties = r.properties();
    var due = properties.dueDate;
    return {id:properties.id, list_id:p.list_id, account_id:p.account_id,
      title:properties.name, body:properties.body || '', completed:properties.completed,
      due_date:due ? due.toISOString() : null};
  }
  if (action === 'snapshot') {
    var ids = list.reminders.id(), titles = list.reminders.name();
    var bodies = list.reminders.body(), complete = list.reminders.completed();
    var dates = list.reminders.dueDate();
    return JSON.stringify(ids.map(function(id, i) {
      return {id:id, list_id:p.list_id, account_id:p.account_id,
        title:titles[i], body:bodies[i] || '', completed:complete[i],
        due_date:dates[i] ? dates[i].toISOString() : null};
    }));
  }
  if (action === 'create') {
    list.reminders.push(new app.Reminder({name:p.title, body:p.body, completed:false}));
    var bodies = list.reminders.body();
    var all = list.reminders();
    var created = all.filter(function(r, i) { return (bodies[i] || '').indexOf(p.marker) !== -1; });
    if (created.length !== 1) throw Error('create_marker_ambiguous');
    return JSON.stringify(info(created[0]));
  }
  var reminder = list.reminders.byId(p.reminder_id);
  if (reminder.id() !== p.reminder_id) throw Error('reminder_identity_unresolved');
  if (action === 'get') return JSON.stringify(info(reminder));
  if (action === 'complete') {
    reminder.completed = p.completed;
    return JSON.stringify(info(reminder));
  }
  throw Error('unsupported_action');
}
'''


class NativeReminders:
    def call(self, action: str, payload: Dict[str, Any]) -> Any:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", JXA, action, json.dumps(payload)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            # Provider content stays out of public error messages.
            raise RuntimeError("native_reminders_action_failed")
        return json.loads(result.stdout)


def initialize(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS reminder_effects (
        task_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL, marker TEXT NOT NULL,
        status TEXT NOT NULL, reminder_id TEXT, receipt_json TEXT, error TEXT
    )""")
    con.commit()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _action_title(value: str) -> str:
    for prefix in ("Confirm current status: ", "Evidence needed: "):
        if value.startswith(prefix):
            value = value[len(prefix):]
    return " ".join(value.casefold().split())


def deliver(con: sqlite3.Connection, backend: Any, task: Dict[str, Any]) -> Dict[str, Any]:
    """Reserve, reconcile, create if absent, and verify one exact native item.

    A changed intent requires an explicit later operation, never silent overwrite.
    Marker matches must be unique in the exact account/list. A timeout leaves an
    uncertain reservation that the same request can safely reconcile on retry.
    """
    required = {"task_id", "account_id", "list_id", "title", "body", "source"}
    if required - task.keys() or any(not task[k] for k in required):
        raise ValueError("task_identity_payload_and_provenance_required")
    source = task["source"]
    if not isinstance(source, dict) or {"source_id", "source_version_id", "locator", "excerpt_sha256", "event_date"} - source.keys():
        raise ValueError("source_provenance_required")
    marker = "apple-effect:" + hashlib.sha256(
        _canonical(["trojanhorse", task["task_id"], "create-v1"]).encode()
    ).hexdigest()
    payload = {**task, "body": task["body"].rstrip() + "\n\n" + marker, "completed": False, "due_date": None}
    encoded = _canonical(payload)
    old = con.execute("SELECT payload_json FROM reminder_effects WHERE task_id=?", (task["task_id"],)).fetchone()
    if old and old[0] != encoded:
        return {"status": "conflict", "task_id": task["task_id"], "reason": "intent_changed"}
    con.execute("INSERT OR IGNORE INTO reminder_effects VALUES (?, ?, ?, 'reserved', NULL, NULL, NULL)",
                (task["task_id"], encoded, marker))
    con.commit()  # Durable reservation exists before any native effect.
    target = {"account_id": task["account_id"], "list_id": task["list_id"]}
    try:
        items = backend.call("snapshot", target)
        matches = [item for item in items if marker in item.get("body", "")]
        if len(matches) > 1:
            raise RuntimeError("multiple_marker_matches")
        if not matches:
            if any(_action_title(item["title"]) == _action_title(task["title"]) for item in items):
                con.execute("UPDATE reminder_effects SET status='pending', error='unmarked_plausible_match' WHERE task_id=?", (task["task_id"],))
                con.commit()
                return {"status": "pending", "task_id": task["task_id"], "reason": "unmarked_plausible_match"}
            created = backend.call("create", {**target, "title": payload["title"], "body": payload["body"], "marker": marker})
            reminder_id = created["id"]
            created_now = True
        else:
            reminder_id = matches[0]["id"]
            created_now = False
        con.execute("UPDATE reminder_effects SET reminder_id=? WHERE task_id=?", (reminder_id, task["task_id"]))
        con.commit()
        actual = backend.call("get", {**target, "reminder_id": reminder_id})
        fields = ("account_id", "list_id", "title", "body", "completed", "due_date")
        if any(actual.get(key) != payload[key] for key in fields):
            raise RuntimeError("native_readback_conflict")
        receipt = {"status": "verified", "task_id": task["task_id"], "created_now": created_now,
                   "native": actual, "source": source, "payload_sha256": hashlib.sha256(encoded.encode()).hexdigest()}
        con.execute("UPDATE reminder_effects SET status='verified', receipt_json=?, error=NULL WHERE task_id=?",
                    (_canonical(receipt), task["task_id"]))
        con.commit()
        return receipt
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, ValueError, KeyError) as exc:
        reason = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        con.execute("UPDATE reminder_effects SET status='uncertain', error=? WHERE task_id=?", (reason, task["task_id"]))
        con.commit()
        return {"status": "uncertain", "task_id": task["task_id"], "reason": reason}


def owner_completion_changes(con: sqlite3.Connection, backend: Any) -> list:
    """Read-only observation; it never writes the ledger's old state back."""
    changes = []
    for task_id, raw, reminder_id in con.execute(
        "SELECT task_id, payload_json, reminder_id FROM reminder_effects WHERE status='verified'"
    ):
        payload = json.loads(raw)
        actual = backend.call("get", {"account_id": payload["account_id"], "list_id": payload["list_id"], "reminder_id": reminder_id})
        if actual["completed"] != payload["completed"]:
            changes.append({"task_id": task_id, "completed": actual["completed"], "reminder_id": reminder_id,
                            "owner_fields_changed": any(actual.get(k) != payload.get(k) for k in ("title", "body", "due_date"))})
    return changes
