"""Two-pass verification that raw files do not change during a local run."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Dict, Mapping

from .config import Config
from .inventory import _iter_files
from .util import (
    atomic_write_json,
    ensure_dir,
    now_iso,
    safe_relpath,
    sha256_file,
)


Snapshot = Dict[str, Dict[str, Any]]
SnapshotReader = Callable[[Config], Snapshot]


def raw_snapshot(config: Config) -> Snapshot:
    """Hash every readable raw file without writing to the raw tree."""
    ignore_names = set(config.get("inventory", "ignore_directories", []))
    follow_symlinks = bool(
        config.get("inventory", "follow_directory_symlinks", False)
    )
    snapshot: Snapshot = {}
    for path in _iter_files(config.data_dir, ignore_names, follow_symlinks):
        try:
            stat = path.stat()
            digest = sha256_file(path)
        except OSError as exc:
            raise RuntimeError(
                f"raw verification could not read {path}: {exc}"
            ) from exc
        snapshot[safe_relpath(path, config.root)] = {
            "size_bytes": int(stat.st_size),
            "sha256": digest,
        }
    return dict(sorted(snapshot.items()))


def _stream_hash(snapshot: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for path in sorted(snapshot):
        row = snapshot[path]
        digest.update(
            json.dumps(
                [path, row.get("size_bytes", 0), row.get("sha256", "")],
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def compare_snapshots(
    before: Mapping[str, Mapping[str, Any]],
    after: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    before_paths = set(before)
    after_paths = set(after)
    changed = sorted(
        path
        for path in before_paths & after_paths
        if (
            before[path].get("size_bytes") != after[path].get("size_bytes")
            or before[path].get("sha256") != after[path].get("sha256")
        )
    )
    added = sorted(after_paths - before_paths)
    removed = sorted(before_paths - after_paths)
    return {
        "status": "passed" if not (changed or added or removed) else "changed",
        "added_paths": added,
        "removed_paths": removed,
        "changed_paths": changed,
        "before_files": len(before),
        "after_files": len(after),
        "before_bytes": sum(
            int(row.get("size_bytes", 0) or 0) for row in before.values()
        ),
        "after_bytes": sum(
            int(row.get("size_bytes", 0) or 0) for row in after.values()
        ),
        "before_stream_sha256": _stream_hash(before),
        "after_stream_sha256": _stream_hash(after),
        "verified_at": now_iso(),
        "comparison_scope": "current_inventory_counts",
    }


def verify_raw_immutability(
    config: Config,
    *,
    snapshot_reader: SnapshotReader = raw_snapshot,
) -> Dict[str, Any]:
    """Take two raw snapshots and persist only the comparison result."""
    before = snapshot_reader(config)
    after = snapshot_reader(config)
    result = compare_snapshots(before, after)
    path = config.state_dir / "raw_immutability.json"
    config.assert_derived_path(path)
    ensure_dir(path.parent)
    atomic_write_json(path, result)
    return result
