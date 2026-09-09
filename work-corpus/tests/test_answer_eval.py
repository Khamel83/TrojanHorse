from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from work_corpus import answering, cli, db


def _hit(
    *,
    label: str = "canonical",
    evidence_id: str = "evidence-1",
    source_id: str = "source-1",
    source_version_id: str = "version-1",
    snippet: str = "Project Atlas was approved for launch.",
) -> dict[str, str]:
    return {
        "label": label,
        "evidence_status": label,
        "evidence_id": evidence_id,
        "source_id": source_id,
        "source_version_id": source_version_id,
        "source_path": "/Users/Omar/TrojanHorse/data/work/atlas.md",
        "relative_path": "data/work/atlas.md",
        "absolute_path": "/Users/Omar/TrojanHorse/data/work/atlas.md",
        "locator": "document:1",
        "date_basis": "meeting_date",
        "date_value": "2026-09-08",
        "scope": "Work",
        "source_system": "synthetic",
        "sensitivity": "internal",
        "snippet": snippet,
    }


class _Backend:
    name = "synthetic"

    def __init__(self, text: str) -> None:
        self.text = text
        self.messages: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> answering.Completion:
        self.messages.append(messages)
        return answering.Completion(self.text, metadata={"route": self.name, "model": "synthetic"})


def test_compare_answers_keeps_original_local_and_sends_only_sanitized_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_result = {
        "question": "What happened to Project Atlas?",
        "results": [
            _hit(
                snippet=(
                    "Project Atlas was approved. "
                    "Private file /Users/Omar/TrojanHorse/data/work/atlas.md."
                )
            )
        ],
        "source_facts": [_hit()],
        "inferences": [],
        "conflicts": [],
        "missing": [],
    }
    monkeypatch.setattr(answering, "search", lambda *_args, **_kwargs: search_result)
    local = _Backend('{"answer":"local","citations":["S1"],"stance":"supported"}')
    remote = _Backend('{"answer":"remote","citations":["S1"],"stance":"supported"}')

    result = answering.compare_answers(
        object(),
        "What happened to Project Atlas?",
        local_backend=local,
        remote_backend=remote,
        allow_sensitive_remote=True,
    )

    assert len(local.messages) == 2
    assert len(remote.messages) == 1
    original_prompt = local.messages[0][-1]["content"]
    sanitized_prompt = local.messages[1][-1]["content"]
    remote_prompt = remote.messages[0][-1]["content"]
    assert "/Users/Omar/TrojanHorse/data/work/atlas.md" in original_prompt
    assert "/Users/Omar/TrojanHorse/data/work/atlas.md" not in sanitized_prompt
    assert remote_prompt == sanitized_prompt
    assert "/Users/Omar/TrojanHorse/data/work/atlas.md" not in remote_prompt
    assert result["lanes"]["local_original"]["packet_sha256"] != result["lanes"]["local_sanitized"]["packet_sha256"]
    assert result["packet_sha256_equal"] is True
    assert result["packet_digests"]["local_sanitized"] == result["packet_digests"]["gateway_sensitive"]
    assert result["sanitizer_findings"]
    assert result["source_grounded_comparison"]["local_original"]["source_ids"] == ["source-1"]


def test_evaluate_cases_scores_source_ids_status_abstention_and_terms(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    supported = _hit()
    conflict = _hit(
        label="conflict",
        evidence_id="evidence-2",
        source_id="source-2",
        source_version_id="version-2",
        snippet="Project Atlas has conflicting proposed dates.",
    )
    results = {
        "supported": {
            "question": "supported",
            "results": [supported],
            "source_facts": [supported],
            "inferences": [],
            "conflicts": [],
            "missing": [],
        },
        "none": {
            "question": "none",
            "results": [],
            "source_facts": [],
            "inferences": [],
            "conflicts": [],
            "missing": [],
        },
        "conflict": {
            "question": "conflict",
            "results": [conflict],
            "source_facts": [],
            "inferences": [],
            "conflicts": [conflict],
            "missing": [],
        },
        "missing-citation": {
            "question": "missing-citation",
            "results": [supported],
            "source_facts": [supported],
            "inferences": [],
            "conflicts": [],
            "missing": [],
        },
        "malformed": {
            "question": "malformed",
            "results": [supported],
            "source_facts": [supported],
            "inferences": [],
            "conflicts": [],
            "missing": [],
        },
    }
    monkeypatch.setattr(answering, "search", lambda _con, question, **_kwargs: results[question])
    backend = _Backend('{"answer":"Project Atlas was approved for launch.","citations":["S1"],"stance":"supported"}')
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        "\n".join(
            json.dumps(case)
            for case in (
                {
                    "id": "supported",
                    "question": "supported",
                    "expected_source_ids": ["source-1"],
                    "expected_status": "synthesized",
                    "expected_terms": ["Atlas", "approved"],
                },
                {
                    "id": "none",
                    "question": "none",
                    "expected_source_ids": [],
                    "expected_status": "no_evidence",
                },
                {
                    "id": "conflict",
                    "question": "conflict",
                    "expected_source_ids": ["source-2"],
                    "expected_status": "synthesized",
                },
                {
                    "id": "missing-citation",
                    "question": "missing-citation",
                    "expected_source_ids": ["source-2"],
                    "expected_status": "synthesized",
                },
                {
                    "id": "malformed",
                    "question": "malformed",
                    "expected_source_ids": ["source-1"],
                    "expected_status": "model_error",
                },
            )
        )
        + "\n",
        encoding="utf-8",
    )
    backend.text = '{"answer":"Project Atlas was approved for launch.","citations":["S1"],"stance":"supported"}'

    original_complete = backend.complete

    def by_question(messages: list[dict[str, str]]) -> answering.Completion:
        prompt = messages[-1]["content"]
        if '"question":"malformed"' in prompt:
            return answering.Completion("not-json", metadata={"route": "synthetic"})
        if '"question":"conflict"' in prompt:
            return answering.Completion(
                '{"answer":"The sources disagree.","citations":["S1"],"stance":"mixed"}',
                metadata={"route": "synthetic"},
            )
        if '"question":"missing-citation"' in prompt:
            return answering.Completion(
                '{"answer":"Only source one is cited.","citations":["S1"],"stance":"supported"}',
                metadata={"route": "synthetic"},
            )
        return original_complete(messages)

    backend.complete = by_question  # type: ignore[method-assign]
    report = answering.evaluate_cases(object(), cases_path, backends={"local": backend})

    assert report["review_authority"] == "source_inspection_required"
    by_id = {item["id"]: item for item in report["cases"]}
    assert by_id["supported"]["backends"]["local"]["citation_precision"] == 1.0
    assert by_id["supported"]["backends"]["local"]["citation_recall"] == 1.0
    assert by_id["none"]["backends"]["local"]["correct_abstention"] is True
    assert by_id["conflict"]["backends"]["local"]["conflict_acknowledged"] is True
    assert by_id["missing-citation"]["backends"]["local"]["citation_recall"] == 0.0
    assert by_id["missing-citation"]["backends"]["local"]["expected_status_match"] is True
    assert by_id["malformed"]["backends"]["local"]["expected_status_match"] is True
    assert by_id["supported"]["backends"]["local"]["term_coverage"] == 1.0
    assert "synthetic" in report["backend_metadata"]["local"]["routes"]


def test_cli_answer_eval_is_read_only_and_emits_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    database = tmp_path / "work-corpus" / "state" / "work_corpus.sqlite"
    database.parent.mkdir(parents=True)
    con = db.connect(database)
    con.close()
    cases_path = tmp_path / "cases.jsonl"
    cases_path.write_text(
        json.dumps(
            {
                "id": "case-1",
                "question": "synthetic",
                "expected_source_ids": [],
                "expected_status": "no_evidence",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    seen: dict[str, Any] = {}

    def fake_evaluate(con_arg: Any, path_arg: Path, **kwargs: Any) -> dict[str, Any]:
        seen.update(con=con_arg, path=path_arg, **kwargs)
        return {
            "status": "evaluated",
            "accuracy_claim": None,
            "review_authority": "source_inspection_required",
        }

    monkeypatch.setattr(cli, "bootstrap", lambda *_args: pytest.fail("bootstrap called"))
    monkeypatch.setattr(cli, "_record_start", lambda *_args: pytest.fail("pipeline recorded"))
    monkeypatch.setattr(cli, "evaluate_cases", fake_evaluate)

    assert (
        cli.main(
            [
                "--root",
                str(tmp_path),
                "answer-eval",
                "--cases",
                str(cases_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["review_authority"] == "source_inspection_required"
    assert seen["path"] == cases_path
    assert seen["allow_sensitive_remote"] is False
