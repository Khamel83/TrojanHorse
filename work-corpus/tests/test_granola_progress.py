from __future__ import annotations

import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.cli import _parser, main
from work_corpus.granola_progress import write_granola_progress
from work_corpus.db import connect
from work_corpus.inventory import inventory
from work_corpus.mcp_ingest import ingest_mcp_sources
from work_corpus.report import build_report


def test_cli_exposes_granola_progress_reconciliation():
    args = _parser().parse_args(["granola-progress"])

    assert args.command == "granola-progress"


def test_granola_progress_includes_unnumbered_content_captures(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [{"id": "listed-1", "title": "One"}],
            }
        ),
        encoding="utf-8",
    )
    (granola_dir / "granola-content-20260907T000000Z.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [
                    {
                        "id": "listed-1",
                        "summary": "Detailed summary",
                        "transcript": "Transcript text",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        ingest_mcp_sources(config, con)
        progress = write_granola_progress(config, con)
    finally:
        con.close()

    assert progress["content_capture_file_count"] == 1
    assert progress["capture_file_count"] == 2
    assert progress["content_captured_ids"] == ["listed-1"]
    assert progress["registered_capture_file_count"] == 2
    assert progress["unregistered_capture_files"] == []


def test_granola_progress_uses_connector_limit_for_clean_batch(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    listed = [{"id": f"listed-{index:02d}"} for index in range(12)]
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps({"provider": "granola", "meetings": listed}),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        progress = write_granola_progress(config, con)
        summary = build_report(config, con)
    finally:
        con.close()

    assert progress["next_batch_size"] == 10
    assert len(progress["next_batch_ids"]) == 10
    assert progress["next_batch_ids"] == [f"listed-{index:02d}" for index in range(10)]


def test_granola_progress_downshifts_after_explicit_rate_limit(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    listed_ids = [f"listed-{index:02d}" for index in range(12)]
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps(
            {"provider": "granola", "meetings": [{"id": value} for value in listed_ids]}
        ),
        encoding="utf-8",
    )
    (granola_dir / "granola-content-batch-0001-20260906.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [],
                "_capture": {
                    "requests": [
                        {
                            "tool": "granola_get_meetings",
                            "meeting_ids": listed_ids[:10],
                            "status": "rate_limited",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        progress = write_granola_progress(config, con)
    finally:
        con.close()

    assert progress["next_batch_size"] == 5
    assert len(progress["next_batch_ids"]) == 5
    assert progress["rate_limited_ids"] == listed_ids[:10]


def test_granola_progress_cli_records_index_checkpoint(tmp_path: Path, capsys):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps({"provider": "granola", "meetings": [{"id": "listed-1"}]}),
        encoding="utf-8",
    )

    assert main(["--root", str(tmp_path), "granola-progress"]) == 0
    capsys.readouterr()

    checkpoint = json.loads(
        (tmp_path / "work-corpus/state/index_rebuild.json").read_text(
            encoding="utf-8"
        )
    )
    assert checkpoint["fts_rows"] == 0
    assert checkpoint["relationship_rows"] == 0
    assert checkpoint["fts_api"] == "work_corpus.query.rebuild_search_index"


def test_granola_progress_uses_exact_ids_and_separates_retries(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [
                    {"id": "listed-1", "title": "One", "summary": "metadata"},
                    {"id": "listed-2", "title": "Two", "summary": "metadata"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (granola_dir / "granola-content-batch-0001-20260906.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [
                    {
                        "id": "listed-1",
                        "summary": "Detailed summary",
                        "transcript": "Transcript text",
                    },
                    {"id": "listed-2", "summary": "Summary only"},
                ],
                "_capture": {
                    "requests": [
                        {
                            "tool": "granola_get_meetings",
                            "meeting_ids": ["listed-1", "unlisted-provider-id"],
                        },
                        {
                            "tool": "granola_get_meeting_transcript",
                            "meeting_id": "listed-1",
                        },
                        {
                            "tool": "granola_get_meeting_transcript",
                            "meeting_id": "listed-2",
                        },
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        ingest_mcp_sources(config, con)
        (config.state_dir / "mcp").mkdir(parents=True, exist_ok=True)
        (config.state_dir / "mcp/granola_detail_progress.json").write_text(
            json.dumps({"not_found_ids": ["stale-id"]}), encoding="utf-8"
        )
        progress = write_granola_progress(config, con)
        summary = build_report(config, con)
    finally:
        con.close()

    assert progress["listed_id_count"] == 2
    assert progress["content_captured_id_count"] == 2
    assert progress["detailed_summary_id_count"] == 2
    assert progress["transcript_id_count"] == 1
    assert progress["summary_only_ids"] == ["listed-2"]
    assert progress["transcript_retry_ids"] == ["listed-2"]
    assert progress["metadata_only_pending"] == 0
    assert progress["imported_id_count"] == 2
    assert progress["searchable_id_count"] == 2
    assert progress["terminal_unavailable_ids"] == []
    assert progress["requested_ids_not_in_inventory"] == ["unlisted-provider-id"]
    assert progress["previous_state_not_found_ids"] == ["stale-id"]
    assert progress["previous_state_not_listed_ids"] == ["stale-id"]
    assert progress["registered_capture_file_count"] == 2
    assert progress["unregistered_capture_files"] == []
    assert len(progress["next_batch_ids"]) <= 10
    assert summary["granola_progress"]["status"] == "incomplete"
    assert summary["granola_progress"]["listed_id_count"] == 2
    assert summary["granola_progress"]["content_captured_id_count"] == 2
    assert summary["granola_progress"]["imported_id_count"] == 2
    assert summary["granola_progress"]["searchable_id_count"] == 2


def test_granola_progress_requires_exact_terminal_outcomes(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps({"provider": "granola", "meetings": [{"id": "listed-1"}]}),
        encoding="utf-8",
    )
    (granola_dir / "granola-content-batch-0001-20260906.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [],
                "_capture": {
                    "not_found_ids": ["listed-1", "stale-id"],
                    "requests": [
                        {
                            "tool": "granola_get_meetings",
                            "meeting_id": "listed-1",
                            "status": "not_found",
                        },
                        {
                            "tool": "granola_get_meeting_transcript",
                            "meeting_id": "listed-1",
                            "status": "unavailable",
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        ingest_mcp_sources(config, con)
        (config.state_dir / "mcp").mkdir(parents=True, exist_ok=True)
        (config.state_dir / "mcp/granola_detail_progress.json").write_text(
            json.dumps({"not_found_ids": ["old-id"]}), encoding="utf-8"
        )
        progress = write_granola_progress(config, con)
    finally:
        con.close()

    assert progress["status"] == "complete"
    assert progress["terminal_unavailable_ids"] == ["listed-1", "stale-id"]
    assert progress["terminal_unavailable_listed_ids"] == ["listed-1"]
    assert progress["retryable_ids"] == []
    assert progress["imported_ids"] == ["listed-1"]
    assert progress["searchable_ids"] == ["listed-1"]
    assert progress["unimported_ids"] == []
    assert progress["requested_ids_not_in_inventory"] == []
    assert progress["previous_state_not_found_ids"] == ["old-id"]


def test_granola_progress_reports_complete_rest_api_backfill_separately(tmp_path: Path):
    granola_dir = tmp_path / "data/mcp/granola"
    granola_dir.mkdir(parents=True)
    (granola_dir / "granola-inventory-20260906.json").write_text(
        json.dumps({"provider": "granola", "meetings": [{"id": "mcp-1"}]}),
        encoding="utf-8",
    )
    (granola_dir / "granola-api-backfill-test.json").write_text(
        json.dumps(
            {
                "provider": "granola",
                "meetings": [
                    {
                        "id": "not_12345678901234",
                        "title": "API note",
                        "date": "2026-09-06T18:00:00Z",
                        "summary": "Summary",
                        "transcript": "Summary:\nSummary",
                    }
                ],
                "notes": [
                    {
                        "id": "not_12345678901234",
                        "title": "API note",
                        "created_at": "2026-09-06T18:00:00Z",
                        "summary_text": "Summary",
                        "transcript": [],
                    }
                ],
                "_capture": {
                    "transport": "granola_rest_api",
                    "list_pages": [
                        {
                            "page": 1,
                            "note_ids": ["not_12345678901234"],
                            "has_more": False,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    con = connect(config.state_dir / "work_corpus.sqlite")
    try:
        inventory(config, con)
        ingest_mcp_sources(config, con)
        progress = write_granola_progress(config, con)
        summary = build_report(config, con)
    finally:
        con.close()

    rest = progress["rest_api"]
    assert rest["status"] == "complete"
    assert rest["note_count"] == 1
    assert rest["unique_note_id_count"] == 1
    assert rest["list_page_count"] == 1
    assert rest["summary_only_count"] == 1
    assert rest["imported_id_count"] == 1
    assert rest["searchable_id_count"] == 1
    assert progress["status"] == "incomplete"
    assert summary["granola_progress"]["archive_status"] == "complete"
    assert summary["granola_progress"]["rest_api"]["note_count"] == 1
    report_markdown = (
        tmp_path / "work-corpus/corpus/reports/what_we_have_and_need.md"
    ).read_text(
        encoding="utf-8"
    )
    assert "Granola capture remains incomplete" not in report_markdown
    assert "Granola REST archive: status=complete" in report_markdown
    report_html = (tmp_path / "work-corpus/corpus/reports/status.html").read_text(
        encoding="utf-8"
    )
    assert "<h2>Granola API archive</h2>" in report_html
    assert "status=complete; 1 notes" in report_html
