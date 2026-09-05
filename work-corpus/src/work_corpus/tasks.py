"""Explicit, provenance-backed task proposals.

Task extraction is intentionally a small deterministic pass.  It recognizes
clear assignments, promises, deliverables, and follow-ups.  It does not use a
generic classifier, an external model, or an old source date as permission to
create a current backlog.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, List, Mapping, Optional, Union

from .db import record_review_item
from .util import now_iso, stable_id


ReliableDate = Union[str, date, datetime]
RELIABLE_DATE_BASES = {"event", "event_date", "meeting", "meeting_date"}
EXPLICIT_PATTERNS = (
    re.compile(r"^(?:please|kindly)\s+(?P<action>.+)$", re.IGNORECASE),
    re.compile(r"^(?:action\s+item|todo|to-do|deliverable)\s*[:\-]\s*(?P<action>.+)$", re.IGNORECASE),
    re.compile(r"^(?:follow\s*[- ]?up)(?:\s+on|\s+with|\s*[:\-])?\s*(?P<action>.+)$", re.IGNORECASE),
    re.compile(r"^(?:i|we|you)\s+(?:will|'ll|need\s+to|promise\s+to|must)\s+(?P<action>.+)$", re.IGNORECASE),
)
NON_TASK_CLAIM_PATTERNS = (
    re.compile(
        r"^(?:be|become)\s+(?:promoted|appointed|hired|fired|recognized|"
        r"awarded|selected|named|responsible|successful|ready|available|"
        r"a|an|the)\b",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:earn|receive|secure|land)\s+(?:a|an|the)\s+promotion\b", re.IGNORECASE),
    re.compile(
        r"^(?:advance|progress|further)\s+(?:my|your|their|one's)\s+career\b",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class TaskProposal:
    task_id: Optional[str]
    action: str
    status: str
    source_evidence_id: str
    source_event_date: Optional[str]
    source_date_basis: str
    review_id: Optional[str] = None
    reason: str = ""


def _date_value(value: Optional[ReliableDate]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    value = str(value).strip()
    if not value:
        return None
    candidate = value[:10]
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def _run_date(value: Optional[ReliableDate]) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _sentences(text: str) -> List[str]:
    return [
        part.strip().lstrip("-*• ").strip()
        for part in re.split(r"(?:\r?\n+)|(?<=[.!?])\s+", text)
        if part.strip().lstrip("-*• ").strip()
    ]


def _explicit_action(sentence: str) -> Optional[str]:
    candidate = sentence.strip().strip(".;: ")
    for pattern in EXPLICIT_PATTERNS:
        match = pattern.match(candidate)
        if match:
            action = re.sub(r"\s+", " ", match.group("action").strip(" .;:"))
            if (
                action
                and not re.match(r"^(?:maybe|possibly|we should)\b", action, re.IGNORECASE)
                and not any(pattern.match(action) for pattern in NON_TASK_CLAIM_PATTERNS)
            ):
                return action
    return None


def is_current_task_date(
    event_date: Optional[ReliableDate],
    source_date_basis: Optional[str],
    run_date: Optional[ReliableDate],
) -> bool:
    """Apply the inclusive fourteen-day boundary to event/meeting dates only."""
    value = _date_value(event_date)
    basis = str(source_date_basis or "").casefold().strip()
    if not value or basis not in RELIABLE_DATE_BASES:
        return False
    observed = date.fromisoformat(value)
    effective_run_date = _run_date(run_date)
    return observed >= effective_run_date - timedelta(days=14) or observed > effective_run_date


def _task_id(
    source_evidence_id: str,
    action: str,
    event_date: Optional[str],
    source_date_basis: str,
) -> str:
    return stable_id(
        "task",
        source_evidence_id,
        re.sub(r"\s+", " ", action.casefold().strip()),
        event_date or "",
        source_date_basis.casefold().strip(),
    )


def _review(
    con: sqlite3.Connection,
    *,
    issue_type: str,
    source_id: Optional[str],
    evidence_id: str,
    action: str,
    event_date: Optional[str],
    source_date_basis: str,
    status: str,
    reason: str,
) -> str:
    return record_review_item(
        con,
        issue_type=issue_type,
        source_id=source_id,
        evidence_id=evidence_id,
        proposed_result={
            "action": action,
            "source_evidence_id": evidence_id,
            "source_event_date": event_date,
            "source_date_basis": source_date_basis,
            "eligibility_status": status,
        },
        reason=reason,
        confidence=1.0 if status == "accepted" else 0.0,
        status="accepted" if status == "accepted" else "pending",
    )


def _insert_task(
    con: sqlite3.Connection,
    *,
    task_id: str,
    action: str,
    source_evidence_id: str,
    event_date: str,
    source_date_basis: str,
) -> None:
    timestamp = now_iso()
    con.execute(
        """
        INSERT INTO task (
            task_id, action, source_event_date, event_date, due_date,
            candidate_status, task_status, source_evidence_id,
            source_date_basis, source_date, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, NULL, 'accepted', 'open', ?, ?, ?, 'open', ?, ?)
        ON CONFLICT(task_id) DO UPDATE SET
            action=excluded.action,
            source_event_date=excluded.source_event_date,
            event_date=excluded.event_date,
            candidate_status=CASE
                WHEN task.candidate_status IN ('completed', 'dismissed')
                THEN task.candidate_status ELSE excluded.candidate_status END,
            task_status=CASE
                WHEN task.task_status IN ('completed', 'cancelled', 'dismissed')
                THEN task.task_status ELSE excluded.task_status END,
            source_evidence_id=excluded.source_evidence_id,
            source_date_basis=excluded.source_date_basis,
            source_date=excluded.source_date,
            updated_at=excluded.updated_at
        """,
        (
            task_id,
            action,
            event_date,
            event_date,
            source_evidence_id,
            source_date_basis,
            event_date,
            timestamp,
            timestamp,
        ),
    )


def extract_task_proposals(
    con: sqlite3.Connection,
    text: str,
    *,
    source_evidence_id: str,
    source_id: Optional[str] = None,
    source_event_date: Optional[ReliableDate] = None,
    source_date_basis: str = "",
    run_date: Optional[ReliableDate] = None,
    scope: str = "Work",
    commit: bool = True,
) -> List[TaskProposal]:
    """Extract and persist only explicit task candidates from synthetic text."""
    event_date = _date_value(source_event_date)
    basis = str(source_date_basis or "").casefold().strip()
    proposals: List[TaskProposal] = []
    seen_actions: set[str] = set()
    for sentence in _sentences(text):
        action = _explicit_action(sentence)
        if not action:
            continue
        action_key = re.sub(r"\s+", " ", action.casefold())
        if action_key in seen_actions:
            continue
        seen_actions.add(action_key)

        if str(scope or "Unknown").casefold() != "work":
            reason = "Task source scope is not resolved to Work."
            review_id = _review(
                con,
                issue_type="task_scope_review",
                source_id=source_id,
                evidence_id=source_evidence_id,
                action=action,
                event_date=event_date,
                source_date_basis=basis,
                status="review",
                reason=reason,
            )
            proposals.append(
                TaskProposal(
                    None,
                    action,
                    "review",
                    source_evidence_id,
                    event_date,
                    basis,
                    review_id,
                    reason,
                )
            )
            continue

        if not is_current_task_date(event_date, basis, run_date):
            if not event_date or basis not in RELIABLE_DATE_BASES:
                reason = "A reliable event or meeting date is required before a task can be current."
            else:
                reason = "The source event is older than the inclusive fourteen-day current-task window."
            review_id = _review(
                con,
                issue_type="task_date_review",
                source_id=source_id,
                evidence_id=source_evidence_id,
                action=action,
                event_date=event_date,
                source_date_basis=basis,
                status="historical" if event_date and basis in RELIABLE_DATE_BASES else "review",
                reason=reason,
            )
            proposals.append(
                TaskProposal(
                    None,
                    action,
                    "historical" if event_date and basis in RELIABLE_DATE_BASES else "review",
                    source_evidence_id,
                    event_date,
                    basis,
                    review_id,
                    reason,
                )
            )
            continue

        task_id = _task_id(source_evidence_id, action, event_date, basis)
        _insert_task(
            con,
            task_id=task_id,
            action=action,
            source_evidence_id=source_evidence_id,
            event_date=event_date or "",
            source_date_basis=basis,
        )
        reason = "Explicit assignment, promise, deliverable, or follow-up with an eligible event date."
        review_id = _review(
            con,
            issue_type="task_proposal",
            source_id=source_id,
            evidence_id=source_evidence_id,
            action=action,
            event_date=event_date,
            source_date_basis=basis,
            status="accepted",
            reason=reason,
        )
        proposals.append(
            TaskProposal(
                task_id,
                action,
                "accepted",
                source_evidence_id,
                event_date,
                basis,
                review_id,
                reason,
            )
        )
    if commit:
        con.commit()
    return proposals


propose_tasks = extract_task_proposals
extract_tasks = extract_task_proposals
