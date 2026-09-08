"""Resumable, local-first Granola REST delta maintenance."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from .config import Config, load_config
from .granola_api import GranolaApiClient, GranolaApiError, run_backfill
from .query import rebuild_search_index
from .util import atomic_write_json, ensure_dir, now_iso, read_json


CHECKPOINT_RELATIVE_PATH = Path("mcp") / "granola_rest_delta.json"
LOCK_NAME = "granola_rest_delta.lock"
DEFAULT_OVERLAP_SECONDS = 300
STAGE_ORDER = (
    "inventory",
    "mcp-import",
    "normalize",
    "organize",
    "views",
    "report",
)


class DeltaAlreadyRunning(RuntimeError):
    """Raised when another local delta writer holds the advisory lock."""


StageRunner = Callable[[Config, Path], Optional[Mapping[str, Any]]]


def _record_index_checkpoint(config: Config, con) -> Dict[str, Any]:
    """Keep the report's index-freshness receipt current after a delta."""
    scrubbed_rows = rebuild_search_index(con)
    state = {
        "fts_rows": int(con.execute("SELECT COUNT(*) FROM derived_text_fts").fetchone()[0]),
        "relationship_rows": int(con.execute("SELECT COUNT(*) FROM relationship").fetchone()[0]),
        "scrubbed_rows": int(scrubbed_rows),
        "verified_at": now_iso(),
        "fts_api": "work_corpus.query.rebuild_search_index",
        "relationship_api": "work_corpus.entities (delta maintenance checkpoint)",
    }
    path = config.state_dir / "index_rebuild.json"
    config.assert_derived_path(path)
    atomic_write_json(path, state)
    return state


def _parse_timestamp(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _timestamp(value: Any) -> Optional[str]:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _provider_updated_at(note: Mapping[str, Any]) -> Optional[datetime]:
    return _parse_timestamp(note.get("updated_at"))


def _max_provider_updated_at(notes: Sequence[Mapping[str, Any]]) -> Optional[str]:
    values = [
        value
        for value in (_provider_updated_at(note) for note in notes)
        if value is not None
    ]
    if not values:
        return None
    return _timestamp(max(values))


def _checkpoint_path(config: Config) -> Path:
    path = config.state_dir / CHECKPOINT_RELATIVE_PATH
    config.assert_derived_path(path)
    return path


def _raw_dir(config: Config) -> Path:
    # This is the one intentional writer below data/: it is the provider's
    # immutable response archive, never a derived output.
    return config.source_root("mcp_granola").path


def _latest_archive_watermark(raw_dir: Path) -> Optional[str]:
    candidates: List[tuple[int, str]] = []
    for path in sorted(raw_dir.glob("granola-api-backfill-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, TypeError, ValueError, json.JSONDecodeError):
            continue
        capture = payload.get("_capture") if isinstance(payload, Mapping) else None
        if not isinstance(capture, Mapping):
            continue
        if capture.get("transport") != "granola_rest_api":
            continue
        notes = payload.get("notes") if isinstance(payload, Mapping) else None
        if not isinstance(notes, list):
            continue
        watermark = _max_provider_updated_at(
            [note for note in notes if isinstance(note, Mapping)]
        )
        if watermark:
            candidates.append((path.stat().st_mtime_ns, watermark))
    if not candidates:
        return None
    return max(candidates, key=lambda value: value[0])[1]


def _base_watermark(config: Config, explicit: Optional[str]) -> str:
    if explicit:
        normalized = _timestamp(explicit)
        if normalized is None:
            raise ValueError("updated_after must be an ISO-8601 timestamp")
        return normalized
    checkpoint = read_json(_checkpoint_path(config), {})
    if isinstance(checkpoint, Mapping):
        normalized = _timestamp(checkpoint.get("last_successful_provider_updated_at"))
        if normalized:
            return normalized
    seeded = _latest_archive_watermark(_raw_dir(config))
    if seeded:
        return seeded
    raise ValueError(
        "no Granola delta checkpoint or local REST archive watermark exists; "
        "provide --updated-after for the first bounded run"
    )


def _atomic_write_raw(path: Path, payload: Mapping[str, Any]) -> None:
    ensure_dir(path.parent)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary_name, path)
        os.chmod(path, 0o600)
    finally:
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass


def _capture_path(raw_dir: Path, capture_id: str) -> tuple[Path, str]:
    path = raw_dir / f"{capture_id}.json"
    if not path.exists():
        return path, capture_id
    for attempt in range(1, 1000):
        retry_id = f"{capture_id}-retry-{attempt:03d}"
        retry_path = raw_dir / f"{retry_id}.json"
        if not retry_path.exists():
            return retry_path, retry_id
    raise RuntimeError("could not allocate a unique Granola delta capture path")


@contextmanager
def _single_writer_lock(config: Config):
    lock_path = config.state_dir / "mcp" / LOCK_NAME
    config.assert_derived_path(lock_path)
    ensure_dir(lock_path.parent)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DeltaAlreadyRunning("Granola delta runner is already active") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _run_local_stages(config: Config, _raw_path: Path) -> Dict[str, Any]:
    """Run the complete local maintenance chain in dependency order."""
    from .db import connect
    from .inventory import inventory
    from .mcp_ingest import ingest_mcp_sources
    from .normalize import normalize_all
    from .organization import organize_all
    from .report import build_report
    from .views import build_views

    ensure_dir(config.corpus_dir)
    ensure_dir(config.state_dir)
    con = connect(
        config.state_dir / "work_corpus.sqlite",
        skip_classifications=config.get("normalization", "skip_classifications"),
    )
    try:
        details: Dict[str, Any] = {}
        details["inventory"] = inventory(config, con, full_hash=False)
        details["mcp-import"] = ingest_mcp_sources(config, con)
        details["normalize"] = normalize_all(config, con)
        details["organize"] = organize_all(config, con)
        details["organize"]["index_verification"] = _record_index_checkpoint(
            config, con
        )
        details["views"] = build_views(config, con)
        details["report"] = build_report(config, con)
        return details
    finally:
        con.close()


def run_delta(
    config: Config,
    client: Optional[GranolaApiClient] = None,
    *,
    api_key: Optional[str] = None,
    updated_after: Optional[str] = None,
    overlap_seconds: Optional[int] = None,
    captured_at: Optional[str] = None,
    stage_runner: Optional[StageRunner] = None,
) -> Dict[str, Any]:
    """Capture and locally process one bounded Granola delta."""
    with _single_writer_lock(config):
        overlap = (
            int(overlap_seconds)
            if overlap_seconds is not None
            else int(
                config.get(
                    "mcp", "granola_delta_overlap_seconds", DEFAULT_OVERLAP_SECONDS
                )
            )
        )
        if overlap < 0:
            raise ValueError("overlap_seconds must not be negative")
        base = _base_watermark(config, updated_after)
        base_dt = _parse_timestamp(base)
        if base_dt is None:
            raise ValueError("Granola watermark is not a valid ISO-8601 timestamp")
        request_after = _timestamp(base_dt - timedelta(seconds=overlap))
        if request_after is None:
            raise ValueError("could not calculate Granola delta watermark")

        capture_time = _timestamp(captured_at) or _utc_now()
        capture_seed = "granola-api-delta-" + capture_time.replace(":", "-")
        capture_path, capture_id = _capture_path(_raw_dir(config), capture_seed)
        if client is None:
            key = api_key or os.environ.get("GRANOLA_API_KEY", "")
            if not key:
                raise ValueError("GRANOLA_API_KEY is required")
            client = GranolaApiClient(key)
        capture = run_backfill(
            client,
            capture_id=capture_id,
            captured_at=capture_time,
            updated_after=request_after,
        )
        _atomic_write_raw(capture_path, capture)

        runner = stage_runner or _run_local_stages
        stage_details = runner(config, capture_path)
        notes = capture.get("notes")
        notes_list = [note for note in notes if isinstance(note, Mapping)] if isinstance(notes, list) else []
        latest = _max_provider_updated_at(notes_list) or base
        checkpoint = {
            "schema_version": 1,
            "provider": "granola",
            "mode": "delta",
            "updated_at": now_iso(),
            "last_successful_provider_updated_at": latest,
            "last_successful_capture_id": capture_id,
            "raw_capture_path": capture_path.relative_to(config.root).as_posix(),
            "requested_updated_after": request_after,
            "overlap_seconds": overlap,
            "note_count": len(notes_list),
            "stage_order": list(STAGE_ORDER),
            "stage_details": dict(stage_details or {}),
            "raw_boundary": {
                "raw_capture_appended": True,
                "raw_data_modified": False,
                "external_writes": 0,
            },
        }
        atomic_write_json(_checkpoint_path(config), checkpoint)
        return {
            "mode": "delta",
            "capture_id": capture_id,
            "raw_capture_path": str(capture_path),
            "requested_updated_after": request_after,
            "note_count": len(notes_list),
            "watermark": latest,
            "checkpoint_path": str(_checkpoint_path(config)),
            "stage_order": list(STAGE_ORDER),
            "stages": dict(stage_details or {}),
        }


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run one bounded Granola REST delta")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--updated-after",
        default=None,
        help="Explicit ISO-8601 seed for the first bounded run; never performs a full fetch.",
    )
    parser.add_argument("--overlap-seconds", type=int, default=None)
    args = parser.parse_args(argv)
    config = load_config(args.root.expanduser().resolve())
    try:
        result = run_delta(
            config,
            updated_after=args.updated_after,
            overlap_seconds=args.overlap_seconds,
        )
    except (GranolaApiError, DeltaAlreadyRunning, ValueError, OSError, RuntimeError) as error:
        print(f"granola delta failed: {error}", file=os.sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
