from __future__ import annotations

import copy
import hashlib
import json

from work_corpus.answering import AnswerEvidence, prepare_evidence


def _hit(index: int, *, snippet: str) -> dict[str, str]:
    return {
        "label": "canonical",
        "evidence_status": "canonical",
        "evidence_id": f"evidence-{index}",
        "source_id": f"source-{index}",
        "source_version_id": f"version-{index}",
        "source_path": f"/Users/omar/TrojanHorse/data/work/project-{index}.md",
        "relative_path": f"data/work/project-{index}.md",
        "absolute_path": f"/Users/omar/TrojanHorse/data/work/project-{index}.md",
        "locator": f"line:{index + 10}",
        "date_basis": "meeting_date",
        "source_date_basis": "meeting_date",
        "date_value": "2026-09-08",
        "scope": "Work",
        "source_system": "synthetic",
        "sensitivity": "internal",
        "snippet": snippet,
        "match_type": "exact",
    }


def test_prepare_evidence_is_stable_and_keeps_local_citation_provenance():
    search_result = {
        "question": "What did Maya decide for Project Atlas?",
        "results": [
            _hit(
                1,
                snippet=(
                    "Maya decided that Project Atlas ships on 2026-09-08. "
                    "Contact maya@example.test at +1 (415) 555-2671. "
                    "See https://example.test/private?token=secret-value. "
                    "Authorization: Bearer bearer-secret and api_key=plain-secret. "
                    "The source is /Users/omar/TrojanHorse/data/work/project-1.md."
                ),
            ),
            _hit(
                2,
                snippet="Project Atlas remains owned by Omar; Maya is the reviewer.",
            ),
        ],
    }

    local = prepare_evidence(search_result)
    local_repeat = prepare_evidence(copy.deepcopy(search_result))
    remote = prepare_evidence(search_result, remote_safe=True)

    assert isinstance(local.citation_map["S1"], AnswerEvidence)
    assert local.packet == local_repeat.packet
    assert local.packet_sha256 == local_repeat.packet_sha256
    assert remote.packet == prepare_evidence(
        copy.deepcopy(search_result), remote_safe=True
    ).packet
    assert remote.packet_sha256 == hashlib.sha256(
        remote.packet.encode("utf-8")
    ).hexdigest()
    assert local.packet_sha256 != remote.packet_sha256

    first = remote.citation_map["S1"]
    assert first.hit["source_id"] == "source-1"
    assert first.hit["source_version_id"] == "version-1"
    assert first.hit["locator"] == "line:11"
    assert first.local_hit == first.hit
    assert first.source_id == "source-1"
    assert first.source_version_id == "version-1"
    assert first.locator == "line:11"


def test_remote_packet_redacts_sensitive_values_and_preserves_safe_words():
    search_result = {
        "question": "What did Maya decide for Project Atlas?",
        "results": [
            _hit(
                1,
                snippet=(
                    "Maya and Omar approved Project Atlas. "
                    "Email maya@example.test, call +1 (415) 555-2671, "
                    "open https://example.test/private?token=secret-value, "
                    "Bearer bearer-secret, api_key=plain-secret, "
                    "and /Users/omar/TrojanHorse/data/work/project-1.md."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Maya" in prepared.packet
    assert "Omar" in prepared.packet
    assert "Project Atlas" in prepared.packet
    for sensitive in (
        "maya@example.test",
        "+1 (415) 555-2671",
        "https://example.test/private?token=secret-value",
        "bearer-secret",
        "plain-secret",
        "/Users/omar/TrojanHorse/data/work/project-1.md",
        "source-1",
        "version-1",
        "evidence-1",
    ):
        assert sensitive not in prepared.packet

    assert prepared.sanitizer_findings
    packet = json.loads(prepared.packet)
    assert packet["question"] == "What did Maya decide for Project Atlas?"
    assert packet["evidence"][0]["citation_id"] == "S1"
    assert packet["evidence"][0]["scope"] == "Work"
    assert packet["evidence"][0]["date_value"] == "2026-09-08"
    assert packet["evidence"][0]["locator"] == "line:11"
    assert "source_id" not in packet["evidence"][0]
    assert "source_version_id" not in packet["evidence"][0]
    assert "absolute_path" not in packet["evidence"][0]


def test_remote_packet_redacts_non_http_urls_spaced_paths_and_international_phones():
    posix_path = "/Users/Omar Smith/private.sqlite"
    windows_path = r"C:\Users\Omar Smith\private.sqlite"
    search_result = {
        "question": "Which Project Atlas contact did Maya record?",
        "results": [
            _hit(
                1,
                snippet=(
                    "Maya and Omar approved Project Atlas. Visit "
                    "www.example.com/private and ftp://private.example/file; "
                    f"POSIX {posix_path}; Windows {windows_path}; "
                    "call +44 20 7946 0958 or +61 2 9374 4000."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)
    packet = json.loads(prepared.packet)

    assert "Maya" in prepared.packet
    assert "Omar" in prepared.packet
    assert "Project Atlas" in prepared.packet
    assert packet["evidence"][0]["locator"] == "line:11"
    for sensitive in (
        "www.example.com/private",
        "ftp://private.example/file",
        posix_path,
        windows_path,
        "+44 20 7946 0958",
        "+61 2 9374 4000",
    ):
        assert sensitive not in prepared.packet


def test_prepare_evidence_bounds_hits_snippets_and_total_packet():
    search_result = {
        "question": "Which Project Atlas notes mention Maya?",
        "results": [
            _hit(index, snippet=f"Project Atlas Maya {'x' * 4000}")
            for index in range(12)
        ],
    }

    prepared = prepare_evidence(
        search_result,
        remote_safe=True,
        max_hits=8,
        max_snippet_chars=120,
        max_total_chars=1_200,
    )
    packet = json.loads(prepared.packet)

    assert len(packet["evidence"]) <= 8
    assert len(prepared.packet) <= 1_200
    assert all(len(item["snippet"]) <= 120 for item in packet["evidence"])
    assert list(prepared.citation_map) == [
        f"S{index}" for index in range(1, len(packet["evidence"]) + 1)
    ]
    assert all(
        prepared.citation_map[citation_id].hit["source_version_id"]
        for citation_id in prepared.citation_map
    )


def test_prepare_evidence_result_can_be_unpacked_as_four_values():
    prepared = prepare_evidence(
        {
            "question": "What did Maya decide?",
            "results": [_hit(1, snippet="Maya decided Project Atlas ships.")],
        },
        remote_safe=True,
    )

    packet, citation_map, digest, findings = prepared

    assert packet == prepared.packet
    assert citation_map is prepared.citation_map
    assert digest == prepared.packet_sha256
    assert findings == prepared.sanitizer_findings
