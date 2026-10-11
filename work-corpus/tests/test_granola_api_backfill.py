from __future__ import annotations

import io
import json
from typing import Any, Dict, List, Mapping, Optional
from urllib.error import HTTPError, URLError

import pytest

import work_corpus.granola_api as granola_api
from work_corpus.granola_api import (
    GranolaApiClient,
    GranolaApiError,
    build_capture,
    note_to_meeting,
    run_backfill,
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


def test_list_notes_sends_updated_after_on_every_cursor_page():
    calls: List[tuple[str, Mapping[str, str]]] = []
    note_one = {"id": "one", "updated_at": "2026-09-07T10:00:00Z"}
    note_two = {"id": "two", "updated_at": "2026-09-07T10:01:00Z"}

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        calls.append((path, params))
        if path == "/v1/notes":
            if params.get("cursor") == "next-page":
                return {"notes": [note_two], "hasMore": False, "cursor": None}
            return {"notes": [note_one], "hasMore": True, "cursor": "next-page"}
        return {}

    client = GranolaApiClient("test-key", requester=requester)

    notes, pages = client.list_notes(updated_after="2026-09-07T09:55:00Z")

    assert [note["id"] for note in notes] == ["one", "two"]
    assert len(pages) == 2
    assert calls == [
        (
            "/v1/notes",
            {"page_size": "30", "updated_after": "2026-09-07T09:55:00Z"},
        ),
        (
            "/v1/notes",
            {
                "page_size": "30",
                "cursor": "next-page",
                "updated_after": "2026-09-07T09:55:00Z",
            },
        ),
    ]


def test_transcript_to_text_accepts_strings_nested_payloads_and_plain_speakers():
    assert transcript_to_text("  hello  ") == "hello"
    assert (
        transcript_to_text({"transcript": [{"text": "hi", "speaker": "B"}]})
        == "Speaker B: hi"
    )
    assert (
        transcript_to_text(
            [
                {"text": "plain"},
                {"text": "", "speaker": "A"},
                {"speaker": {"source": "C"}, "text": "sourced"},
                {"no_text_key": 1},
            ]
        )
        == "plain\nSpeaker C: sourced"
    )
    assert transcript_to_text(123) == ""


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": " 2.5 "}, 2.5),
        ({"Retry-After": "soon"}, None),
        ({"Retry-After": ""}, None),
        ({"Retry-After": "-4"}, 0.0),
        ({}, None),
        (None, None),
    ],
)
def test_retry_after_parsing_tolerates_missing_and_malformed_values(headers, expected):
    assert granola_api._retry_after(headers) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [(429, True), (500, True), (503, True), (404, False), (None, False)],
)
def test_retryable_status_classification(status, expected):
    assert granola_api._is_retryable(GranolaApiError("x", status=status)) is expected


def test_client_retries_retryable_status_and_honors_retry_after():
    attempts: List[str] = []
    delays: List[float] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        attempts.append(path)
        if len(attempts) == 1:
            raise GranolaApiError("rate limited", status=429, retry_after=2.5)
        return {"id": "note-1"}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        sleep_fn=delays.append,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    assert client.fetch_note("note-1")["id"] == "note-1"
    assert delays == [2.5]
    assert attempts == ["/v1/notes/note-1", "/v1/notes/note-1"]


def test_client_uses_exponential_backoff_when_retry_after_is_absent():
    attempts: List[int] = []
    delays: List[float] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        attempts.append(1)
        if len(attempts) < 3:
            raise GranolaApiError("server error", status=500)
        return {"id": "note-1"}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        sleep_fn=delays.append,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    client.fetch_note("note-1")
    assert delays == [1.0, 2.0]


def test_client_raises_after_exhausting_retry_budget():
    attempts: List[int] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        attempts.append(1)
        raise GranolaApiError("server error", status=503)

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
        max_retries=2,
    )

    with pytest.raises(GranolaApiError):
        client.fetch_note("note-1")
    assert len(attempts) == 3


def test_client_does_not_retry_non_retryable_client_errors():
    attempts: List[int] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        attempts.append(1)
        raise GranolaApiError("not found", status=404)

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    with pytest.raises(GranolaApiError) as excinfo:
        client.fetch_note("note-1")
    assert excinfo.value.status == 404
    assert len(attempts) == 1


def test_list_notes_rejects_missing_array_and_hasmore_without_cursor():
    def missing_array(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        return {"notes": None}

    client = GranolaApiClient("test-key", requester=missing_array)
    with pytest.raises(GranolaApiError, match="no notes array"):
        client.list_notes()

    def has_more_without_cursor(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        return {"notes": [], "hasMore": True, "cursor": None}

    client = GranolaApiClient("test-key", requester=has_more_without_cursor)
    with pytest.raises(GranolaApiError, match="hasMore without cursor"):
        client.list_notes()


def test_fetch_note_propagates_non_413_errors_without_fallback():
    calls: List[str] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        calls.append(path)
        raise GranolaApiError("forbidden", status=403)

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        sleep_fn=lambda _seconds: None,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    with pytest.raises(GranolaApiError) as excinfo:
        client.fetch_note("note-1")
    assert excinfo.value.status == 403
    assert calls == ["/v1/notes/note-1"]


def test_fetch_note_paginates_the_transcript_endpoint():
    calls: List[Dict[str, str]] = []

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        calls.append({"path": path, **params})
        if params.get("include") == "transcript":
            raise GranolaApiError("payload too large", status=413)
        if path.endswith("/transcript"):
            if params.get("cursor") == "page-2":
                return {
                    "transcript": [{"text": "second"}],
                    "hasMore": False,
                    "cursor": None,
                }
            return {"transcript": [{"text": "first"}], "hasMore": True, "cursor": "page-2"}
        return {"id": "note-1"}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    note = client.fetch_note("note-1")

    assert [segment["text"] for segment in note["transcript"]] == ["first", "second"]
    assert calls[-1] == {
        "path": "/v1/notes/note-1/transcript",
        "page_size": "100",
        "cursor": "page-2",
    }


def test_fetch_note_rejects_transcript_response_without_array():
    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        if params.get("include") == "transcript":
            raise GranolaApiError("payload too large", status=413)
        if path.endswith("/transcript"):
            return {"hasMore": False}
        return {"id": "note-1"}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    with pytest.raises(GranolaApiError, match="no transcript array"):
        client.fetch_note("note-1")


def test_run_backfill_marks_delta_mode_and_reports_progress():
    notes = [{"id": "n1", "title": "one"}, {"id": "n2", "title": "two"}]

    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        if path == "/v1/notes":
            return {"notes": notes, "hasMore": False, "cursor": None}
        return {"id": path.rsplit("/", 1)[1], "title": path}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )
    progress = io.StringIO()

    capture = run_backfill(
        client,
        capture_id="granola-delta",
        captured_at="2026-09-07T20:00:00Z",
        updated_after="2026-09-07T19:00:00Z",
        progress_stream=progress,
    )

    assert capture["_capture"]["mode"] == "delta"
    assert capture["_capture"]["updated_after"] == "2026-09-07T19:00:00Z"
    assert capture["_capture"]["note_count"] == 2
    assert [meeting["id"] for meeting in capture["meetings"]] == ["n1", "n2"]
    assert "fetched 1/2" in progress.getvalue()
    assert "fetched 2/2" in progress.getvalue()


def test_run_backfill_marks_archive_mode_without_updated_after():
    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        if path == "/v1/notes":
            return {"notes": [{"id": "n1"}], "hasMore": False, "cursor": None}
        return {"id": "n1"}

    client = GranolaApiClient(
        "test-key",
        requester=requester,
        monotonic_fn=lambda: 0.0,
        min_interval=0.0,
    )

    capture = run_backfill(
        client,
        capture_id="granola-archive",
        captured_at="2026-09-07T20:00:00Z",
        progress_stream=None,
    )

    assert capture["_capture"]["mode"] == "archive"
    assert capture["_capture"]["updated_after"] is None


def test_run_backfill_rejects_a_listed_note_without_an_id():
    def requester(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        return {"notes": [{"title": "no id"}], "hasMore": False, "cursor": None}

    client = GranolaApiClient("test-key", requester=requester)

    with pytest.raises(GranolaApiError, match="without an id"):
        run_backfill(client, capture_id="granola-bad", progress_stream=None)


def test_request_json_maps_http_error_without_leaking_the_response_body(monkeypatch):
    def fake_urlopen(request, timeout=60):
        raise HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            {"Retry-After": "3"},
            io.BytesIO(b"provider-secret-body"),
        )

    monkeypatch.setattr(granola_api, "urlopen", fake_urlopen)
    requester = granola_api._default_requester("unit-key")

    with pytest.raises(GranolaApiError) as excinfo:
        requester("/v1/notes", {"page_size": "30"})

    assert excinfo.value.status == 429
    assert excinfo.value.retry_after == 3.0
    assert "provider-secret-body" not in str(excinfo.value)
    assert "unit-key" not in str(excinfo.value)


def test_request_json_maps_transport_and_payload_failures(monkeypatch):
    class _Response:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def read(self) -> bytes:
            return self._payload

    requester = granola_api._default_requester("unit-key")

    def url_error(request, timeout=60):
        raise URLError(OSError("connection refused"))

    monkeypatch.setattr(granola_api, "urlopen", url_error)
    with pytest.raises(GranolaApiError, match="request failed"):
        requester("/v1/notes", {})

    monkeypatch.setattr(
        granola_api, "urlopen", lambda request, timeout=60: _Response(b"<html>oops")
    )
    with pytest.raises(GranolaApiError, match="invalid JSON"):
        requester("/v1/notes", {})

    monkeypatch.setattr(
        granola_api, "urlopen", lambda request, timeout=60: _Response(b"[]")
    )
    with pytest.raises(GranolaApiError, match="non-object"):
        requester("/v1/notes", {})

    monkeypatch.setattr(
        granola_api, "urlopen", lambda request, timeout=60: _Response(b'{"notes": []}')
    )
    assert requester("/v1/notes", {}) == {"notes": []}


def test_main_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("GRANOLA_API_KEY", raising=False)
    with pytest.raises(SystemExit) as excinfo:
        granola_api.main(["--capture-id", "granola-cli"])
    assert excinfo.value.code == 2


def test_main_reports_backfill_failure_without_leaking_credentials(
    monkeypatch, capsys
):
    monkeypatch.setenv("GRANOLA_API_KEY", "unit-key")

    def boom(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        raise GranolaApiError("rate limited")

    monkeypatch.setattr(granola_api, "run_backfill", boom)

    assert granola_api.main(["--capture-id", "granola-cli"]) == 1
    err = capsys.readouterr().err
    assert "granola API backfill failed" in err
    assert "unit-key" not in err


def test_main_writes_the_capture_as_json(monkeypatch, capsys):
    monkeypatch.setenv("GRANOLA_API_KEY", "unit-key")
    monkeypatch.setattr(
        granola_api,
        "run_backfill",
        lambda *args, **kwargs: {"provider": "granola", "meetings": []},
    )

    assert granola_api.main(["--capture-id", "granola-cli"]) == 0
    assert json.loads(capsys.readouterr().out) == {"provider": "granola", "meetings": []}
