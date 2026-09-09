from __future__ import annotations

import copy
import hashlib
import json

from work_corpus.answering import (
    AnswerEvidence,
    EvidenceOnlyBackend,
    prepare_evidence,
)


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
                    "www.example.com/private and ftp://private.example/file.sqlite; "
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
        "ftp://private.example/file.sqlite",
        posix_path,
        windows_path,
        "+44 20 7946 0958",
        "+61 2 9374 4000",
    ):
        assert sensitive not in prepared.packet


def test_remote_packet_redacts_trailing_unc_and_unprefixed_phone_forms_without_losing_prose():
    trailing_posix_path = "/Users/Omar/data/"
    trailing_windows_path = "C:\\Users\\Omar\\data\\"
    unc_path = "\\\\server\\share\\foo\\"
    search_result = {
        "question": "What did Maya approve for Project Atlas?",
        "results": [
            _hit(
                1,
                snippet=(
                    "Maya copied /Users/Omar Smith then approved Project Atlas. "
                    "Maya copied /Users/Lina Stone because Maya approved Project Atlas. "
                    f"Trailing POSIX directory {trailing_posix_path}; "
                    f"Windows directory {trailing_windows_path}; UNC {unc_path}; "
                    "local call 020 7946 0958; international call "
                    "44 20 7946 0958; contiguous local call 02079460958; "
                    "contiguous international call 442079460958; "
                    "another local call 01632960001; another international "
                    "call 441632960001."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)
    packet = json.loads(prepared.packet)

    assert "Maya" in prepared.packet
    assert "then approved Project Atlas" in prepared.packet
    assert "because Maya approved Project Atlas" in prepared.packet
    assert packet["evidence"][0]["locator"] == "line:11"
    for sensitive in (
        trailing_posix_path,
        trailing_windows_path,
        unc_path,
        "020 7946 0958",
        "44 20 7946 0958",
        "02079460958",
        "442079460958",
        "01632960001",
        "441632960001",
    ):
        assert sensitive not in prepared.packet


def test_remote_packet_redacts_dotfile_paths_without_leaking_suffixes():
    posix_ssh_path = "/Users/Omar/.ssh/id_rsa"
    posix_env_path = "/tmp/.env"
    windows_path = "C:\\Users\\Omar\\.ssh\\id_rsa"
    unc_path = "\\\\server\\share\\.config\\settings.json"
    search_result = {
        "question": "Which Project Atlas files did Maya review?",
        "results": [
            _hit(
                1,
                snippet=(
                    f"Reviewed {posix_ssh_path}, {posix_env_path}, "
                    f"{windows_path}, and {unc_path}. Project Atlas remains approved."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Project Atlas remains approved" in prepared.packet
    for sensitive in (
        posix_ssh_path,
        posix_env_path,
        windows_path,
        unc_path,
    ):
        assert sensitive not in prepared.packet
    for leaked_suffix in (
        ".ssh/id_rsa",
        ".env",
        ".ssh\\id_rsa",
        ".config\\settings.json",
    ):
        assert leaked_suffix not in prepared.packet


def test_remote_packet_preserves_numeric_evidence_while_redacting_uk_phones():
    timestamp = "2026090812"
    ticket = "1234567890"
    phones = (
        "02079460958",
        "01632960001",
        "442079460958",
        "441632960001",
    )
    search_result = {
        "question": "What did Maya approve for Project Atlas?",
        "results": [
            _hit(
                1,
                snippet=(
                    f"Meeting timestamp {timestamp}; ticket {ticket}; "
                    + "; ".join(f"call {phone}" for phone in phones)
                    + ". Maya approved Project Atlas."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert timestamp in prepared.packet
    assert ticket in prepared.packet
    assert "Maya approved Project Atlas" in prepared.packet
    for phone in phones:
        assert phone not in prepared.packet


def test_remote_packet_redacts_quoted_and_colon_terminated_dotfile_paths():
    posix_path = "/Users/Omar/.ssh/id_rsa"
    windows_path = "C:\\Users\\Omar\\.ssh\\id_rsa"
    unc_path = "\\\\server\\share\\.config\\settings.json"
    search_result = {
        "question": "Which Project Atlas files did Maya review?",
        "results": [
            _hit(
                1,
                snippet=(
                    f'Quoted POSIX "{posix_path}"; '
                    f'quoted Windows "{windows_path}"; '
                    f'quoted UNC "{unc_path}". '
                    f"Colon POSIX: {posix_path}: "
                    f"Windows: {windows_path}: UNC: {unc_path}: "
                    "Project Atlas remains approved."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Quoted POSIX" in prepared.packet
    assert "Project Atlas remains approved" in prepared.packet
    for sensitive in (posix_path, windows_path, unc_path):
        assert sensitive not in prepared.packet
    for leaked_suffix in ("id_rsa", ".env", "settings.json"):
        assert leaked_suffix not in prepared.packet


def test_remote_packet_replaces_complete_spaced_database_and_dotfile_paths():
    paths = (
        "/Users/Omar Smith/private.sqlite",
        "/Users/Omar Smith/.config/settings.json",
        r"C:\Users\Omar Smith\private.sqlite",
        r"C:\Users\Omar Smith\.config\settings.json",
        r"\\server\shared folder\private.sqlite",
        r"\\server\shared folder\.config\settings.json",
    )
    search_result = {
        "question": "Which Project Atlas files did Maya review?",
        "results": [
            _hit(
                1,
                snippet=(
                    f'Quote "{paths[0]}": "{paths[1]}": '
                    f'"{paths[2]}": "{paths[3]}": '
                    f'"{paths[4]}": "{paths[5]}": '
                    f"Adjacent {paths[0]} {paths[2]} {paths[4]}. "
                    "Project Atlas remains approved."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Project Atlas remains approved" in prepared.packet
    for path in paths:
        assert path not in prepared.packet
    for leaked_suffix in (
        "private.sqlite",
        ".sqlite",
        ".config/settings.json",
        ".config\\settings.json",
        ".json",
        "settings.json",
    ):
        assert leaked_suffix not in prepared.packet


def test_remote_packet_replaces_lowercase_spaced_absolute_database_and_dotfile_paths():
    paths = (
        "/private/tmp/my db.sqlite",
        "/private/tmp/my .env",
        r"C:\tmp\my db.sqlite",
        r"C:\tmp\my .env",
        r"\\server\shared folder\my db.sqlite",
        r"\\server\shared folder\my .env",
    )
    search_result = {
        "question": "Which records were approved?",
        "results": [
            _hit(
                1,
                snippet=(
                    f'Quoted "{paths[0]}": "{paths[1]}": '
                    f'"{paths[2]}": "{paths[3]}": '
                    f'"{paths[4]}": "{paths[5]}": '
                    f"Adjacent {paths[0]} {paths[1]} {paths[2]} "
                    f"{paths[3]} {paths[4]} {paths[5]}. "
                    "Project Atlas remains approved."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Project Atlas remains approved" in prepared.packet
    for path in paths:
        assert path not in prepared.packet
    for leaked_component in (
        "private",
        "tmp",
        "my",
        "db.sqlite",
        ".sqlite",
        ".env",
        "server",
        "shared folder",
        "folder",
    ):
        assert leaked_component not in prepared.packet


def test_remote_packet_does_not_redact_ordinary_words_for_short_provenance_ids():
    hit = _hit(
        1,
        snippet="Project Atlas is safe; evidence is available.",
    )
    hit.update(
        evidence_id="e",
        source_id="s",
        source_version_id="v",
        source_path="s",
        relative_path="e",
        absolute_path="v",
    )

    prepared = prepare_evidence(
        {
            "question": "Is Project Atlas safe?",
            "results": [hit],
        },
        remote_safe=True,
    )

    assert "Project Atlas is safe; evidence is available." in prepared.packet
    assert "[REDACTED_IDENTIFIER]" not in prepared.packet


def test_evidence_only_backend_emits_source_facts_without_inference_snippets():
    source_fact = _hit(1, snippet="Project Atlas was approved by the source.")
    inference = _hit(2, snippet="Inference says Project Atlas may expand next quarter.")
    inference["label"] = "inference"
    inference["evidence_status"] = "inference"
    prepared = prepare_evidence(
        {
            "question": "What happened to Project Atlas?",
            "results": [source_fact, inference],
        }
    )

    completion = EvidenceOnlyBackend(prepared).complete([])

    assert "Project Atlas was approved by the source." in completion.text
    assert "Inference says Project Atlas may expand next quarter." not in completion.text


def test_remote_packet_uses_context_for_compact_uk_phones():
    ticket = "07123456789"
    timestamp = "441234567890"
    contextual_phones = (
        "02079460958",
        "01632960001",
        "442079460958",
        "441632960001",
    )
    us_phone = "(415)555-2671"
    search_result = {
        "question": "What did Maya approve for Project Atlas?",
        "results": [
            _hit(
                1,
                snippet=(
                    f"Ticket {ticket}; timestamp {timestamp}; "
                    "call "
                    + contextual_phones[0]
                    + "; phone "
                    + contextual_phones[1]
                    + "; tel "
                    + contextual_phones[2]
                    + "; mobile "
                    + contextual_phones[3]
                    + f"; US {us_phone}. Maya approved Project Atlas."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert ticket in prepared.packet
    assert timestamp in prepared.packet
    assert "Maya approved Project Atlas" in prepared.packet
    for phone in (*contextual_phones, us_phone):
        assert phone not in prepared.packet


def test_remote_packet_preserves_number_labeled_numeric_evidence():
    values = (
        "07123456789",
        "07123456789",
        "441234567890",
    )
    search_result = {
        "question": "Which Project Atlas record did Maya approve?",
        "results": [
            _hit(
                1,
                snippet=(
                    f"Ticket number {values[0]}; "
                    f"invoice number: {values[1]}; "
                    f"case number {values[2]}. Maya approved Project Atlas."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Ticket number 07123456789" in prepared.packet
    assert "invoice number: 07123456789" in prepared.packet
    assert "case number 441234567890" in prepared.packet
    assert "Maya approved Project Atlas" in prepared.packet


def test_remote_packet_redacts_key_value_parenthesized_and_list_phones():
    key_value_phone = "02079460958"
    parenthesized_phone = "01632960001"
    list_phones = ("02079460958", "01632960001")
    us_phone = "(415)555-2671"
    search_result = {
        "question": "Which Project Atlas contact did Maya record?",
        "results": [
            _hit(
                1,
                snippet=(
                    f"phone={key_value_phone}; call({parenthesized_phone}); "
                    f"call {list_phones[0]}, {list_phones[1]}; US {us_phone}. "
                    "Maya approved Project Atlas."
                ),
            )
        ],
    }

    prepared = prepare_evidence(search_result, remote_safe=True)

    assert "Maya approved Project Atlas" in prepared.packet
    for phone in (key_value_phone, parenthesized_phone, *list_phones, us_phone):
        assert phone not in prepared.packet


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
