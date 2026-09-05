from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

import pytest

from work_corpus import db
from work_corpus.db import connect
from work_corpus.entities import create_entity
from work_corpus.query import diagnostic_search, search


def _add_root(con, root_key: str, source_system: str = "synthetic") -> None:
    con.execute(
        """
        INSERT INTO source_root (
            root_key, relative_path, source_system, precedence, enabled
        ) VALUES (?, ?, ?, ?, 1)
        """,
        (root_key, f"data/{root_key}", source_system, 10),
    )


def _add_source(
    con,
    tmp_path: Path,
    *,
    name: str,
    scope: str,
    text: Optional[str] = None,
    evidence_status: Optional[str] = "canonical",
    root_key: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    root_key = root_key or f"root_{name.replace('-', '_')}"
    _add_root(con, root_key)
    relative_path = f"data/{scope.casefold()}/{name}"
    source_id = db.upsert_source_record(
        con,
        root_key=root_key,
        relative_path=relative_path,
        source_system="synthetic",
        kind="document",
        scope=scope,
        sensitivity="internal",
    )
    raw_path = tmp_path / relative_path
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_text = text or ""
    raw_path.write_text(raw_text, encoding="utf-8")
    content = raw_text.encode("utf-8")
    version_id = db.record_source_version(
        con,
        source_id=source_id,
        size_bytes=len(content),
        mtime_ns=1,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, classification=?, scope=?, extraction_status='ready'
        WHERE source_id=?
        """,
        (str(raw_path), scope, scope, source_id),
    )
    evidence_id = None
    if evidence_status is not None:
        evidence_id = db.record_evidence(
            con,
            source_version_id=version_id,
            locator="document",
            derived_text_path=str(raw_path),
            text_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            evidence_status=evidence_status,
            derived_text=raw_text,
        )
    con.commit()
    return source_id, version_id, evidence_id


def test_default_query_scope_cannot_join_non_work_evidence(tmp_path: Path):
    con = connect(tmp_path / "state.sqlite")
    try:
        work_id, _, work_evidence_id = _add_source(
            con,
            tmp_path,
            name="work.md",
            scope="Work",
            text="shared-marker work evidence",
        )
        personal_id, _, _ = _add_source(
            con,
            tmp_path,
            name="personal.md",
            scope="Personal",
            text="shared-marker personal evidence",
        )
        mixed_id, _, _ = _add_source(
            con,
            tmp_path,
            name="mixed.md",
            scope="Mixed",
            text="shared-marker mixed evidence",
        )
        unknown_id, _, _ = _add_source(
            con,
            tmp_path,
            name="unknown.md",
            scope="Unknown",
            text="shared-marker unknown evidence",
        )

        result = search(con, "shared-marker")
    finally:
        con.close()

    hits = result["results"]
    assert {hit["source_id"] for hit in hits} == {work_id}
    assert {hit["evidence_id"] for hit in hits} == {work_evidence_id}
    assert not {personal_id, mixed_id, unknown_id} & {
        hit["source_id"] for hit in hits
    }
    assert all(hit["scope"] == "Work" for hit in hits)
    assert "personal.md" not in json.dumps(result)
    assert "mixed.md" not in json.dumps(result)
    assert "unknown.md" not in json.dumps(result)


def test_raw_fallback_requires_work_scope(tmp_path: Path):
    con = connect(tmp_path / "raw-fallback.sqlite")
    try:
        work_id, work_version_id, _ = _add_source(
            con,
            tmp_path,
            name="work-raw.txt",
            scope="Work",
            text="exact-raw-marker https://example.test/private?token=secret",
            evidence_status=None,
        )
        personal_id, _, _ = _add_source(
            con,
            tmp_path,
            name="personal-raw.txt",
            scope="Personal",
            text="exact-raw-marker personal-only",
            evidence_status=None,
        )
        mixed_id, _, _ = _add_source(
            con,
            tmp_path,
            name="mixed-raw.txt",
            scope="Mixed",
            text="exact-raw-marker mixed-only",
            evidence_status=None,
        )
        unknown_id, _, _ = _add_source(
            con,
            tmp_path,
            name="unknown-raw.txt",
            scope="Unknown",
            text="exact-raw-marker unknown-only",
            evidence_status=None,
        )

        result = search(con, "exact-raw-marker")
        raw_bytes_after_query = (
            tmp_path / "data" / "work" / "work-raw.txt"
        ).read_bytes()
    finally:
        con.close()

    hits = result["results"]
    assert len(hits) == 1
    assert hits[0]["label"] == "raw_work"
    assert hits[0]["source_id"] == work_id
    assert hits[0]["source_version_id"] == work_version_id
    assert not {personal_id, mixed_id, unknown_id} & {
        hit["source_id"] for hit in hits
    }
    assert "https://" not in hits[0]["snippet"]
    assert "secret" not in hits[0]["snippet"]
    assert raw_bytes_after_query == (
        b"exact-raw-marker https://example.test/private?token=secret"
    )


def test_diagnostic_search_labels_excluded_scope(tmp_path: Path):
    con = connect(tmp_path / "diagnostic.sqlite")
    try:
        _add_source(
            con,
            tmp_path,
            name="work.md",
            scope="Work",
            text="diagnostic-marker work",
        )
        _add_source(
            con,
            tmp_path,
            name="personal.md",
            scope="Personal",
            text="diagnostic-marker personal",
        )
        result = diagnostic_search(con, "diagnostic-marker")
    finally:
        con.close()

    assert {hit["label"] for hit in result["results"]} == {
        "canonical",
        "excluded_scope",
    }
    excluded = [
        hit for hit in result["results"] if hit["label"] == "excluded_scope"
    ]
    assert excluded[0]["scope"] == "Personal"
    assert result["excluded_scope_count"] == 1


def test_fts_redaction_changes_derived_index_only(tmp_path: Path):
    con = connect(tmp_path / "fts-redaction.sqlite")
    try:
        source_id, _, _ = _add_source(
            con,
            tmp_path,
            name="secure.md",
            scope="Work",
            text=(
                "fts-marker https://example.test/plain "
                'api_key="plain-secret"'
            ),
        )
        raw_path = tmp_path / "data" / "work" / "secure.md"
        raw_before = raw_path.read_bytes()
        result = search(con, "fts-marker")
        indexed = con.execute(
            """
            SELECT derived_text
            FROM derived_text_fts
            WHERE evidence_id=?
            """,
            (result["results"][0]["evidence_id"],),
        ).fetchone()[0]
    finally:
        con.close()

    assert result["results"][0]["source_id"] == source_id
    assert "https://" not in indexed
    assert "plain-secret" not in indexed
    assert raw_path.read_bytes() == raw_before


def test_exact_fts_relationship_and_provenance_fields(tmp_path: Path):
    con = connect(tmp_path / "search-paths.sqlite")
    try:
        source_id, version_id, evidence_id = _add_source(
            con,
            tmp_path,
            name="decision.md",
            scope="Work",
            text="canonical decision evidence",
        )
        con.execute(
            """
            INSERT INTO date_observation (
                observation_id, evidence_id, date_value, basis, precision,
                confidence, created_at
            ) VALUES ('observation-1', ?, '2026-09-04', 'meeting_date', 'day', 1.0,
                      '2026-09-04T00:00:00Z')
            """,
            (evidence_id,),
        )
        project_id = create_entity(con, "project", "alpha", "Project Alpha")
        con.execute(
            """
            INSERT INTO relationship (
                relationship_id, relationship_type, from_record_type,
                from_record_id, to_record_type, to_record_id, evidence_id,
                status, confidence
            ) VALUES ('relationship-1', 'project_evidence', 'entity', ?,
                      'evidence', ?, ?, 'confirmed', 1.0)
            """,
            (project_id, evidence_id, evidence_id),
        )
        con.commit()

        exact = search(con, "canonical decision")
        relationship = search(con, "Project Alpha")
    finally:
        con.close()

    assert exact["results"][0]["evidence_id"] == evidence_id
    assert exact["results"][0]["match_type"] in {"exact", "fts"}
    assert relationship["results"][0]["evidence_id"] == evidence_id
    hit = relationship["results"][0]
    assert hit["source_path"] == "data/work/decision.md"
    assert hit["source_id"] == source_id
    assert hit["source_version_id"] == version_id
    assert hit["locator"] == "document"
    assert hit["evidence_status"] == "canonical"
    assert hit["date_basis"] == "meeting_date"


def test_evidence_labels_are_separated(tmp_path: Path):
    con = connect(tmp_path / "labels.sqlite")
    try:
        statuses = (
            "canonical",
            "derived_unreviewed",
            "inference",
            "conflict",
            "missing",
        )
        for index, status in enumerate(statuses):
            _add_source(
                con,
                tmp_path,
                name=f"{status}-{index}.md",
                scope="Work",
                text=f"label-marker {status}",
                evidence_status=status,
                root_key=f"labels-{index}",
            )

        result = search(con, "label-marker")
    finally:
        con.close()

    labels = {hit["label"] for hit in result["results"]}
    assert labels == {
        "canonical",
        "derived_unreviewed",
        "inference",
        "conflict",
        "missing",
    }
    assert result["source_facts"]
    assert result["inferences"]
    assert result["conflicts"]
    assert result["missing"]
    assert result["used_raw_fallback"] is False


def test_no_match_is_an_explicit_missing_result(tmp_path: Path):
    con = connect(tmp_path / "missing.sqlite")
    try:
        result = search(con, "unrecorded question")
    finally:
        con.close()

    assert result["results"]
    assert result["results"][0]["label"] == "missing"
    assert result["missing"][0]["question"] == "unrecorded question"


def test_query_rejects_empty_question_and_non_work_default_scope(tmp_path: Path):
    con = connect(tmp_path / "validation.sqlite")
    try:
        with pytest.raises(ValueError, match="question"):
            search(con, "   ")
        with pytest.raises(ValueError, match="Work"):
            search(con, "anything", scope="Personal")
    finally:
        con.close()
