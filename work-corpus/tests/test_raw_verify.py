from __future__ import annotations

from pathlib import Path

from work_corpus.config import load_config
from work_corpus.raw_verify import compare_snapshots, raw_snapshot, verify_raw_immutability


def test_raw_snapshot_records_relative_path_size_and_hash(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "note.md").write_text("hello\n", encoding="utf-8")
    config = load_config(tmp_path)

    snapshot = raw_snapshot(config)

    assert snapshot == {
        "data/note.md": {
            "size_bytes": 6,
            "sha256": "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03",
        }
    }


def test_compare_snapshots_detects_changed_added_and_removed_files():
    before = {
        "data/old.txt": {"size_bytes": 1, "sha256": "a"},
        "data/changed.txt": {"size_bytes": 1, "sha256": "b"},
    }
    after = {
        "data/changed.txt": {"size_bytes": 2, "sha256": "c"},
        "data/new.txt": {"size_bytes": 1, "sha256": "d"},
    }

    result = compare_snapshots(before, after)

    assert result["status"] == "changed"
    assert result["removed_paths"] == ["data/old.txt"]
    assert result["added_paths"] == ["data/new.txt"]
    assert result["changed_paths"] == ["data/changed.txt"]


def test_verify_raw_immutability_persists_passed_state(tmp_path: Path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "note.md").write_text("hello\n", encoding="utf-8")
    config = load_config(tmp_path)

    result = verify_raw_immutability(config)

    assert result["status"] == "passed"
    assert result["comparison_scope"] == "current_inventory_counts"
    assert result["before_files"] == result["after_files"] == 1
    assert (config.state_dir / "raw_immutability.json").exists()
