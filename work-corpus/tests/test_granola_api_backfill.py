from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from work_corpus.granola_api import (
    GranolaApiClient,
    GranolaApiError,
    build_capture,
    note_to_meeting,
    transcript_to_text,
)


def test_transcript_to_text_keeps_speaker_and_text_order():
    transcript = [
        {
            "speaker": {"diarization_label": "A", "source": "recording"},
            "text": "First point.",
        },
        {
            "speaker": {"diarization_label": "B", "source": "recording"},
            "text": "Second point.",
        },
    ]

    assert transcript_to_text(transcript) == "Speaker A: First point.\nSpeaker B: Second point."


def test_note_to_meeting_preserves_raw_note_and_combines_summary_with_transcript():
    note: Dict[str, Any] = {
        "id": "not_12345678901234",
        "title": "Project review",
        "created_at": "2026-09-06T18:00:00Z",
        "summary_markdown": "Decided to ship.",
        "summary_text": "Decided to ship.",
        "transcript": [
            {
                "speaker": {"diarization_label": "A"},
                "text": "Let's ship.",
            }
        ],
    }

    meeting = note_to_meeting(note)

    assert meeting["id"] == note["id"]
    assert meeting["title"] == note["title"]
    assert meeting["date"] == note["created_at"]
    assert meeting["summary"] == note["summary_markdown"]
    assert meeting["transcript"] == "Summary:\nDecided to ship.\n\nTranscript:\nSpeaker A: Let's ship."
    assert meeting["_api_note"] == note


def test_build_capture_contains_raw_api_notes_and_importable_meetings():
    notes = [
        {
            "id": "not_12345678901234",
            "title": "One",
            "created_at": "2026-09-06T18:00:00Z",
            "summary_text": "Summary",
            "transcript": [],
        }
    ]
    pages = [{"page": 1, "note_ids": [notes[0]["id"]], "has_more": False}]

    capture = build_capture(
        notes,
        list_pages=pages,
        capture_id="granola-api-backfill-test",
        captured_at="2026-09-06T20:00:00Z",
    )

    assert capture["provider"] == "granola"
    assert capture["notes"] == notes
    assert capture["meetings"][0]["id"] == notes[0]["id"]
    assert capture["_capture"]["transport"] == "granola_rest_api"
    assert capture["_capture"]["list_pages"] == pages


def test_client_uses_transcript_endpoint_after_413():
    note = {
        "id": "not_12345678901234",
        "title": "Large note",
        "created_at": "2026-09-06T18:00:00Z",
        "summary_text": "Summary",
        "transcript": None,
    }
    calls: List[tuple[str, Mapping[str, str]]] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        calls.append((path, params))
        if params.get("include") == "transcript":
            raise GranolaApiError("payload too large", status=413)
        if path.endswith("/transcript"):
            return {
                "transcript": [
                    {"speaker": {"diarization_label": "A"}, "text": "Long note."}
                ],
                "hasMore": False,
                "cursor": None,
            }
        return note

    client = GranolaApiClient("test-key", requester=requester)

    fetched = client.fetch_note(note["id"])

    assert fetched["transcript"] == [
        {"speaker": {"diarization_label": "A"}, "text": "Long note."}
    ]
    assert calls == [
        ("/v1/notes/not_12345678901234", {"include": "transcript"}),
        ("/v1/notes/not_12345678901234", {}),
        ("/v1/notes/not_12345678901234/transcript", {"page_size": "100"}),
    ]
