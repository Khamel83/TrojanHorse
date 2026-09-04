from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

from .config import Config
from .util import (
    detect_kind,
    detect_source_system,
    ensure_dir,
    now_iso,
    parse_date_hint,
    safe_relpath,
    sha256_file,
    stable_source_id,
    write_csv,
)


def _iter_files(root: Path, ignore_names: Set[str], follow_symlinks: bool) -> Iterator[Path]:
    if not root.exists():
        return
    if root.is_file():
        yield root
        return

    visited: Set[Tuple[int, int]] = set()
    for current, dirs, files in os.walk(root, followlinks=follow_symlinks):
        current_path = Path(current)

        try:
            st = current_path.stat()
            key = (st.st_dev, st.st_ino)
            if key in visited:
                dirs[:] = []
                continue
            visited.add(key)
        except OSError:
            pass

        filtered_dirs = []
        for name in dirs:
            if name in ignore_names or name.startswith(".git"):
                continue
            child = current_path / name
            if child.is_symlink() and not follow_symlinks:
                continue
            filtered_dirs.append(name)
        dirs[:] = filtered_dirs

        for name in files:
            if name == ".DS_Store" or name.startswith("._"):
                continue
            path = current_path / name
            if path.is_symlink() and not path.exists():
                continue
            yield path


PERSONAL_PATH_TERMS = {
    "therapy", "divorce", "custody", "medical", "doctor", "dietician",
    "family", "children", "kids", "tax", "fidelity", "relationship",
    "personal", "health record", "court", "attorney",
}

WORK_PATH_TERMS = {
    "usc", "hrec", "work", "project", "strategy", "analytics", "meeting",
    "granola", "wispr", "outlook", "zoom", "performance review",
    "work arrangement", "workforce", "dashboard", "research", "advancement",
}

SENSITIVE_PATH_TERMS = {
    "employee id", "eid", "ssn", "social security", "medical", "therapy",
    "investigation", "legal", "attorney", "privileged", "complaint",
    "protected class", "salary", "compensation", "layoff", "warn", "union",
    "divorce", "custody", "tax", "confidential", "personnel",
}


def _path_classification(relative_path: str) -> str:
    low = relative_path.lower().replace("_", " ").replace("-", " ")
    personal = any(term in low for term in PERSONAL_PATH_TERMS)
    work = any(term in low for term in WORK_PATH_TERMS)
    if personal and work:
        return "mixed_or_review"
    if personal:
        return "potential_personal"
    if work:
        return "likely_work"
    return "unknown"


def _sensitivity(relative_path: str, source_system: str) -> str:
    low = relative_path.lower().replace("_", " ").replace("-", " ")
    if any(term in low for term in SENSITIVE_PATH_TERMS):
        return "potential_restricted"
    if source_system in {"email", "outlook", "granola", "wispr_flow", "zoom"}:
        return "internal_review"
    return "unknown"


def _parse_readiness(kind: str, extension: str) -> str:
    if kind == "media":
        return "transcription_or_existing_transcript"
    if extension in {".one", ".onepkg", ".olm", ".pst", ".ost", ".doc", ".ppt", ".xls"}:
        return "conversion_required"
    if extension in {".pdf", ".docx", ".pptx", ".xlsx"}:
        return "optional_parser"
    if kind == "archive":
        return "archive_inventory_only" if extension == ".zip" else "conversion_required"
    if kind in {"document", "table", "transcript", "transcript_candidate", "structured_text", "email", "email_data", "mcp", "database"}:
        return "direct_or_supported"
    return "unknown"


def _value_flags(source_system: str, kind: str) -> tuple[str, str]:
    if source_system == "formal_records":
        return "high", "medium"
    if source_system in {"granola", "wispr_flow", "email", "outlook", "zoom"}:
        return "medium", "high"
    if source_system in {"notion", "onenote", "capacities", "other"}:
        return "medium", "medium"
    if source_system == "inventory":
        return "none", "low"
    if kind == "media":
        return "indirect", "medium"
    return "unknown", "unknown"


def _source_rows(con: sqlite3.Connection) -> List[Dict[str, object]]:
    query = """
        SELECT source_id, relative_path, absolute_path, source_system, kind,
               extension, size_bytes, mtime_ns, content_sha256, date_hint,
               classification, sensitivity, parse_readiness, career_value,
               operations_value, duplicate_group_id, status, first_seen, last_seen
        FROM source_item
        ORDER BY source_system, relative_path
    """
    return [dict(row) for row in con.execute(query)]


def inventory(config: Config, con: sqlite3.Connection, full_hash: bool = False) -> Dict[str, object]:
    ensure_dir(config.corpus_dir)
    ensure_dir(config.state_dir)

    ignore = set(config.get("inventory", "ignore_directories", []))
    follow_symlinks = bool(config.get("inventory", "follow_directory_symlinks", False))
    hash_limit = int(config.get("inventory", "hash_files_up_to_mb", 32)) * 1024 * 1024

    scan_time = now_iso()
    seen_paths: Set[str] = set()
    counts: Dict[str, int] = {}
    errors: List[str] = []
    total_bytes = 0

    for path in _iter_files(config.data_dir, ignore, follow_symlinks):
        try:
            stat = path.stat()
            if not path.is_file():
                continue
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue

        relative_path = safe_relpath(path, config.root)
        seen_paths.add(relative_path)
        source_system = detect_source_system(relative_path)
        kind = detect_kind(path, source_system)
        extension = path.suffix.lower()
        content_hash = ""

        if full_hash or stat.st_size <= hash_limit:
            try:
                content_hash = sha256_file(path)
            except OSError as exc:
                errors.append(f"hash {path}: {exc}")

        source_id = stable_source_id(relative_path, stat.st_size, stat.st_mtime_ns, content_hash)
        date_hint = parse_date_hint(relative_path)
        classification = _path_classification(relative_path)
        sensitivity = _sensitivity(relative_path, source_system)
        parse_readiness = _parse_readiness(kind, extension)
        career_value, operations_value = _value_flags(source_system, kind)
        metadata = {
            "is_symlink": path.is_symlink(),
            "parent": safe_relpath(path.parent, config.root),
        }

        previous = con.execute(
            "SELECT source_id, first_seen FROM source_item WHERE relative_path = ?",
            (relative_path,),
        ).fetchone()

        if previous and previous["source_id"] != source_id:
            con.execute("DELETE FROM source_item WHERE source_id = ?", (previous["source_id"],))

        first_seen = previous["first_seen"] if previous else scan_time
        con.execute(
            """
            INSERT INTO source_item (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, content_sha256, date_hint,
                classification, sensitivity, parse_readiness, career_value,
                operations_value, duplicate_group_id,
                status, first_seen, last_seen, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'present', ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                source_id = excluded.source_id,
                absolute_path = excluded.absolute_path,
                source_system = excluded.source_system,
                kind = excluded.kind,
                extension = excluded.extension,
                size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns,
                content_sha256 = excluded.content_sha256,
                date_hint = excluded.date_hint,
                classification = excluded.classification,
                sensitivity = excluded.sensitivity,
                parse_readiness = excluded.parse_readiness,
                career_value = excluded.career_value,
                operations_value = excluded.operations_value,
                status = 'present',
                last_seen = excluded.last_seen,
                metadata_json = excluded.metadata_json
            """,
            (
                source_id,
                relative_path,
                str(path.resolve(strict=False)),
                source_system,
                kind,
                extension,
                stat.st_size,
                stat.st_mtime_ns,
                content_hash or None,
                date_hint or None,
                classification,
                sensitivity,
                parse_readiness,
                career_value,
                operations_value,
                first_seen,
                scan_time,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        counts[source_system] = counts.get(source_system, 0) + 1
        total_bytes += stat.st_size

    existing = con.execute("SELECT relative_path FROM source_item").fetchall()
    for row in existing:
        if row["relative_path"] not in seen_paths:
            con.execute(
                "UPDATE source_item SET status = 'missing', last_seen = ? WHERE relative_path = ?",
                (scan_time, row["relative_path"]),
            )

    # Exact duplicate grouping is available for files that were hashed.
    con.execute("UPDATE source_item SET duplicate_group_id=NULL WHERE status='present'")
    duplicate_hashes = con.execute(
        """
        SELECT content_sha256
        FROM source_item
        WHERE status='present' AND content_sha256 IS NOT NULL AND content_sha256<>''
        GROUP BY content_sha256
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    for duplicate in duplicate_hashes:
        digest = duplicate[0]
        con.execute(
            "UPDATE source_item SET duplicate_group_id=? WHERE status='present' AND content_sha256=?",
            ("dup_" + digest[:16], digest),
        )

    con.commit()

    rows = _source_rows(con)
    manifest_path = config.corpus_dir / "source_manifest.csv"
    write_csv(
        manifest_path,
        rows,
        [
            "source_id",
            "relative_path",
            "absolute_path",
            "source_system",
            "kind",
            "extension",
            "size_bytes",
            "mtime_ns",
            "content_sha256",
            "date_hint",
            "classification",
            "sensitivity",
            "parse_readiness",
            "career_value",
            "operations_value",
            "duplicate_group_id",
            "status",
            "first_seen",
            "last_seen",
        ],
    )

    errors_path = config.state_dir / "inventory_errors.txt"
    errors_path.write_text("\n".join(errors) + ("\n" if errors else ""), encoding="utf-8")

    result = {
        "scanned_at": scan_time,
        "data_dir": str(config.data_dir),
        "files_present": len(seen_paths),
        "total_bytes": total_bytes,
        "counts_by_source_system": dict(sorted(counts.items())),
        "errors": len(errors),
        "manifest": str(manifest_path),
    }
    (config.state_dir / "inventory_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result
