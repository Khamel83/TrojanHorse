from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import traceback
from typing import Any, Dict, Optional

from .config import Config, load_config
from .db import connect
from .inventory import inventory
from .mcp_ingest import ingest_mcp_sources
from .normalize import normalize_all
from .query import search
from .report import build_report
from .transcription import transcribe_jobs
from .util import ensure_dir, now_iso, stable_id
from .zoom import scan_zoom


CORPUS_SUBDIRS = [
    "normalized",
    "transcripts/zoom/existing",
    "transcripts/zoom/generated",
    "mcp/granola",
    "mcp/wispr_flow",
    "reports",
]
STATE_SUBDIRS = ["tmp", "mcp"]


def bootstrap(config: Config) -> None:
    ensure_dir(config.corpus_dir)
    ensure_dir(config.state_dir)
    for rel in CORPUS_SUBDIRS:
        ensure_dir(config.corpus_dir / rel)
    for rel in STATE_SUBDIRS:
        ensure_dir(config.state_dir / rel)


def _record_start(con, command: str) -> str:
    run_id = stable_id("run", command, now_iso())
    con.execute(
        "INSERT INTO pipeline_run (run_id, command, started_at, status) VALUES (?, ?, ?, 'running')",
        (run_id, command, now_iso()),
    )
    con.commit()
    return run_id


def _record_end(con, run_id: str, status: str, details: Dict[str, Any]) -> None:
    con.execute(
        """
        UPDATE pipeline_run
        SET completed_at=?, status=?, details_json=?
        WHERE run_id=?
        """,
        (now_iso(), status, json.dumps(details, ensure_ascii=False), run_id),
    )
    con.commit()


def run_pipeline(config: Config, con, full_hash: bool = False) -> Dict[str, Any]:
    bootstrap(config)
    details: Dict[str, Any] = {}
    details["inventory"] = inventory(config, con, full_hash=full_hash)
    details["mcp"] = ingest_mcp_sources(config, con)
    details["normalization"] = normalize_all(config, con)
    details["zoom"] = scan_zoom(config, con)

    auto_limit = int(config.get("zoom", "auto_transcribe_max_files", 0))
    if auto_limit > 0:
        details["auto_transcription"] = transcribe_jobs(
            config, con, max_files=auto_limit, all_jobs=False
        )
        details["zoom_after_transcription"] = scan_zoom(config, con)

    details["report"] = build_report(config, con)
    return details


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="work-corpus",
        description="Local-first evidence corpus inventory and normalization.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Existing project root containing data/, corpus/, state/, and work-corpus/.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inv = sub.add_parser("inventory", help="Inventory everything under data/.")
    inv.add_argument("--full-hash", action="store_true", help="SHA-256 all files; expensive for large media.")

    sub.add_parser("normalize", help="Normalize supported text-bearing source files.")
    sub.add_parser("zoom-scan", help="Detect existing Zoom transcripts and queue missing ones.")

    tx = sub.add_parser("transcribe", help="Run local transcription jobs.")
    tx.add_argument(
        "--engine",
        default="",
        choices=("", "auto", "custom", "whisper_cpp", "faster_whisper", "openai_whisper"),
    )
    tx.add_argument("--max-files", type=int, default=None)
    tx.add_argument("--all", action="store_true", help="Process all pending jobs.")
    tx.add_argument("--retry-errors", action="store_true")

    sub.add_parser("report", help="Rebuild status reports from SQLite state.")
    query = sub.add_parser("query", help="Query local work evidence.")
    query.add_argument("question", nargs="+", help="Question or exact search text.")
    query.add_argument("--limit", type=int, default=20)
    query.add_argument(
        "--no-raw-fallback",
        action="store_true",
        help="Do not inspect Work raw files after canonical search misses.",
    )
    query.add_argument(
        "--diagnostic",
        action="store_true",
        help="Inspect excluded scopes locally and label them excluded_scope.",
    )
    sub.add_parser("mcp-import", help="Import Granola/Wispr Flow dumps.")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    config = load_config(root)
    bootstrap(config)
    con = connect(
        config.state_dir / "work_corpus.sqlite",
        skip_classifications=config.get(
            "normalization",
            "skip_classifications",
        ),
    )
    run_id = _record_start(con, args.command)
    details: Dict[str, Any] = {}

    try:
        if args.command == "inventory":
            details = inventory(config, con, full_hash=args.full_hash)
        elif args.command == "normalize":
            details = normalize_all(config, con)
        elif args.command == "zoom-scan":
            details = scan_zoom(config, con)
        elif args.command == "transcribe":
            scan_zoom(config, con)
            details = transcribe_jobs(
                config,
                con,
                requested_engine=args.engine,
                max_files=args.max_files,
                all_jobs=args.all,
                retry_errors=args.retry_errors,
            )
            scan_zoom(config, con)
            details["report"] = build_report(config, con)
        elif args.command == "report":
            details = build_report(config, con)
        elif args.command == "query":
            details = search(
                con,
                " ".join(args.question),
                limit=args.limit,
                raw_fallback=not args.no_raw_fallback,
                diagnostic=args.diagnostic,
            )
        elif args.command == "mcp-import":
            details = ingest_mcp_sources(config, con)
        else:
            parser.error(f"unknown command: {args.command}")

        _record_end(con, run_id, "complete", details)
        print(json.dumps(details, indent=2, ensure_ascii=False, default=str))
        if args.command in {"report", "transcribe"}:
            print(f"\nOpen: {config.corpus_dir / 'reports' / 'status.html'}")
        return 0
    except KeyboardInterrupt:
        _record_end(con, run_id, "cancelled", {"message": "interrupted by user"})
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        details = {"error": f"{type(exc).__name__}: {exc}"}
        _record_end(con, run_id, "error", details)
        print(details["error"], file=sys.stderr)
        if "--debug" in sys.argv:
            traceback.print_exc()
        return 1
    finally:
        con.close()
