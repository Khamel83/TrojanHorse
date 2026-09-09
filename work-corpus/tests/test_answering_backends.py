from __future__ import annotations

import json
import subprocess
from typing import Any

import pytest

from work_corpus.answering import (
    CompletionModelError,
    CompletionParseError,
    CompletionResponseError,
    CompletionTimeoutError,
    CompletionTransportError,
    EvidenceOnlyBackend,
    GatewaySensitiveBackend,
    MAX_COMPLETION_PROMPT_CHARS,
    OllamaBackend,
    parse_completion,
    prepare_evidence,
)


def _prepared() -> Any:
    return prepare_evidence(
        {
            "question": "What did Maya decide for Project Atlas?",
            "results": [
                {
                    "label": "Source fact",
                    "snippet": "Maya approved Project Atlas for launch.",
                    "evidence_status": "canonical",
                    "evidence_id": "evidence-1",
                    "source_id": "source-1",
                    "source_version_id": "version-1",
                    "source_path": "data/work/atlas.md",
                    "relative_path": "data/work/atlas.md",
                    "absolute_path": "/private/corpus/data/work/atlas.md",
                    "locator": "line:11",
                    "scope": "Work",
                    "source_system": "synthetic",
                    "sensitivity": "internal",
                    "match_type": "exact",
                }
            ],
        },
        remote_safe=True,
    )


def _messages(prompt: str = "Use only the supplied evidence.") -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "Return strict JSON."},
        {"role": "user", "content": prompt},
    ]


def test_parse_completion_accepts_a_cited_json_object():
    parsed = parse_completion(
        '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}',
        {"S1"},
        has_source_facts=True,
        has_conflict=False,
    )

    assert parsed == {
        "answer": "Project Atlas was approved.",
        "citations": ["S1"],
        "stance": "supported",
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            '{"answer":"fact","citations":["S9"],"stance":"supported"}',
            "unknown citation",
        ),
        (
            '{"answer":"fact","citations":["S1","S1"],"stance":"supported"}',
            "duplicate citation",
        ),
    ],
)
def test_parse_completion_rejects_unknown_and_duplicate_citations(
    text: str, message: str
):
    with pytest.raises(CompletionParseError, match=message):
        parse_completion(text, {"S1"}, has_source_facts=True, has_conflict=False)


def test_parse_completion_requires_citations_for_source_facts():
    with pytest.raises(CompletionParseError, match="citation"):
        parse_completion(
            '{"answer":"fact","citations":[],"stance":"supported"}',
            {"S1"},
            has_source_facts=True,
            has_conflict=False,
        )


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        '{"answer":"first","answer":"second","citations":[],"stance":"insufficient"}',
        '{"answer":"fact","citations":[],"stance":"supported","extra":true}',
        '{"answer":"  ","citations":[],"stance":"insufficient"}',
    ],
)
def test_parse_completion_rejects_malformed_unknown_and_empty_output(text: str):
    with pytest.raises(CompletionParseError):
        parse_completion(text, set(), has_source_facts=False, has_conflict=False)


def test_parse_completion_requires_conflict_acknowledgment():
    parsed = parse_completion(
        '{"answer":"The sources disagree.","citations":["S1"],"stance":"mixed"}',
        {"S1"},
        has_source_facts=True,
        has_conflict=True,
    )
    assert parsed["stance"] == "mixed"

    with pytest.raises(CompletionParseError, match="conflict"):
        parse_completion(
            '{"answer":"One source is correct.","citations":["S1"],"stance":"supported"}',
            {"S1"},
            has_source_facts=True,
            has_conflict=True,
        )


def test_evidence_only_backend_formats_source_facts_without_a_model():
    completion = EvidenceOnlyBackend(_prepared()).complete(_messages())
    parsed = parse_completion(
        completion.text,
        {"S1"},
        has_source_facts=True,
        has_conflict=False,
    )

    assert parsed["citations"] == ["S1"]
    assert "Maya approved Project Atlas" in parsed["answer"]
    assert completion.metadata["backend"] == "evidence"


def test_evidence_only_backend_requires_trusted_prepared_evidence():
    with pytest.raises(TypeError, match="prepared evidence"):
        EvidenceOnlyBackend()


def test_evidence_only_backend_ignores_untrusted_message_evidence():
    completion = EvidenceOnlyBackend(_prepared()).complete(
        [
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "evidence": [
                            {"citation_id": "S1", "snippet": "hallucinated"}
                        ]
                    }
                ),
            }
        ]
    )

    assert "hallucinated" not in completion.text
    assert "Maya approved Project Atlas" in completion.text


def test_ollama_backend_posts_bounded_json_request_and_returns_completion():
    seen: dict[str, Any] = {}

    def request(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        seen.update(url=url, payload=payload, timeout=timeout)
        return {
            "model": "tiny-local",
            "message": {
                "role": "assistant",
                "content": '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}',
            },
            "done": True,
            "eval_count": 7,
        }

    backend = OllamaBackend(
        "tiny-local",
        "http://127.0.0.1:11434",
        4,
        request_fn=request,
    )
    completion = backend.complete(_messages("PRIVATE PROMPT"))

    assert seen["url"] == "http://127.0.0.1:11434/api/chat"
    assert seen["timeout"] == 4
    assert seen["payload"]["model"] == "tiny-local"
    assert seen["payload"]["stream"] is False
    assert seen["payload"]["format"] == "json"
    assert seen["payload"]["options"]["temperature"] == 0
    assert completion.metadata["model"] == "tiny-local"
    assert parse_completion(
        completion.text,
        {"S1"},
        has_source_facts=True,
        has_conflict=False,
    )["stance"] == "supported"


def test_ollama_backend_truncates_oversized_prompt_before_transport():
    seen: dict[str, Any] = {}

    def request(_url: str, payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
        seen["payload"] = payload
        return {
            "message": {
                "role": "assistant",
                "content": '{"answer":"fact","citations":[],"stance":"insufficient"}',
            }
        }

    OllamaBackend(
        "tiny-local",
        "http://127.0.0.1:11434",
        4,
        request_fn=request,
    ).complete(_messages("PRIVATE PROMPT " + "x" * (MAX_COMPLETION_PROMPT_CHARS * 2)))

    assert len(json.dumps(seen["payload"]["messages"], ensure_ascii=False)) <= (
        MAX_COMPLETION_PROMPT_CHARS
    )


@pytest.mark.parametrize(
    ("request_error", "error_type", "error_message"),
    [
        (TimeoutError("PRIVATE PROMPT"), CompletionTimeoutError, "timeout"),
        (OSError("PRIVATE PROMPT"), CompletionTransportError, "transport"),
    ],
)
def test_ollama_backend_reports_request_failures_without_prompt_text(
    request_error: Exception, error_type: type[Exception], error_message: str
):
    def request(*_args: Any, **_kwargs: Any) -> Any:
        raise request_error

    with pytest.raises(error_type, match=error_message) as caught:
        OllamaBackend(
            "tiny-local",
            "http://localhost:11434",
            4,
            request_fn=request,
        ).complete(_messages("PRIVATE PROMPT"))

    assert "PRIVATE PROMPT" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert not hasattr(caught.value, "output")
    assert not hasattr(caught.value, "stderr")


def test_ollama_backend_reports_malformed_and_model_errors_without_prompt_text():
    for response, expected in (
        ({"message": {"role": "assistant"}}, CompletionTransportError),
        ({"error": "model saw PRIVATE PROMPT"}, CompletionModelError),
    ):
        with pytest.raises(expected) as caught:
            OllamaBackend(
                "tiny-local",
                "http://127.0.0.1:11434",
                4,
                request_fn=lambda *_args, response=response: response,
            ).complete(_messages("PRIVATE PROMPT"))
        assert "PRIVATE PROMPT" not in str(caught.value)
        assert caught.value.__cause__ is None
        assert caught.value.__context__ is None
        assert not hasattr(caught.value, "output")
        assert not hasattr(caught.value, "stderr")


def test_ollama_backend_drops_malformed_response_excerpt_from_exception_links():
    with pytest.raises(CompletionResponseError) as caught:
        OllamaBackend(
            "tiny-local",
            "http://127.0.0.1:11434",
            4,
            request_fn=lambda *_args: "PRIVATE RESPONSE EXCERPT is not JSON",
        ).complete(_messages("PRIVATE PROMPT"))

    assert "PRIVATE RESPONSE EXCERPT" not in repr(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


@pytest.mark.parametrize(
    "base_url",
    ["https://example.test", "http://8.8.8.8:11434", "http://127.0.0.1.evil"],
)
def test_ollama_backend_rejects_non_loopback_urls(base_url: str):
    with pytest.raises(ValueError, match="loopback"):
        OllamaBackend("tiny-local", base_url, 4)


def _gateway_receipt(text: str) -> str:
    return json.dumps(
        {
            "type": "message_end",
            "message": {
                "id": "message-1",
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
                "provider": "secret-provider",
                "model": "secret-model",
                "usage": {"input": 12, "output": 7},
            },
        }
    ) + "\n"


def test_gateway_backend_sources_helper_parses_assistant_receipt_and_hides_provider():
    seen: dict[str, Any] = {}

    def runner(command: list[str], prompt: str, timeout: float) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, prompt=prompt, timeout=timeout)
        return subprocess.CompletedProcess(command, 0, _gateway_receipt(
            '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}'
        ), "")

    completion = GatewaySensitiveBackend(
        "/tmp/gateway2000.zsh",
        8,
        runner=runner,
    ).complete(_messages("PRIVATE PROMPT"))

    command_text = " ".join(seen["command"])
    assert "source" in command_text
    assert "/tmp/gateway2000.zsh" in command_text or "/tmp/gateway2000.zsh" in seen["command"]
    assert "--no-session" in command_text
    assert "--no-tools" in command_text
    assert "--no-extensions" in command_text
    assert "--mode" in command_text
    assert "json" in command_text
    assert seen["prompt"]
    assert seen["timeout"] == 8
    assert completion.metadata["route"] == "g2k-sensitive"
    assert "provider" not in completion.metadata
    assert "secret-provider" not in json.dumps(completion.metadata)
    assert parse_completion(
        completion.text,
        {"S1"},
        has_source_facts=True,
        has_conflict=False,
    )["answer"] == "Project Atlas was approved."


@pytest.mark.parametrize("position", ["before", "after"])
def test_gateway_backend_rejects_malformed_ndjson_around_valid_receipt(position: str):
    valid = _gateway_receipt(
        '{"answer":"fact","citations":["S1"],"stance":"supported"}'
    )
    output = (
        "{\"truncated\":\n" + valid
        if position == "before"
        else valid + "{\"truncated\":\n"
    )

    with pytest.raises(CompletionResponseError, match="malformed") as caught:
        GatewaySensitiveBackend(
            "/tmp/gateway2000.zsh",
            8,
            runner=lambda command, _prompt, _timeout: subprocess.CompletedProcess(
                command, 0, output, ""
            ),
        ).complete(_messages())
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_gateway_backend_rejects_oversized_injected_stderr():
    with pytest.raises(CompletionResponseError, match="stderr") as caught:
        GatewaySensitiveBackend(
            "/tmp/gateway2000.zsh",
            8,
            runner=lambda command, _prompt, _timeout: subprocess.CompletedProcess(
                command,
                0,
                _gateway_receipt(
                    '{"answer":"fact","citations":["S1"],"stance":"supported"}'
                ),
                "x" * (64_000 + 1),
            ),
        ).complete(_messages())
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_default_gateway_runner_discards_stderr(monkeypatch: pytest.MonkeyPatch):
    seen: dict[str, Any] = {}

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(args=args, kwargs=kwargs)
        return subprocess.CompletedProcess(args[0], 0, "", None)

    monkeypatch.setattr(subprocess, "run", fake_run)
    from work_corpus.answering import _default_gateway_runner

    _default_gateway_runner(["zsh", "-c", "true"], "prompt", 2)

    assert seen["kwargs"]["stdout"] is subprocess.PIPE
    assert seen["kwargs"]["stderr"] is subprocess.DEVNULL


def test_gateway_backend_drops_nested_provider_metadata_from_usage():
    response = json.dumps(
        {
            "type": "message_end",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": '{"answer":"fact","citations":["S1"],"stance":"supported"}',
                    }
                ],
                "usage": {
                    "input": 12,
                    "output": 7,
                    "provider": "secret-provider",
                    "model": "secret-model",
                    "nested": {"total": 19},
                },
            },
        }
    )

    completion = GatewaySensitiveBackend(
        "/tmp/gateway2000.zsh",
        8,
        runner=lambda command, _prompt, _timeout: subprocess.CompletedProcess(
            command, 0, response + "\n", ""
        ),
    ).complete(_messages())

    assert completion.metadata["usage"] == {"input": 12, "output": 7}
    assert "secret-provider" not in json.dumps(completion.metadata)
    assert "secret-model" not in json.dumps(completion.metadata)


@pytest.mark.parametrize(
    ("runner_error", "error_type", "error_message"),
    [
        (
            subprocess.TimeoutExpired("g2k-sensitive", 8, output="PRIVATE PROMPT"),
            CompletionTimeoutError,
            "timeout",
        ),
        (
            subprocess.CompletedProcess(
                ["g2k-sensitive"], 17, "PRIVATE PROMPT", "failure"
            ),
            CompletionTransportError,
            "exit",
        ),
    ],
)
def test_gateway_backend_reports_nonzero_or_timeout_without_prompt_text(
    runner_error: Any, error_type: type[Exception], error_message: str
):
    def runner(*_args: Any, **_kwargs: Any) -> Any:
        if isinstance(runner_error, BaseException):
            raise runner_error
        return runner_error

    with pytest.raises(error_type, match=error_message) as caught:
        GatewaySensitiveBackend(
            "/tmp/gateway2000.zsh", 8, runner=runner
        ).complete(_messages("PRIVATE PROMPT"))
    assert "PRIVATE PROMPT" not in str(caught.value)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert not hasattr(caught.value, "output")
    assert not hasattr(caught.value, "stderr")


def test_ollama_and_gateway_canaries_return_the_same_parsed_shape():
    response_text = (
        '{"answer":"Project Atlas was approved.","citations":["S1"],"stance":"supported"}'
    )
    ollama = OllamaBackend(
        "tiny-local",
        "http://127.0.0.1:11434",
        4,
        request_fn=lambda *_args: {
            "message": {"role": "assistant", "content": response_text}
        },
    ).complete(_messages())
    gateway = GatewaySensitiveBackend(
        "/tmp/gateway2000.zsh",
        8,
        runner=lambda command, _prompt, _timeout: subprocess.CompletedProcess(
            command, 0, _gateway_receipt(response_text), ""
        ),
    ).complete(_messages())

    allowed = {"S1"}
    assert parse_completion(ollama.text, allowed, True, False) == parse_completion(
        gateway.text, allowed, True, False
    )
