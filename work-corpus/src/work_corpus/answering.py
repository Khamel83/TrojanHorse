"""Read-only evidence preparation for local answer evaluation.

The corpus remains the source of truth.  This module only prepares a bounded
JSON evidence packet and an in-memory map back to the complete local hits.
Model invocation and answer parsing belong to later answering tasks.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

from .query import redact_snippet


DEFAULT_MAX_HITS = 8
DEFAULT_MAX_SNIPPET_CHARS = 1_200
DEFAULT_MAX_TOTAL_CHARS = 12_000

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
