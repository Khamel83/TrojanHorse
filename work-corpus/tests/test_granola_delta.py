from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Mapping

import pytest

from work_corpus.config import load_config
from work_corpus.granola_delta import (
    DeltaAlreadyRunning,
    _single_writer_lock,
    _run_local_stages,
    run_delta,
)
from work_corpus.db import connect


class FakeClient:
    def __init__(self, notes: List[Mapping[str, Any]]):
        self.notes = [dict(note) for note in notes]
        self.updated_after: List[str | None] = []

    def list_notes(self, updated_after=None):
        self.updated_after.append(updated_after)
        return list(self.notes), [
            {
                "page": 1,
                "note_ids": [str(note.get("id")) for note in self.notes],
                "has_more": False,
                "cursor": None,
            }
        ]

    def fetch_note(self, note_id: str):
        return next(note for note in self.notes if str(note.get("id")) == note_id)


def _seed_archive(tmp_path: Path, updated_at: str) -> None:
    path = tmp_path / "data/mcp/granola/granola-api-backfill-seed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "provider": "granola",
                "notes": [{"id": "seed", "updated_at": updated_at}],
                "_capture": {"transport": "granola_rest_api", "mode": "archive"},
            }
        ),
        encoding="utf-8",
    )


def test_delta_uses_overlap_and_advances_checkpoint_after_stages(tmp_path: Path):
    _seed_archive(tmp_path, "2026-09-07T10:00:00Z")
    config = load_config(tmp_path)
    client = FakeClient(
        [
            {
                "id": "changed-note",
                "title": "Changed note",
                "updated_at": "2026-09-07T10:02:00Z",
                "created_at": "2026-09-07T09:00:00Z",
                "summary_text": "Summary",
                "transcript": [],
            }
        ]
    )
    stages: List[Path] = []

    result = run_delta(
        config,
        client,
        captured_at="2026-09-07T10:05:00Z",
        stage_runner=lambda _config, raw_path: stages.append(raw_path),
    )

    assert client.updated_after == ["2026-09-07T09:55:00Z"]
    assert stages and stages[0].is_file()
    assert stages[0].stat().st_mode & 0o777 == 0o600
    assert result["note_count"] == 1
    assert result["mode"] == "delta"
    assert result["capture_appended"] is True
    assert result["poll_id"] == result["capture_id"]
    checkpoint = json.loads(
        (config.state_dir / "mcp/granola_rest_delta.json").read_text()
    )
    assert checkpoint["last_successful_provider_updated_at"] == "2026-09-07T10:02:00Z"
    assert checkpoint["overlap_seconds"] == 300
    assert checkpoint["raw_capture_path"].endswith(".json")


def test_delta_skips_local_stages_for_overlap_only_notes(tmp_path: Path):
    _seed_archive(tmp_path, "2026-09-07T10:00:00Z")
    config = load_config(tmp_path)
    client = FakeClient(
        [
            {
                "id": "unchanged-note",
                "title": "Unchanged note",
                "updated_at": "2026-09-07T10:00:00.186Z",
                "summary_text": "Already imported",
                "transcript": [],
            }
        ]
    )
    stages: List[Path] = []

    result = run_delta(
        config,
        client,
        captured_at="2026-09-07T10:05:00Z",
        stage_runner=lambda _config, raw_path: stages.append(raw_path),
    )

    assert result["stages_skipped"] is True
    assert result["capture_appended"] is False
    assert stages == []
    assert list((tmp_path / "data/mcp/granola").glob("granola-api-delta-*.json")) == []
    checkpoint = json.loads(
        (config.state_dir / "mcp/granola_rest_delta.json").read_text()
    )
    assert checkpoint["stage_details"] == {
        "status": "no_provider_changes",
        "stages_skipped": True,
    }
    assert checkpoint["last_successful_capture_id"] is None
    assert checkpoint["last_successful_poll_id"] == result["poll_id"]
    assert checkpoint["raw_capture_path"] is None
    assert checkpoint["raw_boundary"]["raw_capture_appended"] is False


def test_delta_failure_keeps_raw_capture_and_previous_checkpoint(tmp_path: Path):
    _seed_archive(tmp_path, "2026-09-07T10:00:00Z")
    config = load_config(tmp_path)
    state_path = config.state_dir / "mcp/granola_rest_delta.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    previous = {
        "schema_version": 1,
        "last_successful_provider_updated_at": "2026-09-07T10:00:00Z",
    }
    state_path.write_text(json.dumps(previous), encoding="utf-8")
    client = FakeClient([{"id": "changed", "updated_at": "2026-09-07T10:01:00Z"}])

    def fail(_config, _raw_path):
        raise RuntimeError("local stage failed")

    with pytest.raises(RuntimeError, match="local stage failed"):
        run_delta(
            config,
            client,
            captured_at="2026-09-07T10:05:00Z",
            stage_runner=fail,
        )

    assert json.loads(state_path.read_text()) == previous
    raw_files = list((tmp_path / "data/mcp/granola").glob("granola-api-delta-*.json"))
    assert len(raw_files) == 1


def test_delta_allows_explicit_seed_and_empty_result(tmp_path: Path):
    config = load_config(tmp_path)
    client = FakeClient([])

    result = run_delta(
        config,
        client,
        updated_after="2026-09-07T08:00:00Z",
        captured_at="2026-09-07T08:05:00Z",
        stage_runner=lambda _config, _raw_path: None,
    )

    assert result["note_count"] == 0
    assert client.updated_after == ["2026-09-07T07:55:00Z"]
    checkpoint = json.loads(
        (config.state_dir / "mcp/granola_rest_delta.json").read_text()
    )
    assert checkpoint["last_successful_provider_updated_at"] == "2026-09-07T08:00:00Z"


def test_delta_lock_rejects_a_second_writer(tmp_path: Path):
    config = load_config(tmp_path)
    with _single_writer_lock(config):
        with pytest.raises(DeltaAlreadyRunning):
            run_delta(
                config,
                FakeClient([]),
                updated_after="2026-09-07T08:00:00Z",
                captured_at="2026-09-07T08:05:00Z",
                stage_runner=lambda _config, _raw_path: None,
            )


def test_default_local_stages_refresh_index_checkpoint(tmp_path: Path):
    config = load_config(tmp_path)
    result = _run_local_stages(config, tmp_path / "capture.json")

    checkpoint = json.loads(
        (config.state_dir / "index_rebuild.json").read_text(encoding="utf-8")
    )
    assert result["organize"]["index_verification"]["fts_rows"] == checkpoint["fts_rows"]
    assert result["organize"]["index_verification"]["relationship_rows"] == checkpoint[
        "relationship_rows"
    ]
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        assert checkpoint["fts_rows"] == con.execute(
            "SELECT COUNT(*) FROM derived_text_fts"
        ).fetchone()[0]
    finally:
        con.close()
