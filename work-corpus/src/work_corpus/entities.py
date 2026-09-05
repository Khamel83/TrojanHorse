"""Deterministic canonical entities, aliases, and scope proposals.

This module deliberately has no model or network boundary.  It only applies
the reviewed local dictionary and conservative string rules.  Uncertain
matches are retained as provenance-backed review items; they are never
silently merged.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .db import record_review_item
from .util import now_iso, stable_id


VALID_ALIAS_STATUSES = {"valid", "approved", "accepted", "confirmed", "canonical"}
ENTITY_TYPES = {"project", "person", "organization"}


@dataclass(frozen=True)
class EntityMatch:
    """The result of resolving one original mention."""

    entity_id: Optional[str]
    canonical_name: Optional[str]
    original_mention: str
    rule: str
    status: str
    confidence: float
    mention_id: Optional[str] = None
    review_id: Optional[str] = None
    candidate_entity_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ScopeProposal:
    scope: str
    sensitivity: str
    status: str
    review_id: Optional[str]
    reason: str


def normalize_name(value: str, regex_rules: Optional[Sequence[Mapping[str, str]]] = None) -> str:
    """Return a conservative comparison key without changing source text."""
    text = str(value or "").strip().casefold()
    for rule in regex_rules or ():
        pattern = rule.get("pattern", "")
        replacement = rule.get("replacement", "")
        if pattern:
            text = re.sub(pattern, replacement, text)
    text = text.replace("&", " and ")
    text = text.replace("’", "'")
    text = re.sub(r"['`]", "", text)
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _exact_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _status_is_valid(value: Optional[str]) -> bool:
    return str(value or "").casefold() in VALID_ALIAS_STATUSES


def _alias_id(
    entity_id: str,
    alias: str,
    source_system: Optional[str],
    valid_from: Optional[str],
    valid_to: Optional[str],
) -> str:
    return stable_id(
        "alias",
        entity_id,
        normalize_name(alias),
        source_system or "",
        valid_from or "",
        valid_to or "",
    )


def create_entity(
    con: sqlite3.Connection,
    entity_type: str,
    stable_key: str,
    canonical_name: str,
    *,
    status: str = "active",
    confidence: Optional[float] = 1.0,
) -> str:
    """Create or refresh an entity whose ID does not depend on its name."""
    entity_type = str(entity_type).casefold().strip()
    stable_key = str(stable_key).strip()
    canonical_name = str(canonical_name).strip()
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"unsupported entity type: {entity_type}")
    if not stable_key:
        raise ValueError("stable_key is required")
    if not canonical_name:
        raise ValueError("canonical_name is required")

    entity_id = stable_id("entity", entity_type, stable_key)
    timestamp = now_iso()
    con.execute(
        """
        INSERT INTO entity (
            entity_id, entity_type, canonical_name, status, confidence,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET
            entity_type=excluded.entity_type,
            canonical_name=excluded.canonical_name,
            status=excluded.status,
            confidence=excluded.confidence,
            updated_at=excluded.updated_at
        """,
        (
            entity_id,
            entity_type,
            canonical_name,
            status,
            confidence,
            timestamp,
            timestamp,
        ),
    )
    return entity_id


def add_alias(
    con: sqlite3.Connection,
    entity_id: str,
    alias: str,
    *,
    source_system: Optional[str] = None,
    evidence_id: Optional[str] = None,
    valid_from: Optional[str] = None,
    valid_to: Optional[str] = None,
    rule: str = "dictionary",
    confidence: Optional[float] = 1.0,
    review_status: str = "valid",
) -> str:
    """Add an evidence-linked alias while retaining effective dates."""
    alias = str(alias).strip()
    if not alias:
        raise ValueError("alias is required")
    alias_id = _alias_id(entity_id, alias, source_system, valid_from, valid_to)
    con.execute(
        """
        INSERT INTO entity_alias (
            alias_id, entity_id, evidence_id, alias, source_system,
            valid_from, valid_to, rule, confidence, review_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(alias_id) DO UPDATE SET
            evidence_id=COALESCE(excluded.evidence_id, entity_alias.evidence_id),
            alias=excluded.alias,
            rule=excluded.rule,
            confidence=excluded.confidence,
            review_status=excluded.review_status
        """,
        (
            alias_id,
            entity_id,
            evidence_id,
            alias,
            source_system,
            valid_from,
            valid_to,
            rule,
            confidence,
            review_status,
            now_iso(),
        ),
    )
    return alias_id


def _candidate_rows(
    con: sqlite3.Connection,
    *,
    source_system: Optional[str],
) -> List[sqlite3.Row]:
    rows = con.execute(
        """
        SELECT a.alias_id, a.entity_id, a.alias, a.source_system, a.rule,
               a.confidence AS alias_confidence, a.review_status,
               e.entity_type, e.canonical_name, e.confidence AS entity_confidence
        FROM entity_alias a
        JOIN entity e ON e.entity_id=a.entity_id
        WHERE LOWER(a.review_status) IN ('valid', 'approved', 'accepted', 'confirmed', 'canonical')
        ORDER BY a.entity_id, a.alias_id
        """
    ).fetchall()
    if source_system is None:
        return [row for row in rows if row["source_system"] is None]
    source_key = source_system.casefold()
    return [
        row
        for row in rows
        if row["source_system"] is None
        or str(row["source_system"]).casefold() == source_key
    ]


def _candidate_entities(
    con: sqlite3.Connection,
    mention: str,
    *,
    source_system: Optional[str],
    source_identifier: Optional[str],
    regex_rules: Optional[Sequence[Mapping[str, str]]],
) -> Tuple[List[sqlite3.Row], str]:
    rows = _candidate_rows(con, source_system=source_system)
    entities = con.execute(
        "SELECT entity_id, canonical_name, entity_type, confidence FROM entity ORDER BY entity_id"
    ).fetchall()
    exact = _exact_key(mention)
    exact_rows = [row for row in rows if _exact_key(row["alias"]) == exact]
    exact_rows.extend(
        {
            "alias_id": None,
            "entity_id": row["entity_id"],
            "alias": row["canonical_name"],
            "source_system": None,
            "rule": "canonical",
            "alias_confidence": row["confidence"],
            "review_status": "canonical",
            "entity_type": row["entity_type"],
            "canonical_name": row["canonical_name"],
            "entity_confidence": row["confidence"],
        }
        for row in entities
        if _exact_key(row["canonical_name"]) == exact
    )
    if exact_rows:
        return _unique_candidate_rows(exact_rows), "exact_alias"

    normal = normalize_name(mention, regex_rules)
    normalized_rows = [row for row in rows if normalize_name(row["alias"], regex_rules) == normal]
    normalized_rows.extend(
        {
            "alias_id": None,
            "entity_id": row["entity_id"],
            "alias": row["canonical_name"],
            "source_system": None,
            "rule": "canonical",
            "alias_confidence": row["confidence"],
            "review_status": "canonical",
            "entity_type": row["entity_type"],
            "canonical_name": row["canonical_name"],
            "entity_confidence": row["confidence"],
        }
        for row in entities
        if normalize_name(row["canonical_name"], regex_rules) == normal
    )
    if normalized_rows:
        return _unique_candidate_rows(normalized_rows), "normalized_alias"

    if source_identifier:
        identifier = _exact_key(source_identifier)
        identifier_rows = [
            row
            for row in rows
            if _exact_key(row["alias"]) == identifier
            and row["source_system"] is not None
            and source_system is not None
            and str(row["source_system"]).casefold() == source_system.casefold()
        ]
        if identifier_rows:
            return _unique_candidate_rows(identifier_rows), "source_identifier"

    return [], "unresolved"


def _unique_candidate_rows(rows: Iterable[sqlite3.Row]) -> List[sqlite3.Row]:
    output: List[sqlite3.Row] = []
    seen: set[str] = set()
    for row in rows:
        entity_id = str(row["entity_id"])
        if entity_id not in seen:
            output.append(row)
            seen.add(entity_id)
    return output


def _mention_id(
    original_mention: str,
    evidence_id: Optional[str],
    location: str,
    rule: str,
    entity_id: Optional[str],
) -> str:
    return stable_id(
        "entity-mention",
        evidence_id or "",
        location,
        original_mention,
        rule,
        entity_id or "",
    )


def _record_mention(
    con: sqlite3.Connection,
    *,
    evidence_id: Optional[str],
    original_mention: str,
    location: str,
    entity_id: Optional[str],
    status: str,
    rule: str,
) -> Optional[str]:
    if not evidence_id:
        return None
    mention_id = _mention_id(original_mention, evidence_id, location, rule, entity_id)
    con.execute(
        """
        INSERT INTO entity_mention (
            mention_id, evidence_id, entity_id, original_mention,
            location, resolution_status, rule, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(mention_id) DO UPDATE SET
            entity_id=excluded.entity_id,
            resolution_status=excluded.resolution_status,
            rule=excluded.rule
        """,
        (
            mention_id,
            evidence_id,
            entity_id,
            original_mention,
            location,
            status,
            rule,
            now_iso(),
        ),
    )
    return mention_id


def resolve_mention(
    con: sqlite3.Connection,
    mention: str,
    *,
    evidence_id: Optional[str] = None,
    source_id: Optional[str] = None,
    location: str = "document",
    source_system: Optional[str] = None,
    source_identifier: Optional[str] = None,
    context: Optional[Mapping[str, Any]] = None,
    regex_rules: Optional[Sequence[Mapping[str, str]]] = None,
    frequencies: Optional[Mapping[str, int]] = None,
) -> EntityMatch:
    """Resolve one mention, or create a review proposal for uncertainty."""
    original = str(mention)
    context_payload = dict(context or {})
    rows, rule = _candidate_entities(
        con,
        original,
        source_system=source_system,
        source_identifier=source_identifier,
        regex_rules=regex_rules,
    )
    candidate_ids = tuple(sorted({str(row["entity_id"]) for row in rows}))
    if len(candidate_ids) == 1:
        entity_id = candidate_ids[0]
        entity_row = con.execute(
            "SELECT canonical_name, confidence FROM entity WHERE entity_id=?",
            (entity_id,),
        ).fetchone()
        confidence = float(entity_row["confidence"] or 0.0) if entity_row else 0.0
        canonical_name = entity_row["canonical_name"] if entity_row else None
        match_rule = rule
        if frequencies and entity_row is not None:
            selected = select_canonical_name(
                con,
                entity_id,
                frequencies,
                apply=False,
            )
            if selected != canonical_name:
                canonical_name = selected
                match_rule = "frequency_valid_name"
        mention_id = _record_mention(
            con,
            evidence_id=evidence_id,
            original_mention=original,
            location=location,
            entity_id=entity_id,
            status="resolved",
            rule=match_rule,
        )
        return EntityMatch(
            entity_id=entity_id,
            canonical_name=canonical_name,
            original_mention=original,
            rule=match_rule,
            status="resolved",
            confidence=confidence,
            mention_id=mention_id,
            candidate_entity_ids=candidate_ids,
        )

    if len(candidate_ids) > 1:
        issue_type = "entity_collision"
        proposed = {
            "original_mention": original,
            "candidate_entity_ids": list(candidate_ids),
            "context": context_payload,
            "action": "keep_separate_until_review",
        }
        review_id = record_review_item(
            con,
            issue_type=issue_type,
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result=proposed,
            reason="Multiple valid entities share this alias; context is required before any merge.",
            confidence=0.0,
        )
        status = "review"
        review_rule = "collision_review"
    else:
        proposed = {
            "original_mention": original,
            "source_system": source_system,
            "source_identifier": source_identifier,
            "context": context_payload,
            "action": "add_alias_or_resolve",
        }
        review_id = record_review_item(
            con,
            issue_type="entity_unresolved",
            source_id=source_id,
            evidence_id=evidence_id,
            proposed_result=proposed,
            reason="No valid exact, normalized, or source-specific alias matched.",
            confidence=0.0,
        )
        status = "review"
        review_rule = "unresolved_review"

    mention_id = _record_mention(
        con,
        evidence_id=evidence_id,
        original_mention=original,
        location=location,
        entity_id=None,
        status=status,
        rule=review_rule,
    )
    return EntityMatch(
        entity_id=None,
        canonical_name=None,
        original_mention=original,
        rule=review_rule,
        status=status,
        confidence=0.0,
        mention_id=mention_id,
        review_id=review_id,
        candidate_entity_ids=candidate_ids,
    )


def select_canonical_name(
    con: sqlite3.Connection,
    entity_id: str,
    frequencies: Mapping[str, int],
    *,
    apply: bool = False,
) -> str:
    """Choose the most frequent valid spelling; invalid aliases never win."""
    entity = con.execute(
        "SELECT canonical_name FROM entity WHERE entity_id=?", (entity_id,)
    ).fetchone()
    if entity is None:
        raise ValueError(f"unknown entity: {entity_id}")
    candidates = [(entity["canonical_name"], True)]
    candidates.extend(
        (
            row["alias"],
            _status_is_valid(row["review_status"]),
        )
        for row in con.execute(
            "SELECT alias, review_status FROM entity_alias WHERE entity_id=?",
            (entity_id,),
        )
    )
    valid = [name for name, is_valid in candidates if is_valid]
    selected = sorted(
        valid,
        key=lambda name: (
            -int(
                frequencies.get(
                    name,
                    frequencies.get(normalize_name(name), 0),
                )
            ),
            normalize_name(name),
            name,
        ),
    )[0]
    if apply and selected != entity["canonical_name"]:
        con.execute(
            "UPDATE entity SET canonical_name=?, updated_at=? WHERE entity_id=?",
            (selected, now_iso(), entity_id),
        )
    return selected


def record_scope_proposal(
    con: sqlite3.Connection,
    source_id: str,
    proposed_scope: str,
    *,
    evidence_id: Optional[str] = None,
    sensitivity: str = "unknown",
    reason: str = "",
) -> Optional[str]:
    """Accept clear work scope; retain every other scope as a review item."""
    scope = str(proposed_scope or "Unknown").strip().title()
    if scope == "Work":
        return None
    if scope not in {"Personal", "Mixed", "Unknown"}:
        scope = "Unknown"
    return record_review_item(
        con,
        issue_type="scope_review",
        source_id=source_id,
        evidence_id=evidence_id,
        proposed_result={
            "scope": scope,
            "sensitivity": sensitivity,
            "resolution_required": True,
        },
        reason=reason or "Scope is not clear work-only evidence.",
        confidence=0.0 if scope == "Unknown" else 0.5,
    )


def load_alias_dictionary(path: Path) -> Dict[str, Any]:
    """Load the local-only dictionary template without contacting a provider."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("entity alias dictionary must be a JSON object")
    entities = payload.get("entities", [])
    if not isinstance(entities, list):
        raise ValueError("entity alias dictionary entities must be a list")
    return payload


def seed_alias_dictionary(
    con: sqlite3.Connection,
    payload: Mapping[str, Any],
    *,
    evidence_id: Optional[str] = None,
) -> List[str]:
    """Seed only explicit local dictionary entries; no names are inferred."""
    entity_ids: List[str] = []
    for item in payload.get("entities", []):
        if not isinstance(item, Mapping):
            continue
        entity_id = create_entity(
            con,
            str(item.get("type", "")),
            str(item.get("key", "")),
            str(item.get("canonical_name", "")),
            status=str(item.get("status", "active")),
            confidence=float(item.get("confidence", 1.0)),
        )
        entity_ids.append(entity_id)
        aliases = item.get("aliases", [])
        if isinstance(aliases, Mapping):
            aliases = [{"alias": key, **(value if isinstance(value, Mapping) else {})} for key, value in aliases.items()]
        for alias in aliases:
            if isinstance(alias, str):
                alias = {"alias": alias}
            if not isinstance(alias, Mapping):
                continue
            add_alias(
                con,
                entity_id,
                str(alias.get("alias", "")),
                source_system=alias.get("source_system"),
                evidence_id=alias.get("evidence_id") or evidence_id,
                valid_from=alias.get("valid_from"),
                valid_to=alias.get("valid_to"),
                rule=str(alias.get("rule", "dictionary")),
                confidence=float(alias.get("confidence", 1.0)),
                review_status=str(alias.get("review_status", "valid")),
            )
    return entity_ids


class EntityResolver:
    """Small object wrapper around the deterministic functional API."""

    def __init__(
        self,
        con: sqlite3.Connection,
        *,
        regex_rules: Optional[Sequence[Mapping[str, str]]] = None,
    ) -> None:
        self.con = con
        self.regex_rules = regex_rules

    def create(self, entity_type: str, stable_key: str, canonical_name: str, **kwargs: Any) -> str:
        return create_entity(self.con, entity_type, stable_key, canonical_name, **kwargs)

    def add_alias(self, entity_id: str, alias: str, **kwargs: Any) -> str:
        return add_alias(self.con, entity_id, alias, **kwargs)

    def resolve(self, mention: str, **kwargs: Any) -> EntityMatch:
        kwargs.setdefault("regex_rules", self.regex_rules)
        return resolve_mention(self.con, mention, **kwargs)

    def choose_canonical(self, entity_id: str, frequencies: Mapping[str, int], *, apply: bool = False) -> str:
        return select_canonical_name(self.con, entity_id, frequencies, apply=apply)


def resolve_mentions(
    con: sqlite3.Connection,
    mentions: Iterable[str],
    **kwargs: Any,
) -> List[EntityMatch]:
    """Resolve a deterministic sequence while preserving each mention."""
    return [resolve_mention(con, mention, **kwargs) for mention in mentions]
