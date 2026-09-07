"""Granola REST API backfill helpers.

The client is intentionally small and read-only. It pages through the API
note list, fetches each note with its transcript, and falls back to the
paginated transcript endpoint when the inline response is too large.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


API_BASE_URL = "https://public-api.granola.ai"
LIST_PAGE_SIZE = 30
TRANSCRIPT_PAGE_SIZE = 100
MIN_REQUEST_INTERVAL_SECONDS = 0.21
MAX_RETRIES = 5

Requester = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


class GranolaApiError(RuntimeError):
    """A safe API error that does not include response bodies or credentials."""

    def __init__(
        self,
        message: str,
        *,
        status: Optional[int] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _retry_after(headers: Any) -> Optional[float]:
    value = headers.get("Retry-After") if headers is not None else None
    if value in (None, ""):
        return None
    try:
        return max(0.0, float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _default_requester(api_key: str) -> Requester:
    def request_json(path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        query = urlencode(dict(params))
        url = f"{API_BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            # Never include the provider response body. It is unnecessary for
            # retry decisions and could contain source text.
            raise GranolaApiError(
                f"Granola API returned HTTP {exc.code} for {path}",
                status=exc.code,
                retry_after=_retry_after(exc.headers),
            ) from None
        except URLError as exc:
            raise GranolaApiError(
                f"Granola API request failed for {path}: {type(exc.reason).__name__}"
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GranolaApiError(
                f"Granola API returned invalid JSON for {path}"
            ) from None
        if not isinstance(payload, Mapping):
            raise GranolaApiError(f"Granola API returned a non-object for {path}")
        return payload

    return request_json


def _is_retryable(error: GranolaApiError) -> bool:
    return error.status == 429 or (error.status is not None and error.status >= 500)


def transcript_to_text(transcript: Any) -> str:
    """Turn API transcript segments into stable searchable plain text."""
    if isinstance(transcript, str):
        return transcript.strip()
    if isinstance(transcript, Mapping):
        nested = transcript.get("transcript")
        if nested is not None:
            return transcript_to_text(nested)
    if not isinstance(transcript, Sequence) or isinstance(transcript, (bytes, bytearray)):
        return ""

    lines: List[str] = []
    for segment in transcript:
        if not isinstance(segment, Mapping):
            continue
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        speaker = segment.get("speaker")
        label = ""
        if isinstance(speaker, Mapping):
            label = str(
                speaker.get("diarization_label")
                or speaker.get("name")
                or speaker.get("source")
                or ""
            ).strip()
        elif speaker not in (None, ""):
            label = str(speaker).strip()
        if label:
            prefix = label if label.casefold().startswith("speaker ") else f"Speaker {label}"
            lines.append(f"{prefix}: {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def note_to_meeting(note: Mapping[str, Any]) -> Dict[str, Any]:
    """Create an importer-compatible record while retaining the raw API note."""
    summary = str(
        note.get("summary_markdown") or note.get("summary_text") or ""
    ).strip()
    transcript = transcript_to_text(note.get("transcript"))
    if summary and transcript:
        searchable_transcript = f"Summary:\n{summary}\n\nTranscript:\n{transcript}"
    else:
        searchable_transcript = summary or transcript
    return {
        "id": str(note.get("id") or "").strip(),
        "title": str(note.get("title") or "Granola note").strip(),
        "date": note.get("created_at") or note.get("updated_at") or "",
        "summary": summary,
        "transcript": searchable_transcript,
        "_api_note": dict(note),
    }


def build_capture(
    notes: Sequence[Mapping[str, Any]],
    *,
    list_pages: Sequence[Mapping[str, Any]],
    capture_id: str,
    captured_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the local raw capture envelope used by the existing importer."""
    raw_notes = [dict(note) for note in notes]
    return {
        "schema_version": 2,
        "provider": "granola",
        "capture_id": capture_id,
        "captured_at": captured_at
        or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "meetings": [note_to_meeting(note) for note in raw_notes],
        "notes": raw_notes,
        "_capture": {
            "transport": "granola_rest_api",
            "api_base_url": API_BASE_URL,
            "list_page_size": LIST_PAGE_SIZE,
            "transcript_page_size": TRANSCRIPT_PAGE_SIZE,
            "list_pages": [dict(page) for page in list_pages],
            "note_count": len(raw_notes),
        },
    }


class GranolaApiClient:
    """Read-only Granola API client with pagination and bounded retries."""

    def __init__(
        self,
        api_key: str,
        *,
        requester: Optional[Requester] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
        min_interval: float = MIN_REQUEST_INTERVAL_SECONDS,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Granola API key is required")
        self._requester = requester or _default_requester(api_key)
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._last_request_at: Optional[float] = None

    def _pace(self) -> None:
        now = self._monotonic()
        if self._last_request_at is not None:
            remaining = self._min_interval - (now - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()

    def _get(self, path: str, params: Mapping[str, str]) -> Mapping[str, Any]:
        for attempt in range(self._max_retries + 1):
            self._pace()
            try:
                return self._requester(path, dict(params))
            except GranolaApiError as error:
                if not _is_retryable(error) or attempt >= self._max_retries:
                    raise
                delay = error.retry_after
                if delay is None:
                    delay = min(30.0, float(2**attempt))
                self._sleep(delay)
        raise AssertionError("unreachable")

    def list_notes(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        notes: List[Dict[str, Any]] = []
        pages: List[Dict[str, Any]] = []
        params: Dict[str, str] = {"page_size": str(LIST_PAGE_SIZE)}
        for page_number in range(1, 1001):
            payload = self._get("/v1/notes", params)
            batch = payload.get("notes")
            if not isinstance(batch, list):
                raise GranolaApiError("Granola list response has no notes array")
            page_notes = [dict(note) for note in batch if isinstance(note, Mapping)]
            notes.extend(page_notes)
            has_more = bool(payload.get("hasMore"))
            cursor = payload.get("cursor")
            pages.append(
                {
                    "page": page_number,
                    "note_ids": [str(note.get("id") or "") for note in page_notes],
                    "has_more": has_more,
                    "cursor": cursor,
                }
            )
            if not has_more:
                return notes, pages
            if not cursor:
                raise GranolaApiError("Granola list response hasMore without cursor")
            params = {"page_size": str(LIST_PAGE_SIZE), "cursor": str(cursor)}
        raise GranolaApiError("Granola list pagination exceeded safety limit")

    def fetch_note(self, note_id: str) -> Dict[str, Any]:
        safe_id = quote(str(note_id), safe="")
        path = f"/v1/notes/{safe_id}"
        try:
            return dict(self._get(path, {"include": "transcript"}))
        except GranolaApiError as error:
            if error.status != 413:
                raise

        note = dict(self._get(path, {}))
        transcript: List[Dict[str, Any]] = []
        params: Dict[str, str] = {"page_size": str(TRANSCRIPT_PAGE_SIZE)}
        for _page_number in range(1, 1001):
            page = self._get(f"{path}/transcript", params)
            batch = page.get("transcript")
            if not isinstance(batch, list):
                raise GranolaApiError(
                    f"Granola transcript response has no transcript array for {note_id}"
                )
            transcript.extend(
                dict(segment) for segment in batch if isinstance(segment, Mapping)
            )
            if not page.get("hasMore"):
                note["transcript"] = transcript
                return note
            cursor = page.get("cursor")
            if not cursor:
                raise GranolaApiError(
                    f"Granola transcript response hasMore without cursor for {note_id}"
                )
            params = {
                "page_size": str(TRANSCRIPT_PAGE_SIZE),
                "cursor": str(cursor),
            }
        raise GranolaApiError(
            f"Granola transcript pagination exceeded safety limit for {note_id}"
        )


def run_backfill(
    client: GranolaApiClient,
    *,
    capture_id: str,
    captured_at: Optional[str] = None,
    progress_stream: Any = sys.stderr,
) -> Dict[str, Any]:
    """Fetch every currently listed API note and return one capture."""
    listed_notes, list_pages = client.list_notes()
    fetched: List[Dict[str, Any]] = []
    total = len(listed_notes)
    for index, listed_note in enumerate(listed_notes, start=1):
        note_id = str(listed_note.get("id") or "").strip()
        if not note_id:
            raise GranolaApiError("Granola list contained a note without an id")
        fetched.append(client.fetch_note(note_id))
        if progress_stream is not None and (index == 1 or index % 25 == 0 or index == total):
            print(f"granola API backfill: fetched {index}/{total}", file=progress_stream)
    return build_capture(
        fetched,
        list_pages=list_pages,
        capture_id=capture_id,
        captured_at=captured_at,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Fetch a complete Granola REST API snapshot")
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--api-key", default=None, help="Use only on a trusted host; prefer GRANOLA_API_KEY")
    args = parser.parse_args(argv)
    api_key = args.api_key or os.environ.get("GRANOLA_API_KEY", "")
    if not api_key:
        parser.error("GRANOLA_API_KEY is required")
    try:
        capture = run_backfill(
            GranolaApiClient(api_key),
            capture_id=args.capture_id,
        )
    except (GranolaApiError, ValueError) as error:
        print(f"granola API backfill failed: {error}", file=sys.stderr)
        return 1
    json.dump(capture, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
