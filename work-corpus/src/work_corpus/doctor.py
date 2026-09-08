"""Safe local diagnostics for the supported work-corpus runtime."""

from __future__ import annotations

import importlib.util
import sqlite3
from typing import Any, Dict, List, Optional

from .config import Config
from .db import connect, recover_stale_runs
from .util import atomic_write_json, atomic_write_text, executable, now_iso


def _sqlite_summary(con: sqlite3.Connection) -> Dict[str, Any]:
    quick_check = str(con.execute("PRAGMA quick_check").fetchone()[0])
    violations = con.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "quick_check": quick_check,
        "foreign_key_violations": len(violations),
        "source_records": int(
            con.execute("SELECT COUNT(*) FROM source_record").fetchone()[0]
        ),
        "evidence_records": int(
            con.execute("SELECT COUNT(*) FROM evidence_record").fetchone()[0]
        ),
        "fts_rows": int(
            con.execute("SELECT COUNT(*) FROM derived_text_fts").fetchone()[0]
        ),
    }


def _legacy_summary(config: Config) -> Dict[str, Any]:
    paths = {
        "root_package": config.root / "TrojanHorse",
        "bridge": config.root / "bridge",
        "legacy_systemd": config.root / "systemd",
    }
    present = [name for name, path in paths.items() if path.exists()]
    return {
        "status": "quarantined" if present else "absent",
        "present_paths": present,
        "supported_runtime": "work-corpus",
    }


def doctor(
    config: Config,
    con: Optional[sqlite3.Connection] = None,
    *,
    exclude_run_id: Optional[str] = None,
) -> str:
    """Write a local runtime report without network or provider calls."""
    owned_connection = con is None
    if con is None:
        con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        recovered = recover_stale_runs(con)
        sqlite_summary = _sqlite_summary(con)
        running_sql = "SELECT COUNT(*) FROM pipeline_run WHERE status='running'"
        running_parameters: tuple[str, ...] = ()
        if exclude_run_id:
            running_sql += " AND run_id<>?"
            running_parameters = (exclude_run_id,)
        running_rows = int(con.execute(running_sql, running_parameters).fetchone()[0])
        summary: Dict[str, Any] = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "project_root": str(config.root),
            "supported_runtime": "work-corpus",
            "paths": {
                key: {"path": str(path), "exists": path.exists()}
                for key, path in (
                    ("data", config.data_dir),
                    ("corpus", config.corpus_dir),
                    ("state", config.state_dir),
                )
            },
            "sqlite": sqlite_summary,
            "pipeline": {
                "stale_runs_recovered": recovered,
                "running_rows_after_recovery": running_rows,
            },
            "legacy_runtime": _legacy_summary(config),
            "optional_modules": {
                name: bool(importlib.util.find_spec(name))
                for name in ("pypdf", "docx", "pptx", "openpyxl")
            },
            "commands": {
                name: executable(name) or ""
                for name in ("ffmpeg", "ffprobe", "whisper-cli", "whisper")
            },
            "raw_boundary": {
                "raw_data_modified": False,
                "network_calls": 0,
                "provider_writes": 0,
            },
        }
        lines: List[str] = [
            "WORK CORPUS DOCTOR",
            "=" * 72,
            f"Generated: {summary['generated_at']}",
            f"Project root: {config.root}",
            "Supported runtime: work-corpus",
            "",
            "PATHS",
            "-" * 72,
        ]
        for key, value in summary["paths"].items():
            lines.append(f"{key}: {value['path']} (exists={value['exists']})")
        lines.extend(
            [
                "",
                "SQLITE",
                "-" * 72,
                f"quick_check: {sqlite_summary['quick_check']}",
                f"foreign_key_violations: {sqlite_summary['foreign_key_violations']}",
                f"source_records: {sqlite_summary['source_records']}",
                f"evidence_records: {sqlite_summary['evidence_records']}",
                f"fts_rows: {sqlite_summary['fts_rows']}",
                "",
                "PIPELINE",
                "-" * 72,
                f"stale_runs_recovered: {recovered}",
                f"running_rows_after_recovery: {running_rows}",
                "",
                "LEGACY RUNTIME",
                "-" * 72,
                "status: quarantined",
                "The root TrojanHorse/Atlas bridge is historical and is not supported.",
                "",
                "SECURITY",
                "-" * 72,
                "Core pipeline reads files under data/ and writes only to corpus/ and state/.",
                "This doctor performs no network calls, provider writes, or mailbox access.",
            ]
        )
        text = "\n".join(lines) + "\n"
        atomic_write_json(config.state_dir / "doctor.json", summary)
        atomic_write_text(config.state_dir / "doctor.txt", text)
        return text
    finally:
        if owned_connection:
            con.close()
