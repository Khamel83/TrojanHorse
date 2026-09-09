from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
import time
import traceback
from typing import Any, Dict, Optional

from .answering import (
    DEFAULT_ANSWER_TIMEOUT_SECONDS,
    DEFAULT_GATEWAY_HELPER,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    GatewaySensitiveBackend,
    OllamaBackend,
    answer as answer_question,
)
from .config import Config, load_config
from .db import connect, recover_stale_runs
from .doctor import doctor
from .granola_delta import run_delta
from .granola_progress import write_granola_progress
from .inventory import inventory
from .mcp_ingest import ingest_mcp_sources
from .normalize import normalize_all
from .organization import organize_all
from .query import rebuild_search_index, search
from .raw_verify import verify_raw_immutability
from .report import build_report
from .transcription import transcribe_jobs
from .util import atomic_write_json, ensure_dir, now_iso, stable_id
from .views import build_views
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
    recover_stale_runs(con)
    run_id = stable_id("run", command, now_iso(), str(time.time_ns()))
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


def _record_index_checkpoint(config: Config, con) -> Dict[str, Any]:
    """Scrub existing FTS rows and record the current derived index counts."""
    scrubbed_rows = rebuild_search_index(con)
    state = {
        "fts_rows": int(con.execute("SELECT COUNT(*) FROM derived_text_fts").fetchone()[0]),
        "relationship_rows": int(con.execute("SELECT COUNT(*) FROM relationship").fetchone()[0]),
        "scrubbed_rows": int(scrubbed_rows),
        "verified_at": now_iso(),
        "fts_api": "work_corpus.query.rebuild_search_index",
        "relationship_api": "work_corpus.entities (no corpus-wide relationship rebuild requested)",
    }
    path = config.state_dir / "index_rebuild.json"
    config.assert_derived_path(path)
    atomic_write_json(path, state)
    return state


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

    details["organization"] = organize_all(config, con)
    details["views"] = build_views(config, con)
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
    tx.add_argument(
        "--retry-blocked",
        action="store_true",
        help="Requeue jobs blocked because no local engine was discovered.",
    )
    tx.add_argument(
        "--approve-run",
        action="store_true",
        help="Approve the complete pending local transcription run.",
    )

    sub.add_parser("report", help="Rebuild status reports from SQLite state.")
    sub.add_parser("views", help="Rebuild source-backed project, task, and career views.")
    query = sub.add_parser("query", help="Query local work evidence.")
    query.add_argument("question", nargs="+", help="Question or exact search text.")
    query.add_argument("--limit", type=int, default=20)
    query.add_argument(
        "--scope",
        choices=("All", "Work"),
        default="All",
        help="Search the unified corpus (All) or narrow results to Work.",
    )
    query.add_argument(
        "--no-raw-fallback",
        action="store_true",
        help="Do not inspect raw source files after canonical search misses.",
    )
    query.add_argument(
        "--diagnostic",
        action="store_true",
        help="Inspect excluded scopes locally and label them excluded_scope.",
    )

    answer_parser = sub.add_parser(
        "answer",
        help="Answer one question from the local corpus without maintenance writes.",
    )
    answer_parser.add_argument("question", nargs="+", help="Question to answer.")
    answer_parser.add_argument(
        "--backend",
        choices=("evidence", "ollama", "g2k-sensitive"),
        default="evidence",
    )
    answer_parser.add_argument(
        "--allow-sensitive-remote",
        action="store_true",
        help="Authorize the g2k-sensitive backend for this request.",
    )
    answer_parser.add_argument("--model", "--ollama-model", dest="model", default=DEFAULT_OLLAMA_MODEL)
    answer_parser.add_argument(
        "--ollama-url",
        "--ollama-base-url",
        "--base-url",
        dest="ollama_url",
        default=DEFAULT_OLLAMA_URL,
        help="Loopback Ollama URL.",
    )
    answer_parser.add_argument(
        "--timeout",
        "--timeout-seconds",
        dest="timeout",
        type=float,
        default=DEFAULT_ANSWER_TIMEOUT_SECONDS,
    )
    answer_parser.add_argument("--limit", type=int, default=8)
    answer_parser.add_argument(
        "--scope",
        choices=("All", "Work"),
        default="All",
    )
    answer_parser.add_argument(
        "--gateway-helper",
        type=Path,
        default=Path(DEFAULT_GATEWAY_HELPER),
        help="Sourced Gateway2000 shell helper path.",
    )

    compare_parser = sub.add_parser(
        "answer-compare",
        help="Compare local evidence with the explicitly authorized sensitive route.",
    )
    compare_parser.add_argument("question", nargs="+", help="Question to compare.")
    compare_parser.add_argument(
        "--allow-sensitive-remote",
        action="store_true",
        help="Required authorization for the g2k-sensitive route.",
    )
    compare_parser.add_argument("--model", "--ollama-model", dest="model", default=DEFAULT_OLLAMA_MODEL)
    compare_parser.add_argument(
        "--ollama-url",
        "--ollama-base-url",
        "--base-url",
        dest="ollama_url",
        default=DEFAULT_OLLAMA_URL,
    )
    compare_parser.add_argument(
        "--timeout",
        "--timeout-seconds",
        dest="timeout",
        type=float,
        default=DEFAULT_ANSWER_TIMEOUT_SECONDS,
    )
    compare_parser.add_argument("--limit", type=int, default=8)
    compare_parser.add_argument(
        "--scope",
        choices=("All", "Work"),
        default="All",
    )
    compare_parser.add_argument(
        "--gateway-helper",
        type=Path,
        default=Path(DEFAULT_GATEWAY_HELPER),
    )
    sub.add_parser("mcp-import", help="Import Granola/Wispr Flow dumps.")
    sub.add_parser(
        "granola-progress",
        help="Reconcile exact Granola capture, import, and search progress.",
    )
    granola_delta = sub.add_parser(
        "granola-delta",
        help="Fetch one bounded Granola REST delta and run local maintenance.",
    )
    granola_delta.add_argument(
        "--updated-after",
        default=None,
        help="Explicit ISO-8601 seed for the first bounded run.",
    )
    granola_delta.add_argument("--overlap-seconds", type=int, default=None)
    organize = sub.add_parser(
        "organize",
        help="Build deterministic derived entities, links, task proposals, and residuals.",
    )
    organize.add_argument(
        "--run-date",
        default="",
        help="ISO date used for current-task eligibility (defaults to today).",
    )
    organize.add_argument(
        "--first-pass",
        action="store_true",
        help="Apply safe defaults and write a small exception response sheet.",
    )
    sub.add_parser("doctor", help="Run safe local runtime and SQLite diagnostics.")
    sub.add_parser(
        "raw-verify",
        help="Hash the raw tree twice and verify it did not change between scans.",
    )
    return parser


def _completion_backend_for_args(args: Any) -> Optional[Any]:
    if args.backend == "evidence":
        return None
    if args.backend == "ollama":
        return OllamaBackend(args.model, args.ollama_url, args.timeout)
    return GatewaySensitiveBackend(args.gateway_helper.expanduser(), args.timeout)


def _run_read_only_answer(args: Any, root: Path) -> int:
    """Run answer commands without bootstrap, pipeline rows, or DB writes."""
    con = None
    try:
        if args.command == "answer" and (
            args.backend == "g2k-sensitive" and not args.allow_sensitive_remote
        ):
            raise ValueError(
                "g2k-sensitive backend requires --allow-sensitive-remote"
            )
        if args.command == "answer-compare" and not args.allow_sensitive_remote:
            raise ValueError("answer-compare requires --allow-sensitive-remote")
        config = load_config(root)
        con = connect(
            config.state_dir / "work_corpus.sqlite",
            read_only=True,
        )
        question = " ".join(args.question)
        if args.command == "answer":
            result = answer_question(
                con,
                question,
                backend=args.backend,
                scope=args.scope,
                limit=args.limit,
                completion_backend=_completion_backend_for_args(args),
                allow_sensitive_remote=args.allow_sensitive_remote,
            )
        else:
            local = answer_question(
                con,
                question,
                backend="evidence",
                scope=args.scope,
                limit=args.limit,
            )
            remote = answer_question(
                con,
                question,
                backend="g2k-sensitive",
                scope=args.scope,
                limit=args.limit,
                completion_backend=GatewaySensitiveBackend(
                    args.gateway_helper.expanduser(),
                    args.timeout,
                ),
                allow_sensitive_remote=True,
            )
            result = {
                "question": question,
                "status": "compared",
                "answer_kind": "comparison",
                "local": local,
                "remote": remote,
                "packet_sha256": remote.get("packet_sha256"),
                "warnings": list(
                    dict.fromkeys(
                        [*local.get("warnings", []), *remote.get("warnings", [])]
                    )
                ),
            }
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        if con is not None:
            con.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if args.command in {"answer", "answer-compare"}:
        return _run_read_only_answer(args, root)
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
                retry_blocked=args.retry_blocked,
                approve_run=args.approve_run,
            )
            scan_zoom(config, con)
            details["report"] = build_report(config, con)
        elif args.command == "report":
            details = build_report(config, con)
        elif args.command == "query":
            details = search(
                con,
                " ".join(args.question),
                scope=args.scope,
                limit=args.limit,
                raw_fallback=not args.no_raw_fallback,
                diagnostic=args.diagnostic,
            )
        elif args.command == "mcp-import":
            details = ingest_mcp_sources(config, con)
        elif args.command == "granola-progress":
            details = write_granola_progress(config, con)
            details["index_verification"] = _record_index_checkpoint(config, con)
        elif args.command == "granola-delta":
            details = run_delta(
                config,
                updated_after=args.updated_after,
                overlap_seconds=args.overlap_seconds,
            )
        elif args.command == "organize":
            run_date = date.fromisoformat(args.run_date) if args.run_date else None
            details = organize_all(
                config,
                con,
                run_date=run_date,
                first_pass=args.first_pass,
            )
            details["index_verification"] = _record_index_checkpoint(config, con)
            details["views"] = build_views(config, con)
            details["report"] = build_report(config, con)
        elif args.command == "views":
            details = build_views(config, con)
        elif args.command == "doctor":
            doctor(config, con, exclude_run_id=run_id)
            details = {
                "doctor_json": str(config.state_dir / "doctor.json"),
                "doctor_text": str(config.state_dir / "doctor.txt"),
            }
        elif args.command == "raw-verify":
            details = verify_raw_immutability(config)
        else:
            parser.error(f"unknown command: {args.command}")

        _record_end(con, run_id, "complete", details)
        print(json.dumps(details, indent=2, ensure_ascii=False, default=str))
        if args.command in {"report", "transcribe", "organize", "views"}:
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
