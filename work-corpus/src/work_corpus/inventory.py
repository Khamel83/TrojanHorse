from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import posixpath
import re
import sqlite3
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple, TypedDict
import zipfile

from .config import (
    Config,
    DEFAULT_SKIP_CLASSIFICATIONS,
    EXPLICIT_SOURCE_ROOTS,
    SourceRoot,
    SourceRootMatch,
)
from .db import mark_noncurrent_normalized_documents_retained
from .report import write_manifest_reports
from .util import (
    detect_kind,
    ensure_dir,
    now_iso,
    parse_date_hint,
    safe_relpath,
    sha256_file,
    stable_source_id,
    stable_source_version_id,
)


class InventoryResult(TypedDict):
    scanned_at: str
    data_dir: str
    files_present: int
    substantive_files: int
    finder_metadata_files: int
    total_bytes: int
    counts_by_source_system: Dict[str, int]
    counts_by_root_key: Dict[str, int]
    archive_members_listed: int
    zoom_dated_folders: int
    notion_export_files: int
    onenote_files: int
    residual_files: int
    residual_paths: List[str]
    errors: int
    error_messages: List[str]
    manifest: str


@dataclass(frozen=True)
class ScopeProposal:
    scope: str
    reason: str


ARCHIVE_DIRECTORY_KEYS = {
    "capacities_archive": "capacities_markdown",
    "notion_archive": "notion_export",
}
FINDER_METADATA_NAMES = {".DS_Store"}
ZOOM_FOLDER_PATTERN = re.compile(r"^data/Zoom/([^/]+)/")


def _iter_files(
    root: Path,
    ignore_names: Set[str],
    follow_symlinks: bool,
) -> Iterator[Path]:
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
        dirs[:] = sorted(filtered_dirs)

        for name in sorted(files):
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

TRUSTED_WORK_SYSTEMS = {"formal_records", "granola", "wispr_flow", "zoom"}


def _normalise_relative_path(value: str) -> str:
    normalised = posixpath.normpath(value.replace("\\", "/"))
    while normalised.startswith("./"):
        normalised = normalised[2:]
    return "" if normalised == "." else normalised


def _root_matches(relative_path: str, root: SourceRoot) -> bool:
    root_path = _normalise_relative_path(root.relative_path).rstrip("/")
    if not root_path:
        return False
    if root.key == "onenote_backup" and not relative_path.lower().endswith(".one"):
        return False
    if root.key.endswith("_archive"):
        return relative_path == root_path
    return relative_path == root_path or relative_path.startswith(root_path + "/")


def classify_root(
    relative_path: str,
    roots: Sequence[SourceRoot],
) -> SourceRootMatch:
    """Match a path against the reviewed source registry by precedence."""
    normalised = _normalise_relative_path(relative_path)
    candidates = roots.values() if isinstance(roots, dict) else roots
    ordered = sorted(
        (root for root in candidates if root.enabled and _root_matches(normalised, root)),
        key=lambda root: (
            0 if root.key in EXPLICIT_SOURCE_ROOTS else 1,
            root.precedence,
            -len(root.relative_path),
            root.key,
        ),
    )
    if not ordered:
        return SourceRootMatch(root=None, relative_path=normalised, kind="residual")

    root = ordered[0]
    if root.source_system == "inventory_discovery":
        kind = "discovery"
    elif root.key.endswith("_archive"):
        kind = "archive"
    else:
        kind = "source"
    return SourceRootMatch(root=root, relative_path=normalised, kind=kind)


def classify_scope(relative_path: str, source_system: str) -> ScopeProposal:
    """Return a conservative scope proposal for review and later promotion."""
    if source_system == "inventory_discovery":
        return ScopeProposal("Unknown", "Machine-discovery evidence is accounting-only.")

    low = relative_path.lower().replace("_", " ").replace("-", " ")
    personal_hits = sorted(term for term in PERSONAL_PATH_TERMS if term in low)
    work_hits = sorted(term for term in WORK_PATH_TERMS if term in low)
    if personal_hits and work_hits:
        return ScopeProposal(
            "Mixed",
            "Path contains both personal and work indicators: "
            + ", ".join(personal_hits + work_hits),
        )
    if personal_hits:
        return ScopeProposal(
            "Personal",
            "Path contains personal indicators: " + ", ".join(personal_hits),
        )
    if work_hits:
        return ScopeProposal(
            "Work",
            "Path contains work indicators: " + ", ".join(work_hits),
        )
    if source_system in TRUSTED_WORK_SYSTEMS:
        return ScopeProposal("Work", f"The approved {source_system} source is work-scoped.")
    return ScopeProposal("Unknown", "No approved scope indicator was found in the path.")


def _sensitivity(relative_path: str, source_system: str) -> str:
    low = relative_path.lower().replace("_", " ").replace("-", " ")
    if any(term in low for term in SENSITIVE_PATH_TERMS):
        return "potential_restricted"
    if source_system in {"email", "outlook", "granola", "wispr_flow", "zoom"}:
        return "internal_review"
    return "unknown"


def _parse_readiness(kind: str, extension: str) -> str:
    if kind in {"metadata", "discovery"}:
        return "excluded"
    if kind == "media":
        return "transcription_or_existing_transcript"
    if extension in {".one", ".onepkg", ".olm", ".pst", ".ost", ".doc", ".ppt", ".xls"}:
        return "conversion_required"
    if extension in {".pdf", ".docx", ".pptx", ".xlsx"}:
        return "optional_parser"
    if kind == "archive":
        return "archive_inventory_only" if extension == ".zip" else "conversion_required"
    if kind in {
        "document", "table", "transcript", "transcript_candidate",
        "structured_text", "email", "email_data", "mcp", "database",
    }:
        return "direct_or_supported"
    return "unknown"


def _value_flags(source_system: str, kind: str) -> tuple[str, str]:
    if source_system == "formal_records":
        return "high", "medium"
    if source_system in {"granola", "wispr_flow", "email", "outlook", "zoom"}:
        return "medium", "high"
    if source_system in {"notion", "onenote", "capacities", "other"}:
        return "medium", "medium"
    if source_system == "inventory_discovery":
        return "none", "low"
    if kind == "media":
        return "indirect", "medium"
    return "unknown", "unknown"


def _root_by_key(config: Config, key: str) -> Optional[SourceRoot]:
    return next((root for root in config.source_roots if root.key == key), None)


def _archive_metadata(
    config: Config,
    path: Path,
    root: SourceRoot,
    max_entries: int,
) -> Tuple[Dict[str, object], List[Dict[str, object]], Optional[str]]:
    extracted_key = ARCHIVE_DIRECTORY_KEYS.get(root.key)
    extracted_root = _root_by_key(config, extracted_key) if extracted_key else None
    extracted_present = bool(
        extracted_root and (config.root / extracted_root.relative_path).is_dir()
    )
    metadata: Dict[str, object] = {
        "archive_member_count": 0,
        "archive_members_listed": 0,
        "archive_members_truncated": False,
        "archive_matches_extracted_root": extracted_present,
        "archive_extracted_root_key": extracted_key or "",
        "archive_semantic_status": (
            "duplicate_of_extracted" if extracted_present else "archive_only"
        ),
    }
    member_rows: List[Dict[str, object]] = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            metadata["archive_member_count"] = len(infos)
            selected = infos[:max_entries]
            metadata["archive_members_listed"] = len(selected)
            metadata["archive_members_truncated"] = len(selected) < len(infos)
            for info in selected:
                member = {
                    "member_path": info.filename,
                    "size_bytes": info.file_size,
                    "compressed_size_bytes": info.compress_size,
                    "is_directory": info.is_dir(),
                    "encrypted": bool(info.flag_bits & 0x1),
                }
                member_rows.append(member)
            metadata["archive_members"] = member_rows
    except (OSError, zipfile.BadZipFile) as exc:
        return metadata, member_rows, f"archive listing {path}: {exc}"
    return metadata, member_rows, None


def _extraction_status(
    kind: str,
    content_hash: str,
    archive_matches_extracted_root: bool,
) -> str:
    if kind in {"metadata", "discovery"} or archive_matches_extracted_root:
        return "excluded"
    if kind == "archive":
        return "archive_only_inventory" if content_hash else "inventory_only"
    return "ready" if content_hash else "inventory_only"


def _source_rows(con: sqlite3.Connection) -> List[Dict[str, object]]:
    query = """
        SELECT source_id, source_version_id, relative_path, absolute_path,
               source_system, kind, extension, size_bytes, mtime_ns,
               content_sha256, date_hint, classification, sensitivity,
               parse_readiness, extraction_status, career_value,
               operations_value, duplicate_group_id, status, first_seen,
               last_seen, metadata_json
        FROM source_item
        ORDER BY source_system, relative_path
    """
    output: List[Dict[str, object]] = []
    for row in con.execute(query):
        item = dict(row)
        try:
            metadata = json.loads(item.get("metadata_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            metadata = {}
        item.update(
            {
                "source_root_key": metadata.get("source_root_key", "residual"),
                "root_match_kind": metadata.get("root_match_kind", "residual"),
                "source_version_id": item.get("source_version_id")
                or metadata.get("source_version_id"),
                "scope_proposal": metadata.get(
                    "scope_proposal", item.get("classification") or "Unknown"
                ),
                "scope_reason": metadata.get("scope_reason", ""),
                "extraction_status": item.get("extraction_status")
                or metadata.get("extraction_status", "inventory_only"),
                "archive_member_count": metadata.get("archive_member_count", 0),
                "archive_members": metadata.get("archive_members", []),
                "archive_semantic_status": metadata.get("archive_semantic_status", ""),
                "archive_extracted_root_key": metadata.get(
                    "archive_extracted_root_key", ""
                ),
            }
        )
        output.append(item)
    return output


def _is_finder_metadata(path: Path) -> bool:
    return path.name in FINDER_METADATA_NAMES or path.name.startswith("._")


def _rekey_legacy_source(
    con: sqlite3.Connection,
    old_source_id: str,
    new_source_id: str,
) -> None:
    """Move bootstrap-era history to the canonical source identity."""
    if old_source_id == new_source_id:
        return

    versions = con.execute(
        """
        SELECT *
        FROM source_version
        WHERE source_id=?
        ORDER BY first_seen, source_version_id
        """,
        (old_source_id,),
    ).fetchall()
    for version in versions:
        canonical_version_id = stable_source_version_id(
            new_source_id,
            version["content_sha256"],
        )
        if canonical_version_id is None:
            continue
        con.execute(
            """
            INSERT INTO source_version (
                source_version_id, source_id, content_sha256, size_bytes,
                mtime_ns, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_version_id) DO UPDATE SET
                size_bytes=excluded.size_bytes,
                mtime_ns=excluded.mtime_ns,
                last_seen=excluded.last_seen
            """,
            (
                canonical_version_id,
                new_source_id,
                version["content_sha256"],
                version["size_bytes"],
                version["mtime_ns"],
                version["first_seen"],
                version["last_seen"],
            ),
        )

        normalized = con.execute(
            "SELECT * FROM normalized_document WHERE source_version_id=?",
            (version["source_version_id"],),
        ).fetchone()
        if normalized:
            target = con.execute(
                "SELECT 1 FROM normalized_document WHERE source_version_id=?",
                (canonical_version_id,),
            ).fetchone()
            if target is None:
                con.execute(
                    """
                    INSERT INTO normalized_document (
                        source_version_id, source_id, normalized_path, parser,
                        source_mtime_ns, char_count, line_count, content_sha256,
                        status, error, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_version_id,
                        new_source_id,
                        normalized["normalized_path"],
                        normalized["parser"],
                        normalized["source_mtime_ns"],
                        normalized["char_count"],
                        normalized["line_count"],
                        normalized["content_sha256"],
                        normalized["status"],
                        normalized["error"],
                        normalized["updated_at"],
                    ),
                )
            con.execute(
                "DELETE FROM normalized_document WHERE source_version_id=?",
                (version["source_version_id"],),
            )
        con.execute(
            "DELETE FROM source_version WHERE source_version_id=?",
            (version["source_version_id"],),
        )

    canonical_source = con.execute(
        "SELECT 1 FROM source_item WHERE source_id=?",
        (new_source_id,),
    ).fetchone()
    if not canonical_source:
        old_source = con.execute(
            "SELECT * FROM source_item WHERE source_id=?",
            (old_source_id,),
        ).fetchone()
        if old_source is not None:
            temporary_path = f"__legacy_rekey__/{old_source_id}"
            con.execute(
                "UPDATE source_item SET relative_path=? WHERE source_id=?",
                (temporary_path, old_source_id),
            )
            con.execute(
                """
                INSERT INTO source_item (
                    source_id, relative_path, absolute_path, source_system,
                    kind, extension, size_bytes, mtime_ns, content_sha256,
                    source_version_id, date_hint, classification, sensitivity,
                    parse_readiness, extraction_status, career_value,
                    operations_value, duplicate_group_id, status, first_seen,
                    last_seen, metadata_json
                )
                SELECT ?, ?, absolute_path, source_system, kind, extension,
                       size_bytes, mtime_ns, content_sha256, source_version_id,
                       date_hint, classification, sensitivity, parse_readiness,
                       extraction_status, career_value, operations_value,
                       duplicate_group_id, status, first_seen, last_seen,
                       metadata_json
                FROM source_item
                WHERE source_id=?
                """,
                (new_source_id, old_source["relative_path"], old_source_id),
            )

    # Keep existing relationship rows valid if a bootstrap database contained
    # Zoom state when the source identity changes. The canonical parent exists
    # before these foreign-key updates.
    con.execute(
        "UPDATE zoom_group SET media_source_id=? WHERE media_source_id=?",
        (new_source_id, old_source_id),
    )
    con.execute(
        "UPDATE zoom_group SET transcript_source_id=? WHERE transcript_source_id=?",
        (new_source_id, old_source_id),
    )
    con.execute(
        "UPDATE transcription_job SET media_source_id=? WHERE media_source_id=?",
        (new_source_id, old_source_id),
    )
    con.execute(
        "UPDATE normalized_document SET source_id=? WHERE source_id=?",
        (new_source_id, old_source_id),
    )
    legacy_table = con.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name='normalized_document_legacy'
        """
    ).fetchone()
    if legacy_table:
        con.execute(
            "UPDATE normalized_document_legacy SET source_id=? WHERE source_id=?",
            (new_source_id, old_source_id),
        )

    if canonical_source:
        con.execute("DELETE FROM source_item WHERE source_id=?", (old_source_id,))
    else:
        con.execute("DELETE FROM source_item WHERE source_id=?", (old_source_id,))


def inventory(
    config: Config,
    con: sqlite3.Connection,
    *,
    full_hash: bool = False,
) -> InventoryResult:
    ensure_dir(config.corpus_dir)
    ensure_dir(config.state_dir)

    ignore = set(config.get("inventory", "ignore_directories", []))
    follow_symlinks = bool(config.get("inventory", "follow_directory_symlinks", False))
    hash_limit = int(config.get("inventory", "hash_files_up_to_mb", 32)) * 1024 * 1024
    max_archive_entries = int(
        config.get("inventory", "max_archive_entries_to_list", 100000)
    )

    scan_time = now_iso()
    seen_paths: Set[str] = set()
    counts: Dict[str, int] = {}
    root_counts: Dict[str, int] = {}
    errors: List[str] = []
    total_bytes = 0
    finder_metadata_files = 0
    archive_members_listed = 0
    zoom_folders: Set[str] = set()
    residual_paths: List[str] = []

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
        match = classify_root(relative_path, config.source_roots)
        source_root_key = match.root.key if match.root else "residual"
        source_system = match.root.source_system if match.root else "unclassified"
        extension = path.suffix.lower()
        if _is_finder_metadata(path):
            kind = "metadata"
            finder_metadata_files += 1
        elif match.kind == "discovery":
            kind = "discovery"
        else:
            kind = detect_kind(path, source_system)

        content_hash = ""
        if full_hash or stat.st_size <= hash_limit:
            try:
                content_hash = sha256_file(path)
            except OSError as exc:
                errors.append(f"hash {path}: {exc}")

        source_id = stable_source_id(source_root_key, relative_path)
        source_version_id = stable_source_version_id(source_id, content_hash)
        scope = classify_scope(relative_path, source_system)
        archive_metadata: Dict[str, object] = {}
        archive_error: Optional[str] = None
        archive_member_rows: List[Dict[str, object]] = []
        if match.root and match.kind == "archive":
            archive_metadata, archive_member_rows, archive_error = _archive_metadata(
                config,
                path,
                match.root,
                max_archive_entries,
            )
            if archive_error:
                errors.append(archive_error)
            archive_members_listed += len(archive_member_rows)

        extraction_status = _extraction_status(
            kind,
            content_hash,
            bool(archive_metadata.get("archive_matches_extracted_root")),
        )
        parse_readiness = (
            "excluded"
            if extraction_status == "excluded"
            else _parse_readiness(kind, extension)
        )
        if match.root is None:
            residual_paths.append(relative_path)
        if match.root:
            root_counts[source_root_key] = root_counts.get(source_root_key, 0) + 1
        counts[source_system] = counts.get(source_system, 0) + 1
        zoom_match = ZOOM_FOLDER_PATTERN.match(relative_path)
        if zoom_match and parse_date_hint(zoom_match.group(1)):
            zoom_folders.add(zoom_match.group(1))

        metadata: Dict[str, object] = {
            "is_symlink": path.is_symlink(),
            "parent": safe_relpath(path.parent, config.root),
            "source_root_key": source_root_key,
            "root_match_kind": match.kind,
            "source_relative_path": (
                relative_path[len(match.root.relative_path):].lstrip("/")
                if match.root and relative_path.startswith(match.root.relative_path)
                else relative_path
            ),
            "source_version_id": source_version_id,
            "scope_proposal": scope.scope,
            "scope_reason": scope.reason,
            "extraction_status": extraction_status,
            **archive_metadata,
        }

        previous = con.execute(
            "SELECT source_id, first_seen FROM source_item WHERE relative_path = ?",
            (relative_path,),
        ).fetchone()
        if previous and previous["source_id"] != source_id:
            _rekey_legacy_source(con, previous["source_id"], source_id)
        first_seen = previous["first_seen"] if previous else scan_time
        con.execute(
            """
            INSERT INTO source_item (
                source_id, relative_path, absolute_path, source_system, kind,
                extension, size_bytes, mtime_ns, content_sha256,
                source_version_id, date_hint, classification, sensitivity,
                parse_readiness, extraction_status, career_value,
                operations_value, duplicate_group_id,
                status, first_seen, last_seen, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL,
                    'present', ?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                source_id = excluded.source_id,
                absolute_path = excluded.absolute_path,
                source_system = excluded.source_system,
                kind = excluded.kind,
                extension = excluded.extension,
                size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns,
                content_sha256 = excluded.content_sha256,
                source_version_id = excluded.source_version_id,
                date_hint = excluded.date_hint,
                classification = excluded.classification,
                sensitivity = excluded.sensitivity,
                parse_readiness = excluded.parse_readiness,
                extraction_status = excluded.extraction_status,
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
                source_version_id,
                parse_date_hint(relative_path) or None,
                scope.scope,
                _sensitivity(relative_path, source_system),
                parse_readiness,
                extraction_status,
                _value_flags(source_system, kind)[0],
                _value_flags(source_system, kind)[1],
                first_seen,
                scan_time,
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        if source_version_id:
            con.execute(
                """
                INSERT INTO source_version (
                    source_version_id, source_id, content_sha256, size_bytes,
                    mtime_ns, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_version_id) DO UPDATE SET
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    last_seen=excluded.last_seen
                """,
                (
                    source_version_id,
                    source_id,
                    content_hash,
                    stat.st_size,
                    stat.st_mtime_ns,
                    scan_time,
                    scan_time,
                ),
            )
        total_bytes += stat.st_size

    existing = con.execute("SELECT relative_path FROM source_item").fetchall()
    for row in existing:
        if row["relative_path"] not in seen_paths:
            con.execute(
                "UPDATE source_item SET status = 'missing', last_seen = ? WHERE relative_path = ?",
                (scan_time, row["relative_path"]),
            )

    mark_noncurrent_normalized_documents_retained(
        con,
        scan_time,
        skip_classifications=config.get(
            "normalization",
            "skip_classifications",
            list(DEFAULT_SKIP_CLASSIFICATIONS),
        ),
    )

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
    manifest_path = write_manifest_reports(config, rows)

    errors_path = config.state_dir / "inventory_errors.txt"
    errors_path.write_text(
        "\n".join(errors) + ("\n" if errors else ""),
        encoding="utf-8",
    )
    residual_paths.sort()
    result: InventoryResult = {
        "scanned_at": scan_time,
        "data_dir": str(config.data_dir),
        "files_present": len(seen_paths),
        "substantive_files": len(seen_paths) - finder_metadata_files,
        "finder_metadata_files": finder_metadata_files,
        "total_bytes": total_bytes,
        "counts_by_source_system": dict(sorted(counts.items())),
        "counts_by_root_key": dict(sorted(root_counts.items())),
        "archive_members_listed": archive_members_listed,
        "zoom_dated_folders": len(zoom_folders),
        "notion_export_files": root_counts.get("notion_export", 0),
        "onenote_files": root_counts.get("onenote_backup", 0),
        "residual_files": len(residual_paths),
        "residual_paths": residual_paths,
        "errors": len(errors),
        "error_messages": errors,
        "manifest": str(manifest_path),
    }
    (config.state_dir / "inventory_summary.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return result
