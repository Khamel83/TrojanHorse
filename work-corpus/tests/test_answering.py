from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from work_corpus import db, answering
from work_corpus.query import QueryValidationError


def _source(
    con: Any,
    tmp_path: Path,
    *,
    name: str,
    text: str,
    evidence_status: str = "canonical",
) -> tuple[str, str, str]:
    con.execute(
        "INSERT INTO source_root (root_key, relative_path, source_system, precedence, enabled) "
        "VALUES (?, ?, 'synthetic', 10, 1)",
        (f"root-{name}", f"data/{name}"),
    )
    source_id = db.upsert_source_record(
        con,
        root_key=f"root-{name}",
        relative_path=f"data/{name}.md",
        source_system="synthetic",
        kind="document",
        scope="Work",
        sensitivity="internal",
    )
    path = tmp_path / "data" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    content = text.encode("utf-8")
    version_id = db.record_source_version(
        con,
        source_id=source_id,
        size_bytes=len(content),
        mtime_ns=1,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )
    con.execute(
        "UPDATE source_record SET absolute_path=?, classification='Work', extraction_status='ready' "
        "WHERE source_id=?",
        (str(path), source_id),
    )
    evidence_id = db.record_evidence(
        con,
        source_version_id=version_id,
        locator="document:1",
        derived_text_path=str(path),
        text_sha256=hashlib.sha256(content).hexdigest(),
        evidence_status=evidence_status,
        derived_text=text,
    )
    con.commit()
    return source_id, version_id, evidence_id


class _SpyBackend:
    name = "synthetic"

    def __init__(self, text: str = "") -> None:
        self.text = text
        self.calls = 0
        self.messages: list[dict[str, str]] = []

    def complete(self, messages: list[dict[str, str]]) -> answering.Completion:
        self.calls += 1
        self.messages = messages
        return answering.Completion(self.text)


def test_answer_evidence_only_returns_citable_local_provenance(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    try:
        source_id, version_id, _evidence_id = _source(
            con,
            tmp_path,
            name="atlas",
            text="Project Atlas was approved for launch.",
        )
        result = answering.answer(con, "Project Atlas")
    finally:
        con.close()

    assert result["status"] == "evidence_only"
    assert result["answer_kind"] == "evidence"
    assert result["citations"]
    citation = result["citations"][0]
    assert citation["source_id"] == source_id
    assert citation["source_version_id"] == version_id
    assert citation["locator"] == "document:1"
    assert result["citation_map"][citation["citation_id"]]["source_id"] == source_id
    assert result["source_facts"]
    assert result["packet_sha256"]
    json.dumps(result)


def test_answer_evidence_backend_never_uses_injected_completion(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"untrusted","citations":["S1"],"stance":"supported"}'
    )
    try:
        _source(con, tmp_path, name="atlas", text="Project Atlas was approved.")
        result = answering.answer(
            con,
            "Project Atlas",
            backend="evidence",
            completion_backend=backend,
        )
    finally:
        con.close()

    assert backend.calls == 0
    assert "untrusted" not in result["answer"]


def test_answer_no_result_does_not_call_completion_backend(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"untrusted","citations":[],"stance":"insufficient"}'
    )
    try:
        result = answering.answer(
            con,
            "question with no matching evidence",
            backend="ollama",
            completion_backend=backend,
        )
    finally:
        con.close()

    assert result["status"] == "no_evidence"
    assert result["answer_kind"] == "abstention"
    assert result["citations"] == []
    assert backend.calls == 0


def test_answer_conflict_can_be_synthesized_when_completion_acknowledges_it(
    tmp_path: Path,
):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"The sources disagree.","citations":["S1"],"stance":"mixed"}'
    )
    try:
        _source(
            con,
            tmp_path,
            name="conflict",
            text="Project Atlas has two proposed dates.",
            evidence_status="conflict",
        )
        result = answering.answer(
            con,
            "Project Atlas",
            backend="ollama",
            completion_backend=backend,
        )
    finally:
        con.close()

    assert result["status"] == "synthesized"
    assert result["answer_kind"] == "model"
    assert result["conflicts"]
    assert backend.calls == 1


def test_answer_parses_completion_and_keeps_model_text_separate(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}'
    )
    try:
        _source(
            con,
            tmp_path,
            name="atlas",
            text="Project Atlas was approved for launch.",
        )
        result = answering.answer(
            con,
            "Project Atlas",
            backend="ollama",
            completion_backend=backend,
        )
    finally:
        con.close()

    assert result["status"] == "synthesized"
    assert result["answer_kind"] == "model"
    assert result["answer"] == "Project Atlas was approved."
    assert result["citations"][0]["citation_id"] == "S1"
    assert "evidence" in backend.messages[-1]["content"]


def test_answer_backend_failure_returns_evidence_fallback_without_model_text(
    tmp_path: Path,
):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"DO NOT RETURN THIS MODEL TEXT","citations":["S1"],"stance":"supported"}'
    )

    def fail(_messages: list[dict[str, str]]) -> answering.Completion:
        backend.calls += 1
        raise answering.CompletionTransportError("provider failed")

    backend.complete = fail  # type: ignore[method-assign]
    try:
        _source(
            con,
            tmp_path,
            name="atlas",
            text="Project Atlas was approved for launch.",
        )
        result = answering.answer(
            con,
            "Project Atlas",
            backend="ollama",
            completion_backend=backend,
        )
    finally:
        con.close()

    assert result["status"] == "model_error"
    assert result["answer_kind"] == "evidence_fallback"
    assert "DO NOT RETURN THIS MODEL TEXT" not in result["answer"]
    assert result["warnings"]
    assert backend.calls == 1


def test_answer_rejects_sensitive_route_without_explicit_opt_in(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend()
    try:
        _source(con, tmp_path, name="atlas", text="Project Atlas was approved.")
        with pytest.raises(ValueError, match="sensitive"):
            answering.answer(
                con,
                "Project Atlas",
                backend="g2k-sensitive",
                completion_backend=backend,
            )
    finally:
        con.close()
    assert backend.calls == 0


def test_answer_sensitive_route_sends_only_remote_safe_packet(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    backend = _SpyBackend(
        '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}'
    )
    try:
        _source(
            con,
            tmp_path,
            name="atlas",
            text=(
                "Project Atlas was approved. Contact maya@example.test at "
                "+1 (415) 555-2671."
            ),
        )
        result = answering.answer(
            con,
            "Project Atlas",
            backend="g2k-sensitive",
            completion_backend=backend,
            allow_sensitive_remote=True,
        )
    finally:
        con.close()

    prompt = json.dumps(backend.messages)
    assert "maya@example.test" not in prompt
    assert "+1 (415) 555-2671" not in prompt
    assert "/data/atlas.md" not in prompt
    assert result["status"] == "synthesized"
    assert result["warnings"]


def test_answer_invalid_question_fails_before_search(tmp_path: Path):
    con = db.connect(tmp_path / "state.sqlite")
    try:
        with pytest.raises(QueryValidationError):
            answering.answer(con, "\x00")
    finally:
        con.close()


def test_answer_does_not_change_database_bytes_or_rows(tmp_path: Path):
    database = tmp_path / "state.sqlite"
    con = db.connect(database)
    _source(con, tmp_path, name="atlas", text="Project Atlas was approved.")
    con.close()
    before_bytes = database.read_bytes()
    before_con = db.connect(database, read_only=True)
    try:
        before_rows = before_con.execute(
            "SELECT COUNT(*) FROM evidence_record"
        ).fetchone()[0]
    finally:
        before_con.close()
    read_only = db.connect(database, read_only=True)
    try:
        answering.answer(read_only, "What happened to Project Atlas?")
    finally:
        read_only.close()
    after_con = db.connect(database, read_only=True)
    try:
        after_rows = after_con.execute(
            "SELECT COUNT(*) FROM evidence_record"
        ).fetchone()[0]
    finally:
        after_con.close()
    assert database.read_bytes() == before_bytes
    assert after_rows == before_rows
