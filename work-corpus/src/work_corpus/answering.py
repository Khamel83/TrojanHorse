"""Read-only evidence preparation for local answer evaluation.

The corpus remains the source of truth.  This module only prepares a bounded
JSON evidence packet and an in-memory map back to the complete local hits.
Model invocation and answer parsing belong to later answering tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import math
import re
import socket
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Protocol
from typing import Sequence, Union
from urllib.parse import urlsplit, urlunsplit

from .query import redact_snippet


DEFAULT_MAX_HITS = 8
DEFAULT_MAX_SNIPPET_CHARS = 1_200
DEFAULT_MAX_TOTAL_CHARS = 12_000

# Completion request/receipt bounds are deliberately independent of the
# evidence-packet bounds.  They protect the adapters when a caller supplies a
# hand-built message rather than a packet from ``prepare_evidence``.
MAX_COMPLETION_PROMPT_CHARS = 24_000
MAX_COMPLETION_RESPONSE_CHARS = 64_000
MAX_COMPLETION_TIMEOUT_SECONDS = 600.0

# Short aliases make the limits easy for callers and tests to discover while
# keeping the descriptive names used internally.
MAX_PROMPT_CHARS = MAX_COMPLETION_PROMPT_CHARS
MAX_RESPONSE_CHARS = MAX_COMPLETION_RESPONSE_CHARS

_EMAIL_RE = re.compile(
    r"\b[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
    r"(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+\b",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(
    r"(?<![\w])(?:"
    r"\+\d{1,3}(?:[ \t().-]*\d){6,12}"
    r"|(?:\(\d{3}\)[\s.-]*|\d{3}[\s.-]+)\d{3}[\s.-]+\d{4}"
    r"|0\d{2}[ \t.-]\d{4}[ \t.-]\d{4}"
    r"|\d{2}[ \t.-]\d{2}[ \t.-]\d{4}[ \t.-]\d{4}"
    r")(?![\w])"
)
_COMPACT_UK_PHONE_RE = r"(?:0[127]\d{9}|44[127]\d{9})"
_COMPACT_UK_PHONE_CONTEXT_RE = re.compile(
    rf"(?P<context>\b(?:calls?|phones?|tel|mobile|contact)\b"
    rf"(?:[ \t]*(?:the|is|at|us|me|number)\b)*[ \t:=().-]*?)"
    rf"(?P<number>{_COMPACT_UK_PHONE_RE})(?![\w])",
    re.IGNORECASE,
)
_COMPACT_UK_PHONE_LIST_RE = re.compile(
    rf"(?P<prefix>\[REDACTED_PHONE\][ \t]*[,;][ \t]*)"
    rf"(?P<number>{_COMPACT_UK_PHONE_RE})(?![\w])"
)
_REMOTE_URL_RE = re.compile(
    r"(?<![@\w./\\:-])(?:"
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\"']+"
    r"|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?"
    r"(?:/[^\s<>\"']*)?"
    r")",
    re.IGNORECASE,
)
# A path component may contain spaces.  A bounded two-word terminal covers
# names such as ``/Users/Omar Smith`` and stops before a lowercase prose token
# without a stop-word allowlist.  The single-token form also stops before the
# next ordinary word, which keeps prose after a path out of the replacement.
_PATH_TOKEN = r"(?:\.+)?[^\s<>\"'/,;!?\\:.]+(?:\.[^\s<>\"'/,;!?\\:.]+)*"
_PATH_COMPONENT = rf"{_PATH_TOKEN}(?:[ \t]+{_PATH_TOKEN})*"
_PATH_TERMINAL = (
    rf"(?:"
    rf"(?=[A-Z]){_PATH_TOKEN}[ \t]+(?=[A-Z0-9]){_PATH_TOKEN}"
    rf"(?=$|[,;.!?)]|[\"']|:|[ \t]+[a-z])"
    rf"|{_PATH_TOKEN}(?=$|[,;.!?)]|[\"']|:|[ \t]+(?=[A-Za-z0-9]))"
    rf")"
)
_POSIX_PATH_RE = re.compile(
    rf"(?<![\w:])(?:"
    rf"/(?:{_PATH_COMPONENT}/)*{_PATH_TERMINAL}/?"
    rf"|/(?:{_PATH_COMPONENT}/)+"
    rf")"
)
_WINDOWS_PATH_RE = re.compile(
    rf"(?<![\w])[A-Za-z]:[\\/](?:"
    rf"(?:{_PATH_COMPONENT}[\\/])*{_PATH_TERMINAL}[\\/]?"
    rf"|(?:{_PATH_COMPONENT}[\\/])+"
    rf")"
)
_UNC_PATH_RE = re.compile(
    rf"(?<![\w])(?:\\\\|//)(?:"
    rf"(?:{_PATH_COMPONENT}[\\/])+{_PATH_TERMINAL}[\\/]?"
    rf"|(?:{_PATH_COMPONENT}[\\/])+"
    rf")"
)


@dataclass(frozen=True)
class AnswerEvidence:
    """One packet citation with the complete local hit retained in memory."""

    citation_id: str
    hit: Mapping[str, Any]
    packet_entry: Mapping[str, Any]

    @property
    def local_hit(self) -> Mapping[str, Any]:
        return self.hit

    @property
    def source_id(self) -> Optional[str]:
        value = self.hit.get("source_id")
        return str(value) if value is not None else None

    @property
    def source_version_id(self) -> Optional[str]:
        value = self.hit.get("source_version_id")
        return str(value) if value is not None else None

    @property
    def locator(self) -> Optional[str]:
        value = self.hit.get("locator")
        return str(value) if value is not None else None

    def __getitem__(self, key: str) -> Any:
        """Permit citation inspection using the familiar hit mapping shape."""
        return self.hit[key]


@dataclass(frozen=True)
class PreparedEvidence:
    """Deterministic packet plus ephemeral local citation state."""

    packet: str
    citation_map: Mapping[str, AnswerEvidence]
    packet_sha256: str
    sanitizer_findings: List[str]

    @property
    def citations(self) -> Mapping[str, AnswerEvidence]:
        return self.citation_map

    @property
    def digest(self) -> str:
        return self.packet_sha256

    @property
    def findings(self) -> List[str]:
        return self.sanitizer_findings

    def __iter__(self) -> Iterator[Any]:
        """Support the concise four-value return form used by callers."""
        yield self.packet
        yield self.citation_map
        yield self.packet_sha256
        yield self.sanitizer_findings

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return tuple(self)[key]
        aliases = {
            "packet": "packet",
            "citation_map": "citation_map",
            "citations": "citation_map",
            "packet_sha256": "packet_sha256",
            "digest": "packet_sha256",
            "sanitizer_findings": "sanitizer_findings",
            "findings": "sanitizer_findings",
        }
        try:
            return getattr(self, aliases[key])
        except KeyError as exc:
            raise KeyError(key) from exc

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


# Descriptive aliases keep the public return type discoverable while allowing
# later callers to use whichever noun is clearest in their context.
EvidencePreparation = PreparedEvidence
EvidencePacket = PreparedEvidence


@dataclass(frozen=True)
class Completion:
    """One untrusted completion and bounded, non-content metadata."""

    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


class CompletionBackend(Protocol):
    """Small common interface for local, gateway, and evidence backends."""

    name: str

    def complete(self, messages: Sequence[Mapping[str, str]]) -> Completion:
        """Return one completion for the supplied prompt messages."""
        ...


class CompletionError(RuntimeError):
    """Base class for bounded backend and parsing failures."""


class CompletionTimeoutError(CompletionError):
    """A backend exceeded its configured timeout."""


class CompletionTransportError(CompletionError):
    """A backend could not obtain a usable response."""


class CompletionResponseError(CompletionTransportError):
    """A backend response was malformed or exceeded its bound."""


class CompletionModelError(CompletionError):
    """The selected model or route reported a completion error."""


class CompletionParseError(CompletionError):
    """A model completion did not satisfy the strict answer contract."""


# Friendly aliases allow callers to use either the completion-oriented names
# above or the shorter backend names without creating a second error taxonomy.
BackendError = CompletionError
BackendTimeoutError = CompletionTimeoutError
BackendTransportError = CompletionTransportError
BackendMalformedError = CompletionResponseError
BackendModelError = CompletionModelError


def _validate_timeout(value: Union[int, float], name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    if timeout > MAX_COMPLETION_TIMEOUT_SECONDS:
        raise ValueError(f"{name} exceeds the maximum allowed timeout")
    return timeout


def _normalise_messages(
    messages: Sequence[Mapping[str, str]],
) -> List[Dict[str, str]]:
    if isinstance(messages, (str, bytes)) or not isinstance(messages, Sequence):
        raise CompletionError("messages must be a sequence of mappings")

    normalised: List[Dict[str, str]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise CompletionError("messages must contain mappings")
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not role.strip():
            raise CompletionError("messages require a role")
        if not isinstance(content, str):
            raise CompletionError("messages require text content")
        if len(role) > 256:
            raise CompletionError("message role is too long")
        normalised.append({"role": role, "content": content})
    return normalised


def _encoded_messages(messages: Sequence[Mapping[str, str]]) -> str:
    return json.dumps(
        {"messages": list(messages)},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _bounded_messages(
    messages: Sequence[Mapping[str, str]],
    *,
    max_chars: int = MAX_COMPLETION_PROMPT_CHARS,
) -> List[Dict[str, str]]:
    """Keep message shape while truncating only content from the end."""
    bounded = [dict(message) for message in messages]
    if len(_encoded_messages(bounded)) <= max_chars:
        return bounded

    # Remove text from the last message first.  This retains the system
    # contract and the beginning of the user question when a caller submits a
    # deliberately oversized prompt.
    for index in range(len(bounded) - 1, -1, -1):
        content = bounded[index]["content"]
        low, high = 0, len(content)
        best = 0
        while low <= high:
            middle = (low + high) // 2
            candidate = [dict(message) for message in bounded]
            candidate[index]["content"] = content[:middle]
            if len(_encoded_messages(candidate)) <= max_chars:
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        bounded[index]["content"] = content[:best]
        if len(_encoded_messages(bounded)) <= max_chars:
            return bounded

    # The fixed role/JSON overhead should always fit under the configured
    # bound.  Keep a defensive failure with no dynamic content if a caller
    # changes the bound to an impossible value.
    raise CompletionError("prompt exceeds the maximum allowed size")


def _messages_prompt(messages: Sequence[Mapping[str, str]]) -> str:
    bounded = _bounded_messages(_normalise_messages(messages))
    prompt = "\n\n".join(
        f"{message['role']}: {message['content']}" for message in bounded
    )
    # The JSON bound includes structural characters.  Keep the shell lane's
    # flattened representation independently bounded as well.
    return prompt[:MAX_COMPLETION_PROMPT_CHARS]


def _allowed_citation_ids(allowed_citations: Any) -> set[str]:
    values = (
        allowed_citations.keys()
        if isinstance(allowed_citations, Mapping)
        else allowed_citations
    )
    try:
        result = set(values)
    except (TypeError, ValueError) as exc:
        raise CompletionParseError("allowed citations are invalid") from exc
    if not all(isinstance(value, str) for value in result):
        raise CompletionParseError("allowed citations are invalid")
    return result


def parse_completion(
    text: str,
    allowed_citations: Any,
    has_source_facts: bool,
    has_conflict: bool,
) -> Dict[str, Any]:
    """Parse one strict answer object without turning model text into evidence."""
    if not isinstance(text, str) or len(text) > MAX_COMPLETION_RESPONSE_CHARS:
        raise CompletionParseError("completion is too large")
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise CompletionParseError("completion is not valid JSON") from exc

    if not isinstance(parsed, dict) or set(parsed) != {
        "answer",
        "citations",
        "stance",
    }:
        raise CompletionParseError("completion must contain only answer, citations, and stance")

    answer = parsed.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise CompletionParseError("answer must not be empty")

    citations = parsed.get("citations")
    if not isinstance(citations, list):
        raise CompletionParseError("citations must be a list")
    if any(not isinstance(citation, str) or not citation for citation in citations):
        raise CompletionParseError("citations must contain text IDs")
    if len(citations) != len(set(citations)):
        raise CompletionParseError("duplicate citation IDs are not allowed")

    allowed = _allowed_citation_ids(allowed_citations)
    if any(citation not in allowed for citation in citations):
        raise CompletionParseError("unknown citation ID")
    if has_source_facts and not citations:
        raise CompletionParseError("source facts require at least one citation")

    stance = parsed.get("stance")
    if stance not in {"supported", "inferred", "mixed", "insufficient"}:
        raise CompletionParseError("stance is invalid")
    if has_conflict and stance not in {"mixed", "insufficient"}:
        raise CompletionParseError("conflict requires mixed or insufficient stance")

    return {
        "answer": answer.strip(),
        "citations": list(citations),
        "stance": stance,
    }


def _packet_from_messages(
    messages: Sequence[Mapping[str, str]],
) -> Optional[Mapping[str, Any]]:
    """Recover an evidence packet only when a caller supplied raw JSON data."""
    for message in reversed(messages):
        content = message.get("content") if isinstance(message, Mapping) else None
        if not isinstance(content, str):
            continue
        try:
            packet = json.loads(content)
        except (TypeError, ValueError):
            continue
        if isinstance(packet, Mapping) and isinstance(packet.get("evidence"), list):
            return packet
    return None


class EvidenceOnlyBackend:
    """Format prepared evidence directly without invoking a model."""

    name = "evidence"

    def __init__(self, prepared_evidence: Optional[PreparedEvidence] = None):
        self.prepared_evidence = prepared_evidence

    def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        prepared_evidence: Optional[PreparedEvidence] = None,
    ) -> Completion:
        prepared = prepared_evidence or self.prepared_evidence
        entries: List[tuple[str, str]] = []
        if prepared is not None:
            for citation_id, evidence in prepared.citation_map.items():
                snippet = str(evidence.packet_entry.get("snippet") or "").strip()
                if snippet:
                    entries.append((citation_id, snippet))
        else:
            packet = _packet_from_messages(_normalise_messages(messages))
            if packet is not None:
                for item in packet.get("evidence", []):
                    if not isinstance(item, Mapping):
                        continue
                    citation_id = item.get("citation_id")
                    snippet = item.get("snippet")
                    if isinstance(citation_id, str) and isinstance(snippet, str):
                        if snippet.strip():
                            entries.append((citation_id, snippet.strip()))

        citations = [citation_id for citation_id, _snippet in entries]
        if entries:
            answer = "\n".join(
                f"[{citation_id}] {snippet}" for citation_id, snippet in entries
            )
            stance = "supported"
        else:
            answer = "No source-backed facts are available."
            stance = "insufficient"
        return Completion(
            text=json.dumps(
                {
                    "answer": answer,
                    "citations": citations,
                    "stance": stance,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            metadata={
                "backend": self.name,
                "route": self.name,
                "citation_count": len(citations),
            },
        )


def _loopback_endpoint(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError("base_url must be a loopback URL")
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise ValueError("base_url must be a loopback URL") from exc
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("base_url must be a loopback URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("base_url must be a loopback URL")
    is_loopback = host.casefold() == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False
    if not is_loopback:
        raise ValueError("base_url must be a loopback URL")
    path = parsed.path.rstrip("/")
    if path.endswith("/api/chat"):
        endpoint_path = path
    elif path.endswith("/api"):
        endpoint_path = f"{path}/chat"
    else:
        endpoint_path = f"{path}/api/chat" if path else "/api/chat"
    return urlunsplit((parsed.scheme, parsed.netloc, endpoint_path, "", ""))


def _default_ollama_request(
    url: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> Any:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(MAX_COMPLETION_RESPONSE_CHARS + 1)
    if len(raw) > MAX_COMPLETION_RESPONSE_CHARS:
        raise CompletionResponseError("ollama response exceeds the maximum size")
    return raw


def _decode_json_response(response: Any, *, backend: str) -> Mapping[str, Any]:
    if hasattr(response, "read") and not isinstance(response, (str, bytes, bytearray)):
        try:
            response = response.read(MAX_COMPLETION_RESPONSE_CHARS + 1)
        except Exception as exc:
            raise CompletionTransportError(f"{backend} response could not be read") from exc
    if isinstance(response, Mapping):
        return response
    if isinstance(response, bytearray):
        response = bytes(response)
    if isinstance(response, bytes):
        if len(response) > MAX_COMPLETION_RESPONSE_CHARS:
            raise CompletionResponseError(f"{backend} response exceeds the maximum size")
        try:
            response = response.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CompletionResponseError(f"{backend} response is malformed") from exc
    if not isinstance(response, str) or len(response) > MAX_COMPLETION_RESPONSE_CHARS:
        raise CompletionResponseError(f"{backend} response is malformed")
    try:
        decoded = json.loads(response)
    except (TypeError, ValueError) as exc:
        raise CompletionResponseError(f"{backend} response is malformed") from exc
    if not isinstance(decoded, Mapping):
        raise CompletionResponseError(f"{backend} response is malformed")
    return decoded


def _safe_metadata_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _safe_metadata_value(item)
            for key, item in value.items()
            if isinstance(key, (str, int, float, bool))
        }
    if isinstance(value, (list, tuple)):
        return [_safe_metadata_value(item) for item in value]
    return None


class OllamaBackend:
    """Call a loopback Ollama chat endpoint with bounded JSON prompts."""

    name = "ollama"

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        timeout_seconds: Union[int, float] = 30,
        request_fn: Optional[Callable[..., Any]] = None,
    ):
        if not isinstance(model, str) or not model.strip() or len(model) > 256:
            raise ValueError("model must be a non-empty bounded string")
        self.model = model.strip()
        self.endpoint = _loopback_endpoint(base_url)
        self.timeout_seconds = _validate_timeout(timeout_seconds, "timeout_seconds")
        self._request_fn = request_fn or _default_ollama_request

    def complete(self, messages: Sequence[Mapping[str, str]]) -> Completion:
        bounded_messages = _bounded_messages(_normalise_messages(messages))
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": bounded_messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        try:
            response = self._request_fn(
                self.endpoint,
                payload,
                self.timeout_seconds,
            )
        except CompletionTimeoutError as exc:
            raise CompletionTimeoutError("ollama timeout") from exc
        except CompletionModelError as exc:
            raise CompletionModelError("ollama model error") from exc
        except CompletionResponseError as exc:
            raise CompletionResponseError("ollama response is malformed") from exc
        except CompletionTransportError as exc:
            raise CompletionTransportError("ollama transport failure") from exc
        except CompletionError as exc:
            raise CompletionTransportError("ollama transport failure") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise CompletionTimeoutError("ollama timeout") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise CompletionTimeoutError("ollama timeout") from exc
            raise CompletionTransportError("ollama transport failure") from exc
        except Exception as exc:
            raise CompletionTransportError("ollama transport failure") from exc

        data = _decode_json_response(response, backend="ollama")
        if data.get("error") is not None:
            raise CompletionModelError("ollama model error")
        message = data.get("message")
        if not isinstance(message, Mapping):
            raise CompletionResponseError("ollama response is malformed")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise CompletionResponseError("ollama response is malformed")
        if len(content) > MAX_COMPLETION_RESPONSE_CHARS:
            raise CompletionResponseError("ollama response exceeds the maximum size")
        metadata: Dict[str, Any] = {
            "backend": self.name,
            "route": self.name,
            "model": self.model,
        }
        for key in (
            "created_at",
            "done",
            "done_reason",
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
        ):
            if key in data:
                metadata[key] = _safe_metadata_value(data[key])
        return Completion(text=content, metadata=metadata)


def _default_gateway_runner(
    command: Sequence[str],
    prompt: str,
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )


def _runner_result(result: Any) -> tuple[int, str, str]:
    if isinstance(result, subprocess.CompletedProcess):
        code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    elif isinstance(result, Mapping):
        code = result.get("returncode", result.get("exit_code", 0))
        stdout = result.get("stdout", result.get("output", ""))
        stderr = result.get("stderr", "")
    elif isinstance(result, (tuple, list)):
        if len(result) == 3 and isinstance(result[0], int):
            code, stdout, stderr = result
        elif len(result) == 3 and isinstance(result[2], int):
            stdout, stderr, code = result
        elif len(result) == 2:
            stdout, stderr = result
            code = 0
        else:
            raise CompletionTransportError("gateway runner returned an invalid result")
    elif isinstance(result, (str, bytes, bytearray)):
        code, stdout, stderr = 0, result, ""
    else:
        code = getattr(result, "returncode", 0)
        stdout = getattr(result, "stdout", "")
        stderr = getattr(result, "stderr", "")

    if isinstance(stdout, bytearray):
        stdout = bytes(stdout)
    if isinstance(stderr, bytearray):
        stderr = bytes(stderr)
    if isinstance(stdout, bytes):
        try:
            stdout = stdout.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CompletionResponseError("gateway response is malformed") from exc
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    if not isinstance(code, int) or isinstance(code, bool):
        raise CompletionTransportError("gateway runner returned an invalid result")
    if not isinstance(stdout, str) or not isinstance(stderr, str):
        raise CompletionTransportError("gateway runner returned an invalid result")
    if len(stdout.encode("utf-8")) > MAX_COMPLETION_RESPONSE_CHARS:
        raise CompletionResponseError("gateway response exceeds the maximum size")
    return code, stdout, stderr


def _message_text(message: Mapping[str, Any]) -> Optional[str]:
    content = message.get("content")
    if isinstance(content, str):
        return content if content.strip() else None
    if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
        return None
    pieces: List[str] = []
    for item in content:
        if isinstance(item, str):
            pieces.append(item)
        elif isinstance(item, Mapping) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                pieces.append(text)
    text = "".join(pieces)
    return text if text.strip() else None


def _gateway_completion(
    stdout: str,
) -> tuple[str, Mapping[str, Any]]:
    malformed_line = False
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except (TypeError, ValueError):
            malformed_line = True
            continue
        if not isinstance(event, Mapping):
            malformed_line = True
            continue
        if event.get("type") == "error":
            raise CompletionModelError("gateway model error")
        if event.get("type") != "message_end":
            continue
        message = event.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        text = _message_text(message)
        if text is None:
            continue
        metadata: Dict[str, Any] = {
            "backend": "g2k-sensitive",
            "route": "g2k-sensitive",
            "gateway_route": "gateway2000/sensitive",
        }
        if isinstance(message.get("id"), (str, int)):
            metadata["message_id"] = message["id"]
        if isinstance(message.get("usage"), Mapping):
            metadata["usage"] = _safe_metadata_value(message["usage"])
        for key in ("finish_reason", "stop_reason"):
            if isinstance(message.get(key), (str, int, float, bool)):
                metadata[key] = message[key]
        return text, metadata
    if malformed_line:
        raise CompletionResponseError("gateway response is malformed")
    raise CompletionResponseError("gateway response has no assistant message")


class GatewaySensitiveBackend:
    """Invoke a sourced ``g2k-sensitive`` helper without provider claims."""

    name = "g2k-sensitive"

    def __init__(
        self,
        helper_path: Union[str, Path],
        timeout_seconds: Union[int, float],
        runner: Optional[Callable[..., Any]] = None,
    ):
        if not isinstance(helper_path, (str, Path)) or not str(helper_path).strip():
            raise ValueError("helper_path must be a non-empty path")
        self.helper_path = str(helper_path)
        self.timeout_seconds = _validate_timeout(timeout_seconds, "timeout_seconds")
        self._runner = runner or _default_gateway_runner

    def complete(self, messages: Sequence[Mapping[str, str]]) -> Completion:
        prompt = _messages_prompt(messages)
        shell_script = (
            'source "$1"; '
            'shift; '
            "g2k-sensitive --no-session --no-tools --no-extensions --mode json -p \"$(cat)\""
        )
        command = [
            "zsh",
            "-c",
            shell_script,
            "work-corpus-gateway",
            self.helper_path,
        ]
        try:
            result = self._runner(command, prompt, self.timeout_seconds)
        except (TimeoutError, socket.timeout, subprocess.TimeoutExpired) as exc:
            raise CompletionTimeoutError("gateway timeout") from exc
        except CompletionTimeoutError as exc:
            raise CompletionTimeoutError("gateway timeout") from exc
        except CompletionResponseError as exc:
            raise CompletionResponseError("gateway response is malformed") from exc
        except CompletionTransportError as exc:
            raise CompletionTransportError("gateway transport failure") from exc
        except CompletionError as exc:
            raise CompletionTransportError("gateway transport failure") from exc
        except Exception as exc:
            raise CompletionTransportError("gateway transport failure") from exc

        code, stdout, _stderr = _runner_result(result)
        if code != 0:
            raise CompletionTransportError("gateway process exit status was nonzero")
        text, metadata = _gateway_completion(stdout)
        metadata = dict(metadata)
        metadata["exit_code"] = code
        return Completion(text=text, metadata=metadata)


def _validate_bound(value: int, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _hit_value(hit: Mapping[str, Any], name: str) -> Any:
    value = hit.get(name)
    if value is None:
        return None
    return str(value)


def _date_value(hit: Mapping[str, Any]) -> Any:
    value = hit.get("date_value")
    if value is None:
        value = hit.get("observed_date")
    return value


def _date_basis(hit: Mapping[str, Any]) -> Any:
    value = hit.get("date_basis")
    if value is None:
        value = hit.get("observed_date_basis")
    if value is None:
        value = hit.get("source_date_basis")
    return value


def _is_citable(hit: Mapping[str, Any]) -> bool:
    """Require enough provenance for a citation to be inspected locally."""
    version = hit.get("source_version_id")
    locator = hit.get("locator")
    identity = hit.get("evidence_id") or hit.get("source_id")
    return bool(version and locator and identity)


def _ordered_hits(search_result: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    raw_hits = search_result.get("results") or ()
    # ``search`` already supplies a deterministic relevance order.  Preserve
    # it so the hit cap does not silently replace the best evidence with a
    # lexical ordering of opaque provenance IDs.
    return [
        hit for hit in raw_hits if isinstance(hit, Mapping) and _is_citable(hit)
    ]


def _local_entry(citation_id: str, hit: Mapping[str, Any]) -> Dict[str, Any]:
    # Keep the packet's local representation explicit.  The citation map
    # retains every other hit field for inspection without serializing it.
    fields = (
        "label",
        "evidence_status",
        "evidence_id",
        "source_id",
        "source_version_id",
        "source_path",
        "relative_path",
        "absolute_path",
        "locator",
        "date_basis",
        "source_date_basis",
        "date_value",
        "scope",
        "source_system",
        "sensitivity",
        "match_type",
    )
    entry: Dict[str, Any] = {"citation_id": citation_id}
    for field in fields:
        if field == "date_value":
            value = _date_value(hit)
        elif field == "date_basis":
            value = _date_basis(hit)
        else:
            value = _hit_value(hit, field)
        if value is not None:
            entry[field] = value
    entry["snippet"] = redact_snippet(str(hit.get("snippet") or ""))
    return entry


def _remote_text(
    value: Any,
    *,
    citation_id: str,
    field: str,
    findings: List[str],
    known_sensitive: Sequence[str],
) -> str:
    original = str(value or "")
    text = redact_snippet(original)
    if text != original:
        findings.append(f"{citation_id}:{field}:url_or_secret")

    remote_url_text = _REMOTE_URL_RE.sub("[REDACTED_URL]", text)
    if remote_url_text != text:
        text = remote_url_text
        findings.append(f"{citation_id}:{field}:url_or_secret")

    replacements = (
        ("email", _EMAIL_RE),
        ("phone", _PHONE_RE),
        ("path", _WINDOWS_PATH_RE),
        ("path", _UNC_PATH_RE),
        ("path", _POSIX_PATH_RE),
    )
    for kind, pattern in replacements:
        if pattern.search(text):
            text = pattern.sub("[REDACTED_{}]".format(kind.upper()), text)
            findings.append(f"{citation_id}:{field}:{kind}")

    contextual_phone_text = _COMPACT_UK_PHONE_CONTEXT_RE.sub(
        lambda match: f"{match.group('context')}[REDACTED_PHONE]",
        text,
    )
    if contextual_phone_text != text:
        text = contextual_phone_text
        findings.append(f"{citation_id}:{field}:phone")

    while True:
        list_phone_text = _COMPACT_UK_PHONE_LIST_RE.sub(
            lambda match: f"{match.group('prefix')}[REDACTED_PHONE]",
            text,
        )
        if list_phone_text == text:
            break
        text = list_phone_text
        findings.append(f"{citation_id}:{field}:phone")

    for sensitive in sorted(
        {str(item) for item in known_sensitive if item},
        key=lambda item: (-len(item), item),
    ):
        if sensitive in text:
            text = text.replace(sensitive, "[REDACTED_IDENTIFIER]")
            findings.append(f"{citation_id}:{field}:identifier")
    return text


def _remote_entry(
    citation_id: str,
    hit: Mapping[str, Any],
    *,
    findings: List[str],
    known_sensitive: Sequence[str],
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"citation_id": citation_id}
    for field in ("label", "scope", "source_system", "date_value", "date_basis"):
        value = (
            _date_value(hit)
            if field == "date_value"
            else _date_basis(hit)
            if field == "date_basis"
            else hit.get(field)
        )
        if value is not None:
            entry[field] = _remote_text(
                value,
                citation_id=citation_id,
                field=field,
                findings=findings,
                known_sensitive=known_sensitive,
            )
    # ``locator`` is retained for source inspection, but receives the same
    # sanitizer as snippets because imported locators can contain paths.
    entry["locator"] = _remote_text(
        hit.get("locator"),
        citation_id=citation_id,
        field="locator",
        findings=findings,
        known_sensitive=known_sensitive,
    )
    entry["snippet"] = _remote_text(
        hit.get("snippet"),
        citation_id=citation_id,
        field="snippet",
        findings=findings,
        known_sensitive=known_sensitive,
    )
    return entry


def _bounded_base(question: str, max_total_chars: int) -> tuple[Dict[str, Any], str]:
    packet: Dict[str, Any] = {"evidence": [], "question": question}
    encoded = _json_text(packet)
    if len(encoded) <= max_total_chars:
        return packet, encoded

    # Preserve valid JSON and the packet shape even when a caller deliberately
    # supplies an unusually small total bound.
    low, high = 0, len(question)
    best = _json_text({"evidence": [], "question": ""})
    while low <= high:
        middle = (low + high) // 2
        candidate = _json_text(
            {"evidence": [], "question": question[:middle]}
        )
        if len(candidate) <= max_total_chars:
            best = candidate
            low = middle + 1
        else:
            high = middle - 1
    if len(best) > max_total_chars:
        if max_total_chars < 2:
            raise ValueError("max_total_chars must allow a JSON packet")
        return {}, "{}"
    return json.loads(best), best


def _append_entry(
    packet: Dict[str, Any],
    entry: Dict[str, Any],
    *,
    max_total_chars: int,
    max_snippet_chars: int,
) -> Optional[Dict[str, Any]]:
    snippet = str(entry.get("snippet") or "")[:max_snippet_chars]
    candidate_entry = dict(entry)
    candidate_entry["snippet"] = snippet
    candidate_packet = dict(packet)
    candidate_packet["evidence"] = [
        *packet.get("evidence", []),
        candidate_entry,
    ]
    encoded = _json_text(candidate_packet)
    if len(encoded) <= max_total_chars:
        packet["evidence"].append(candidate_entry)
        return candidate_entry

    # Metadata can consume most of a small packet.  Find the longest snippet
    # that still fits, retaining the citation when its locator does fit.
    low, high = 0, len(snippet)
    best: Optional[Dict[str, Any]] = None
    while low <= high:
        middle = (low + high) // 2
        candidate_entry = dict(entry)
        candidate_entry["snippet"] = snippet[:middle]
        candidate_packet["evidence"] = [
            *packet.get("evidence", []),
            candidate_entry,
        ]
        if len(_json_text(candidate_packet)) <= max_total_chars:
            best = candidate_entry
            low = middle + 1
        else:
            high = middle - 1
    if best is None:
        return None
    packet["evidence"].append(best)
    return best


def prepare_evidence(
    search_result: Mapping[str, Any],
    *,
    remote_safe: bool = False,
    max_hits: int = DEFAULT_MAX_HITS,
    max_snippet_chars: int = DEFAULT_MAX_SNIPPET_CHARS,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> PreparedEvidence:
    """Build one deterministic, bounded packet and its local citation map.

    ``remote_safe`` controls only the serialized packet.  The citation map
    always points at complete local hits and is never included in the packet.
    Packet snippets are data; this function never evaluates or executes them.
    """
    if not isinstance(search_result, Mapping):
        raise TypeError("search_result must be a mapping")
    _validate_bound(max_hits, "max_hits")
    _validate_bound(max_snippet_chars, "max_snippet_chars")
    _validate_bound(max_total_chars, "max_total_chars")

    hits = _ordered_hits(search_result)
    selected = hits[:max_hits]
    sensitive_values: List[str] = []
    for hit in selected:
        for field in (
            "evidence_id",
            "source_id",
            "source_version_id",
            "source_path",
            "relative_path",
            "absolute_path",
        ):
            value = hit.get(field)
            if value:
                sensitive_values.append(str(value))

    findings: List[str] = []
    question = str(search_result.get("question") or "")
    if remote_safe:
        question = _remote_text(
            question,
            citation_id="QUESTION",
            field="question",
            findings=findings,
            known_sensitive=sensitive_values,
        )
    else:
        question = redact_snippet(question)
    packet, _encoded = _bounded_base(question, max_total_chars)
    citation_map: Dict[str, AnswerEvidence] = {}

    for hit in selected:
        citation_id = f"S{len(citation_map) + 1}"
        entry = (
            _remote_entry(
                citation_id,
                hit,
                findings=findings,
                known_sensitive=sensitive_values,
            )
            if remote_safe
            else _local_entry(citation_id, hit)
        )
        added = _append_entry(
            packet,
            entry,
            max_total_chars=max_total_chars,
            max_snippet_chars=max_snippet_chars,
        )
        if added is None:
            continue
        citation_map[citation_id] = AnswerEvidence(
            citation_id=citation_id,
            hit=hit,
            packet_entry=added,
        )

    encoded = _json_text(packet)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    # Keep findings deterministic even when the same sensitive value occurs in
    # several fields.
    findings = list(dict.fromkeys(findings))
    return PreparedEvidence(
        packet=encoded,
        citation_map=citation_map,
        packet_sha256=digest,
        sanitizer_findings=findings,
    )
