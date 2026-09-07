"""Deterministic, local-only queries over the provenance-first corpus.

The default query path searches the unified private corpus.  ``Work`` remains
an explicit narrower filter, while original scope and classification labels
stay attached to every hit as provenance.  Raw fallback is read-only and is
never written to the corpus or the FTS table.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .util import read_text_guess, scrub_derived_text


ALL_SCOPE = "All"
WORK_SCOPE = "Work"
DEFAULT_SCOPE = ALL_SCOPE
MAX_QUESTION_LENGTH = 2_000
MAX_RAW_BYTES = 2 * 1024 * 1024
DEFAULT_LIMIT = 20

EVIDENCE_LABELS = frozenset(
    {
        "canonical",
        "derived_reviewed",
        "derived_unreviewed",
        "raw_work",
        "raw_source",
        "inference",
        "conflict",
        "missing",
        "excluded_scope",
    }
)

_SOURCE_FACT_LABELS = frozenset(
    {
        "canonical",
        "derived_reviewed",
        "derived_unreviewed",
        "raw_work",
        "raw_source",
    }
)
_FTS_TOKEN_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BEARER_RE = re.compile(
    r"(?P<prefix>\b(?:authorization\s*:\s*)?bearer\s+)"
    r"(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)
_SECRET_RE = re.compile(
    r"(?P<prefix>\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
    r"client[_ -]?secret|secret[_ -]?key|token|credential|password|passwd)"
    r"\b\s*[:=]\s*)(?P<quote>[\"']?)(?P<value>[^\"'\s,;]+)"
    r"(?P=quote)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(
    r"\b(?:eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|"
    r"AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})\b"
)
_REBUILD_CANDIDATE_LIKE = (
    "%http%",
    "%api%key%",
    "%secret%",
    "%token%",
    "%credential%",
    "%password%",
    "%passwd%",
    "%bearer%",
    "%authorization%",
    "%private%key%",
    "%akia%",
    "%asia%",
    "%sk-%",
    "%eyj%",
)


class QueryValidationError(ValueError):
    """Raised when a query would violate the local query contract."""


def validate_question(question: str) -> str:
    """Validate and normalize one human query without interpreting its meaning."""
    if not isinstance(question, str):
        raise QueryValidationError("question must be text")
    value = question.strip()
    if not value:
        raise QueryValidationError("question must not be empty")
    if "\x00" in value:
        raise QueryValidationError("question must not contain NUL characters")
    if len(value) > MAX_QUESTION_LENGTH:
        raise QueryValidationError(
            f"question must be at most {MAX_QUESTION_LENGTH} characters"
        )
    if not re.search(r"[\w]", value, re.UNICODE):
        raise QueryValidationError("question must contain a searchable character")
    return value


def _validate_scope(scope: str) -> str:
    value = str(scope or DEFAULT_SCOPE).strip()
    for allowed in (ALL_SCOPE, WORK_SCOPE):
        if value.casefold() == allowed.casefold():
            return allowed
    raise QueryValidationError("scope must be All or Work")


def redact_snippet(value: str) -> str:
    """Redact URL and secret-like values from displayed or indexed text.

    ``scrub_derived_text`` is the shared extractor redactor.  The additional
    URL pass here is intentional: ordinary URLs are also unsafe to display in
    a query snippet even when they do not carry a signed query string.
    """
    text = scrub_derived_text(str(value or ""))
    text = _URL_RE.sub("[REDACTED_URL]", text)
    text = _BEARER_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED_SECRET]", text
    )
    text = _SECRET_RE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}"
            "[REDACTED_SECRET]"
            f"{match.group('quote')}"
        ),
        text,
    )
    return _TOKEN_RE.sub("[REDACTED_SECRET]", text)


def rebuild_search_index(con: sqlite3.Connection) -> int:
    """Scrub existing derived FTS rows in place and return changed-row count.

    The FTS table is derived state.  This function never reads or writes the
    immutable raw source records, and it is safe to run repeatedly.
    """
    predicates = " OR ".join(
        "lower(COALESCE(derived_text, '')) LIKE ?"
        for _term in _REBUILD_CANDIDATE_LIKE
    )
    rows = con.execute(
        "SELECT rowid, derived_text FROM derived_text_fts "
        f"WHERE {predicates} ORDER BY rowid",
        _REBUILD_CANDIDATE_LIKE,
    ).fetchall()
    changed = 0
    for row in rows:
        original = row["derived_text"] or ""
        scrubbed = redact_snippet(original)
        if scrubbed == original:
            continue
        con.execute(
            "UPDATE derived_text_fts SET derived_text=? WHERE rowid=?",
            (scrubbed, row["rowid"]),
        )
        changed += 1
    if changed:
        con.commit()
    return changed


def _fts_query(question: str) -> Optional[str]:
    tokens = _FTS_TOKEN_RE.findall(question)
    if not tokens:
        return None
    # Quoted tokens keep punctuation from becoming FTS syntax.  AND makes the
    # fallback deterministic and avoids a broad OR search over unrelated text.
    return " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)


def _scope_sql(alias: str = "s", scope: str = WORK_SCOPE) -> str:
    """Return the validated scope predicate used by evidence joins."""
    if scope.casefold() == ALL_SCOPE.casefold():
        return "1=1"
    return f"LOWER(COALESCE({alias}.classification, {alias}.scope, 'Unknown')) = 'work'"


def _date_subqueries() -> str:
    return """
        COALESCE(
            (SELECT date_value FROM date_observation
             WHERE evidence_id=e.evidence_id
             ORDER BY observation_id LIMIT 1),
            (SELECT date_value FROM date_observation
             WHERE source_version_id=v.source_version_id
             ORDER BY observation_id LIMIT 1)
        ) AS observed_date,
        COALESCE(
            (SELECT basis FROM date_observation
             WHERE evidence_id=e.evidence_id
             ORDER BY observation_id LIMIT 1),
            (SELECT basis FROM date_observation
             WHERE source_version_id=v.source_version_id
             ORDER BY observation_id LIMIT 1)
        ) AS observed_date_basis
    """


def _evidence_select() -> str:
    return f"""
        SELECT
            e.evidence_id,
            e.source_version_id,
            e.locator,
            e.derived_text_path,
            e.text_sha256,
            e.evidence_status,
            s.source_id,
            s.relative_path AS source_path,
            s.absolute_path,
            s.source_system,
            s.scope,
            s.classification,
            s.sensitivity,
            s.date_hint,
            s.metadata_json,
            v.content_sha256,
            f.derived_text AS derived_text,
            {_date_subqueries()}
        FROM evidence_record e
        JOIN source_version v ON v.source_version_id=e.source_version_id
        JOIN source_record s ON s.source_id=v.source_id
    """


def _metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    value = row.get("metadata_json")
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _date_fields(row: Mapping[str, Any]) -> Tuple[Optional[str], str]:
    value = row.get("observed_date") or row.get("date_hint") or None
    basis = row.get("observed_date_basis")
    if not basis:
        basis = _metadata(row).get("source_date_basis")
    if not basis and row.get("date_hint"):
        basis = "filename_hint"
    return (str(value) if value else None, str(basis or "not_observed"))


def _label_for_status(status: Any) -> str:
    value = str(status or "derived_unreviewed").casefold().strip()
    if value in EVIDENCE_LABELS:
        return value
    if value in {"derived", "normalized", "normalised", "metadata", "reviewed"}:
        return "derived_unreviewed"
    if value in {"source", "fact", "direct", "confirmed", "accepted"}:
        return "canonical"
    if value in {"model_inference", "local_inference", "inferred"}:
        return "inference"
    if value in {"unresolved_conflict", "conflicting", "disputed"}:
        return "conflict"
    if value in {"not_found", "unavailable", "unresolved"}:
        return "missing"
    return "derived_unreviewed"


def _scope_for_row(row: Mapping[str, Any]) -> str:
    row = dict(row)
    value = row.get("classification") or row.get("scope") or "Unknown"
    normalized = str(value).strip().casefold()
    return {
        "work": "Work",
        "personal": "Personal",
        "mixed": "Mixed",
        "unknown": "Unknown",
    }.get(normalized, str(value))


def _hit_from_row(
    row: Mapping[str, Any],
    *,
    match_type: str,
    snippet: Optional[str] = None,
    label_override: Optional[str] = None,
) -> Dict[str, Any]:
    date_value, date_basis = _date_fields(row)
    label = label_override or _label_for_status(row.get("evidence_status"))
    displayed = snippet
    if displayed is None:
        displayed = row.get("derived_text") or ""
    hit = {
        "label": label,
        "evidence_status": row.get("evidence_status"),
        "evidence_id": row.get("evidence_id"),
        "source_path": row.get("source_path"),
        "relative_path": row.get("source_path"),
        "source_id": row.get("source_id"),
        "source_version_id": row.get("source_version_id"),
        "locator": row.get("locator"),
        "date_basis": date_basis,
        "source_date_basis": date_basis,
        "date_value": date_value,
        "scope": _scope_for_row(row),
        "source_system": row.get("source_system"),
        "sensitivity": row.get("sensitivity"),
        "snippet": redact_snippet(str(displayed)),
        "match_type": match_type,
    }
    return hit


def _work_evidence_rows(
    con: sqlite3.Connection,
    *,
    exact_question: Optional[str] = None,
    fts_query: Optional[str] = None,
    evidence_ids: Optional[Sequence[str]] = None,
    scope: str = DEFAULT_SCOPE,
    diagnostic: bool = False,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    predicates: List[str] = []
    parameters: List[Any] = []
    if not diagnostic and scope.casefold() != ALL_SCOPE.casefold():
        predicates.append(_scope_sql(scope=scope))
    if exact_question is not None:
        predicates.append(
            "(e.evidence_id IN ("
            "SELECT exact_fts.evidence_id FROM derived_text_fts exact_fts "
            "WHERE instr(lower(COALESCE(exact_fts.derived_text, '')), lower(?)) > 0"
            ") "
            "OR instr(lower(e.locator), lower(?)) > 0 "
            "OR instr(lower(COALESCE(s.date_hint, '')), lower(?)) > 0 "
            "OR instr(lower(COALESCE(s.metadata_json, '')), lower(?)) > 0 "
            "OR EXISTS ("
            "SELECT 1 FROM date_observation d "
            "WHERE (d.evidence_id=e.evidence_id "
            "OR d.source_version_id=v.source_version_id) "
            "AND (instr(lower(d.date_value), lower(?)) > 0 "
            "OR instr(lower(d.basis), lower(?)) > 0)"
            ")"
            ")"
        )
        parameters.extend(
            [
                exact_question,
                exact_question,
                exact_question,
                exact_question,
                exact_question,
                exact_question,
            ]
        )
    if evidence_ids is not None:
        if not evidence_ids:
            return []
        placeholders = ", ".join("?" for _ in evidence_ids)
        predicates.append(f"e.evidence_id IN ({placeholders})")
        parameters.extend(evidence_ids)
    if fts_query is not None:
        # Keep MATCH in a subquery.  SQLite does not permit MATCH on the
        # nullable side of a LEFT JOIN, and an alias such as ``f MATCH ?`` is
        # parsed as a reference to a column named f.
        predicates.append(
            "e.evidence_id IN ("
            "SELECT evidence_id FROM derived_text_fts "
            "WHERE derived_text_fts MATCH ?"
            ")"
        )
        parameters.append(fts_query)

    where = " AND ".join(predicates) or "1=1"
    if limit is None:
        sql = f"""
            {_evidence_select()}
            LEFT JOIN derived_text_fts f ON f.evidence_id=e.evidence_id
            WHERE {where}
            ORDER BY s.relative_path, e.locator, e.evidence_id
        """
    else:
        sql = f"""
            WITH candidates AS (
                SELECT DISTINCT e.evidence_id AS evidence_id,
                                s.relative_path AS source_path,
                                e.locator AS locator
                FROM evidence_record e
                JOIN source_version v ON v.source_version_id=e.source_version_id
                JOIN source_record s ON s.source_id=v.source_id
                WHERE {where}
                ORDER BY source_path, locator, evidence_id
                LIMIT ?
            )
            {_evidence_select()}
            LEFT JOIN derived_text_fts f ON f.evidence_id=e.evidence_id
            JOIN candidates c ON c.evidence_id=e.evidence_id
            ORDER BY s.relative_path, e.locator, e.evidence_id
        """
        parameters.append(limit)
    try:
        return con.execute(sql, parameters).fetchall()
    except sqlite3.OperationalError as exc:
        # A malformed FTS expression must not turn a local query into a raw
        # fallback with surprising scope.  The exact path remains available.
        if fts_query is not None and "fts" in str(exc).casefold():
            return []
        raise


def _fetch_evidence_by_ids(
    con: sqlite3.Connection,
    evidence_ids: Iterable[str],
    *,
    scope: str = DEFAULT_SCOPE,
    diagnostic: bool = False,
    limit: Optional[int] = None,
) -> List[sqlite3.Row]:
    unique = sorted({str(value) for value in evidence_ids if value})
    return _work_evidence_rows(
        con,
        evidence_ids=unique,
        scope=scope,
        diagnostic=diagnostic,
        limit=limit,
    )


def exact_search(
    con: sqlite3.Connection,
    question: str,
    *,
    scope: str = DEFAULT_SCOPE,
    diagnostic: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    value = validate_question(question)
    normalized_scope = _validate_scope(scope)
    rows = _work_evidence_rows(
        con,
        exact_question=value,
        scope=normalized_scope,
        diagnostic=diagnostic,
        limit=limit,
    )
    return [
        _hit_from_row(
            dict(row),
            match_type="exact",
            label_override=(
                "excluded_scope"
                if diagnostic and _scope_for_row(row) != WORK_SCOPE
                else None
            ),
        )
        for row in rows
    ]


def fts_search(
    con: sqlite3.Connection,
    question: str,
    *,
    scope: str = DEFAULT_SCOPE,
    diagnostic: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    value = validate_question(question)
    normalized_scope = _validate_scope(scope)
    query_expression = _fts_query(value)
    if not query_expression:
        return []
    rows = _work_evidence_rows(
        con,
        fts_query=query_expression,
        scope=normalized_scope,
        diagnostic=diagnostic,
        limit=limit,
    )
    return [
        _hit_from_row(
            dict(row),
            match_type="fts",
            label_override=(
                "excluded_scope"
                if diagnostic and _scope_for_row(row) != WORK_SCOPE
                else None
            ),
        )
        for row in rows
    ]


def _matching_entity_ids(con: sqlite3.Connection, question: str) -> List[str]:
    pattern = f"%{question.casefold()}%"
    rows = con.execute(
        """
        SELECT entity_id
        FROM entity
        WHERE lower(canonical_name) LIKE ?
           OR entity_id IN (
               SELECT entity_id FROM entity_alias WHERE lower(alias) LIKE ?
           )
        ORDER BY entity_id
        """,
        (pattern, pattern),
    ).fetchall()
    return [str(row["entity_id"]) for row in rows]


def _relationship_evidence_ids(
    con: sqlite3.Connection,
    question: str,
) -> List[str]:
    entity_ids = _matching_entity_ids(con, question)
    evidence_ids: set[str] = set()
    if entity_ids:
        placeholders = ", ".join("?" for _ in entity_ids)
        mentions = con.execute(
            f"SELECT evidence_id FROM entity_mention WHERE entity_id IN ({placeholders})",
            entity_ids,
        ).fetchall()
        evidence_ids.update(str(row["evidence_id"]) for row in mentions)

        relationships = con.execute(
            f"""
            SELECT relationship_id, relationship_type, from_record_type,
                   from_record_id, to_record_type, to_record_id, evidence_id
            FROM relationship
            WHERE (from_record_type IN ('entity', 'project', 'person', 'organization')
                   AND from_record_id IN ({placeholders}))
               OR (to_record_type IN ('entity', 'project', 'person', 'organization')
                   AND to_record_id IN ({placeholders}))
            ORDER BY relationship_id
            """,
            [*entity_ids, *entity_ids],
        ).fetchall()
    else:
        relationships = []

    for row in relationships:
        if row["evidence_id"]:
            evidence_ids.add(str(row["evidence_id"]))
        endpoints = (
            (row["from_record_type"], row["from_record_id"]),
            (row["to_record_type"], row["to_record_id"]),
        )
        for record_type, record_id in endpoints:
            if record_type == "evidence":
                evidence_ids.add(str(record_id))
            elif record_type == "document":
                document = con.execute(
                    "SELECT evidence_id FROM document WHERE document_id=?",
                    (record_id,),
                ).fetchone()
                if document and document["evidence_id"]:
                    evidence_ids.add(str(document["evidence_id"]))
            elif record_type == "task":
                task = con.execute(
                    "SELECT source_evidence_id FROM task WHERE task_id=?",
                    (record_id,),
                ).fetchone()
                if task and task["source_evidence_id"]:
                    evidence_ids.add(str(task["source_evidence_id"]))
            elif record_type == "meeting_group":
                meeting = con.execute(
                    """
                    SELECT transcript_version_id, transcript_source_id
                    FROM meeting_group WHERE group_id=?
                    """,
                    (record_id,),
                ).fetchone()
                if meeting:
                    if meeting["transcript_version_id"]:
                        rows = con.execute(
                            "SELECT evidence_id FROM evidence_record WHERE source_version_id=?",
                            (meeting["transcript_version_id"],),
                        ).fetchall()
                        evidence_ids.update(str(item["evidence_id"]) for item in rows)
                    if meeting["transcript_source_id"]:
                        rows = con.execute(
                            """
                            SELECT e.evidence_id
                            FROM evidence_record e
                            JOIN source_version v ON v.source_version_id=e.source_version_id
                            WHERE v.source_id=?
                            """,
                            (meeting["transcript_source_id"],),
                        ).fetchall()
                        evidence_ids.update(str(item["evidence_id"]) for item in rows)

    # Direct relationship-bearing records are useful even when there is no
    # canonical entity row (for example an imported task title).
    like = f"%{question.casefold()}%"
    for row in con.execute(
        "SELECT evidence_id FROM document WHERE lower(title) LIKE ? ORDER BY document_id",
        (like,),
    ):
        evidence_ids.add(str(row["evidence_id"]))
    for row in con.execute(
        "SELECT source_evidence_id FROM task WHERE lower(action) LIKE ? ORDER BY task_id",
        (like,),
    ):
        if row["source_evidence_id"]:
            evidence_ids.add(str(row["source_evidence_id"]))

    meeting_rows = con.execute(
        """
        SELECT transcript_version_id, transcript_source_id
        FROM meeting_group
        WHERE lower(folder_relative_path) LIKE ?
           OR lower(COALESCE(transcript_path, '')) LIKE ?
        ORDER BY group_id
        """,
        (like, like),
    ).fetchall()
    for meeting in meeting_rows:
        if meeting["transcript_version_id"]:
            rows = con.execute(
                "SELECT evidence_id FROM evidence_record WHERE source_version_id=?",
                (meeting["transcript_version_id"],),
            ).fetchall()
            evidence_ids.update(str(item["evidence_id"]) for item in rows)

    return sorted(evidence_ids)


def _relationship_evidence_labels(
    con: sqlite3.Connection,
    question: str,
    evidence_ids: Sequence[str],
) -> Dict[str, str]:
    """Return the least-trusted review label for relationship-backed evidence."""
    if not evidence_ids:
        return {}
    entity_ids = _matching_entity_ids(con, question)
    placeholders = ", ".join("?" for _value in evidence_ids)
    labels: Dict[str, str] = {str(value): "canonical" for value in evidence_ids}
    ranks = {"canonical": 0, "derived_unreviewed": 1, "conflict": 2}

    def apply(evidence_id: str, status: Any) -> None:
        normalized = str(status or "").casefold().strip()
        if normalized in {"conflict", "conflicted", "disputed"}:
            label = "conflict"
        elif normalized in {"confirmed", "accepted", "resolved", "canonical"}:
            label = "canonical"
        else:
            label = "derived_unreviewed"
        if ranks[label] >= ranks[labels.get(evidence_id, "canonical")]:
            labels[evidence_id] = label

    for row in con.execute(
        f"SELECT evidence_id, status FROM relationship WHERE evidence_id IN ({placeholders})",
        list(evidence_ids),
    ):
        apply(str(row["evidence_id"]), row["status"])

    if entity_ids:
        entity_placeholders = ", ".join("?" for _value in entity_ids)
        for row in con.execute(
            f"""
            SELECT evidence_id, resolution_status
            FROM entity_mention
            WHERE entity_id IN ({entity_placeholders})
              AND evidence_id IN ({placeholders})
            """,
            [*entity_ids, *evidence_ids],
        ):
            apply(str(row["evidence_id"]), row["resolution_status"])
    return labels


def relationship_search(
    con: sqlite3.Connection,
    question: str,
    *,
    scope: str = DEFAULT_SCOPE,
    diagnostic: bool = False,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    value = validate_question(question)
    normalized_scope = _validate_scope(scope)
    evidence_ids = _relationship_evidence_ids(con, value)
    labels = _relationship_evidence_labels(con, value, evidence_ids)
    rows = _fetch_evidence_by_ids(
        con,
        evidence_ids,
        scope=normalized_scope,
        diagnostic=diagnostic,
        limit=limit,
    )
    return [
        _hit_from_row(
            dict(row),
            match_type="relationship",
            label_override=(
                "excluded_scope"
                if diagnostic and _scope_for_row(row) != WORK_SCOPE
                else labels.get(str(row["evidence_id"]))
            ),
        )
        for row in rows
    ]


def _raw_snippet(text: str, question: str) -> Optional[Tuple[str, str]]:
    lowered = text.casefold()
    needle = question.casefold()
    offset = lowered.find(needle)
    if offset < 0:
        return None
    line_number = text.count("\n", 0, offset) + 1
    start = max(0, offset - 180)
    end = min(len(text), offset + len(question) + 220)
    return f"line:{line_number}", text[start:end].strip()


def _raw_work_fallback(
    con: sqlite3.Connection,
    question: str,
    *,
    scope: str = DEFAULT_SCOPE,
    limit: int,
    diagnostic: bool = False,
) -> List[Dict[str, Any]]:
    predicates = [
        "s.status='present'",
        "s.absolute_path IS NOT NULL",
        "s.absolute_path <> ''",
        "s.source_version_id IS NOT NULL",
        "s.content_sha256 IS NOT NULL",
    ]
    if not diagnostic and scope.casefold() != ALL_SCOPE.casefold():
        predicates.append(_scope_sql(scope=scope))
    rows = con.execute(
        f"""
        SELECT s.*, v.source_version_id AS current_version_id,
               v.content_sha256 AS current_content_sha256,
               (SELECT date_value FROM date_observation
                WHERE source_version_id=v.source_version_id
                ORDER BY observation_id LIMIT 1) AS observed_date,
               (SELECT basis FROM date_observation
                WHERE source_version_id=v.source_version_id
                ORDER BY observation_id LIMIT 1) AS observed_date_basis
        FROM source_record s
        JOIN source_version v
          ON v.source_version_id=s.source_version_id
         AND v.source_id=s.source_id
         AND v.content_sha256=s.content_sha256
        WHERE {' AND '.join(predicates)}
        ORDER BY s.relative_path
        """
    ).fetchall()
    hits: List[Dict[str, Any]] = []
    excluded = {"media", "archive", "database", "metadata", "discovery", "artifact"}
    for row in rows:
        if row["kind"] in excluded:
            continue
        path = Path(row["absolute_path"])
        try:
            text = read_text_guess(path, max_bytes=MAX_RAW_BYTES)
        except (OSError, UnicodeError, ValueError):
            continue
        found = _raw_snippet(text, question)
        if found is None:
            continue
        locator, snippet = found
        date_value, date_basis = _date_fields(dict(row))
        row_scope = _scope_for_row(dict(row))
        if diagnostic:
            label = "excluded_scope" if row_scope.casefold() != WORK_SCOPE.casefold() else "raw_work"
        elif row_scope.casefold() == WORK_SCOPE.casefold():
            label = "raw_work"
        else:
            label = "raw_source"
        hits.append(
            {
                "label": label,
                "evidence_status": label if label != "excluded_scope" else "raw_source",
                "evidence_id": None,
                "source_path": row["relative_path"],
                "relative_path": row["relative_path"],
                "source_id": row["source_id"],
                "source_version_id": row["source_version_id"] or row["current_version_id"],
                "locator": locator,
                "date_basis": date_basis,
                "source_date_basis": date_basis,
                "date_value": date_value,
                "scope": row_scope,
                "source_system": row["source_system"],
                "sensitivity": row["sensitivity"],
                "snippet": redact_snippet(snippet),
                "match_type": "raw",
            }
        )
        if len(hits) >= limit:
            break
    return hits


def _deduplicate_hits(hits: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    priority = {"exact": 0, "relationship": 1, "fts": 2, "raw": 3}
    selected: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for hit in hits:
        key = (
            str(hit.get("evidence_id") or hit.get("source_id") or ""),
            str(hit.get("locator") or ""),
            str(hit.get("label") or ""),
        )
        current = selected.get(key)
        if current is None or priority.get(hit.get("match_type", ""), 9) < priority.get(
            current.get("match_type", ""), 9
        ):
            selected[key] = hit
    return sorted(
        selected.values(),
        key=lambda hit: (
            priority.get(hit.get("match_type", ""), 9),
            str(hit.get("source_path") or ""),
            str(hit.get("locator") or ""),
            str(hit.get("evidence_id") or ""),
        ),
    )


def _missing_hit(question: str, *, scope: str = DEFAULT_SCOPE) -> Dict[str, Any]:
    scope_description = "Work-scoped" if scope == WORK_SCOPE else "source-backed"
    reason_scope = "Work raw source" if scope == WORK_SCOPE else "raw source"
    return {
        "label": "missing",
        "evidence_status": "missing",
        "evidence_id": None,
        "source_path": None,
        "relative_path": None,
        "source_id": None,
        "source_version_id": None,
        "locator": None,
        "date_basis": "not_observed",
        "source_date_basis": "not_observed",
        "date_value": None,
        "scope": scope,
        "source_system": None,
        "sensitivity": None,
        "snippet": f"No {scope_description} evidence matched the question.",
        "match_type": "missing",
        "question": question,
        "reason": f"No canonical, derived, or {reason_scope} answer was found.",
    }


def _partition(hits: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        "source_facts": [hit for hit in hits if hit["label"] in _SOURCE_FACT_LABELS],
        "inferences": [hit for hit in hits if hit["label"] == "inference"],
        "conflicts": [hit for hit in hits if hit["label"] == "conflict"],
        "missing": [hit for hit in hits if hit["label"] == "missing"],
        "excluded_scope": [hit for hit in hits if hit["label"] == "excluded_scope"],
    }


def search(
    con: sqlite3.Connection,
    question: str,
    *,
    scope: str = DEFAULT_SCOPE,
    limit: int = DEFAULT_LIMIT,
    raw_fallback: bool = True,
    diagnostic: bool = False,
) -> Dict[str, Any]:
    """Search local evidence in exact, FTS, relationship, then raw order.

    The default response searches all source scopes and preserves each row's
    original scope label.  ``scope="Work"`` narrows the response.
    ``diagnostic=True`` is an explicitly separate local inspection mode that
    labels non-Work rows ``excluded_scope``; it is never enabled by the CLI
    default.
    """
    value = validate_question(question)
    normalized_scope = _validate_scope(scope)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise QueryValidationError("limit must be a positive integer")

    # Keep existing derived FTS rows safe before either MATCH or display.
    rebuild_search_index(con)

    hits: List[Dict[str, Any]] = []
    hits.extend(
        exact_search(
            con,
            value,
            scope=normalized_scope,
            diagnostic=diagnostic,
            limit=limit,
        )
    )
    hits.extend(
        fts_search(
            con,
            value,
            scope=normalized_scope,
            diagnostic=diagnostic,
            limit=limit,
        )
    )
    hits.extend(
        relationship_search(
            con,
            value,
            scope=normalized_scope,
            diagnostic=diagnostic,
            limit=limit,
        )
    )
    hits = _deduplicate_hits(hits)

    source_answer = any(hit["label"] in _SOURCE_FACT_LABELS for hit in hits)
    used_raw_fallback = False
    if raw_fallback and not diagnostic and not source_answer:
        fallback_hits = _raw_work_fallback(
            con,
            value,
            scope=normalized_scope,
            limit=limit,
            diagnostic=False,
        )
        if fallback_hits:
            used_raw_fallback = True
            hits = _deduplicate_hits([*hits, *fallback_hits])

    if diagnostic and not source_answer:
        diagnostic_raw = _raw_work_fallback(
            con,
            value,
            scope=normalized_scope,
            limit=limit,
            diagnostic=True,
        )
        hits = _deduplicate_hits([*hits, *diagnostic_raw])

    hits = hits[:limit]
    if not hits:
        hits = [_missing_hit(value, scope=normalized_scope)]

    partitions = _partition(hits)
    return {
        "question": value,
        "scope": normalized_scope,
        "diagnostic": diagnostic,
        "results": hits,
        "source_facts": partitions["source_facts"],
        "inferences": partitions["inferences"],
        "conflicts": partitions["conflicts"],
        "missing": partitions["missing"],
        "excluded_scope": partitions["excluded_scope"],
        "excluded_scope_count": len(partitions["excluded_scope"]),
        "used_raw_fallback": used_raw_fallback,
        "result_count": len(hits),
    }


def diagnostic_search(
    con: sqlite3.Connection,
    question: str,
    *,
    limit: int = DEFAULT_LIMIT,
) -> Dict[str, Any]:
    """Inspect excluded local records with an explicit excluded-scope label."""
    return search(
        con,
        question,
        scope=ALL_SCOPE,
        limit=limit,
        raw_fallback=False,
        diagnostic=True,
    )


# Descriptive aliases make the small public surface easy to discover without
# introducing a second implementation.
query = search
run_query = search


def query_work(
    con: sqlite3.Connection,
    question: str,
    *,
    limit: int = DEFAULT_LIMIT,
    raw_fallback: bool = True,
    diagnostic: bool = False,
) -> Dict[str, Any]:
    """Preserve the explicit Work-only convenience entry point."""
    return search(
        con,
        question,
        scope=WORK_SCOPE,
        limit=limit,
        raw_fallback=raw_fallback,
        diagnostic=diagnostic,
    )


search_exact = exact_search
search_fts = fts_search
traverse_relationships = relationship_search
redact_output = redact_snippet
rebuild_fts = rebuild_search_index
