from __future__ import annotations

import hashlib
import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import (
    connect,
    record_evidence,
    record_review_item,
    record_source_version,
    upsert_source_record,
)
from work_corpus.entities import add_alias, create_entity
from work_corpus.report import build_report


def _mcp_source(tmp_path: Path, provider: str):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "report.sqlite")
    root_key = "mcp_granola" if provider == "granola" else "mcp_wispr_flow"
    con.execute(
        """
        INSERT INTO source_root (root_key, relative_path, source_system, precedence)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(root_key) DO NOTHING
        """,
        (root_key, f"data/mcp/{provider}", provider, 45),
    )
    relative_path = f"data/mcp/{provider}/snapshot.json"
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    source_id = upsert_source_record(
        con,
        root_key=root_key,
        relative_path=relative_path,
        source_system=provider,
        kind="mcp",
        scope="Work",
        sensitivity="internal_review",
    )
    content = path.read_bytes()
    version_id = record_source_version(
        con,
        source_id,
        len(content),
        path.stat().st_mtime_ns,
        hashlib.sha256(content).hexdigest(),
    )
    con.execute(
        "UPDATE source_record SET absolute_path=?, extension='.json', extraction_status='ready' WHERE source_id=?",
        (str(path), source_id),
    )
    return config, con, source_id, version_id, root_key


def test_report_marks_unknown_mcp_retrieval_as_unknown(tmp_path: Path):
    config, con, source_id, version_id, root_key = _mcp_source(tmp_path, "wispr_flow")
    try:
        checkpoint_id = "checkpoint-wispr"
        con.execute(
            """
            INSERT INTO ingestion_checkpoint (
                checkpoint_id, provider, root_key, cursor, source_version_id,
                item_count, updated_at
            ) VALUES (?, 'wispr_flow', ?, 'snapshot.json:0', ?, 1, ?)
            """,
            (checkpoint_id, root_key, version_id, "2026-09-04T00:00:00Z"),
        )
        con.execute(
            """
            INSERT INTO mcp_item (
                item_id, source_id, provider, external_record_id, capture_date,
                event_date, retrieval_date, original_response_sha256,
                normalized_evidence_id, checkpoint_id, updated_at
            ) VALUES ('item-wispr', ?, 'wispr_flow', 'w-1', '2026-09-03',
                      '2026-09-03', NULL, ?, NULL, ?, ?)
            """,
            (source_id, hashlib.sha256(b"response").hexdigest(), checkpoint_id, "2026-09-04T00:00:00Z"),
        )
        con.commit()
        summary = build_report(config, con)
    finally:
        con.close()

    assert summary["mcp_feed_freshness"] == [
        {
            "provider": "wispr_flow",
            "item_count": 1,
            "known_retrieval_dates": 0,
            "latest_retrieval_date": "",
            "freshness": "unknown",
        }
    ]
    report = json.loads((config.corpus_dir / "reports" / "status.json").read_text())
    assert report["mcp_feed_freshness"][0]["freshness"] == "unknown"


def test_report_contains_all_acceptance_categories_without_sensitive_values(
    tmp_path: Path,
):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "acceptance.sqlite")
    try:
        con.execute(
            "INSERT INTO source_root (root_key, relative_path, source_system, precedence) "
            "VALUES ('synthetic_work', 'data/work', 'formal_records', 5)"
        )

        def source(
            relative_path: str,
            source_system: str,
            kind: str,
            scope: str = "Work",
            content: str = "synthetic evidence",
        ) -> tuple[str, str]:
            root_key = "synthetic_work"
            source_id = upsert_source_record(
                con,
                root_key=root_key,
                relative_path=relative_path,
                source_system=source_system,
                kind=kind,
                scope=scope,
                sensitivity="internal",
            )
            path = tmp_path / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            payload = path.read_bytes()
            version_id = record_source_version(
                con,
                source_id,
                len(payload),
                path.stat().st_mtime_ns,
                hashlib.sha256(payload).hexdigest(),
            )
            con.execute(
                """
                UPDATE source_record
                SET absolute_path=?, extension=?, classification=?,
                    extraction_status='ready'
                WHERE source_id=?
                """,
                (str(path), path.suffix.lower(), scope, source_id),
            )
            return source_id, version_id

        work_source, work_version = source(
            "data/work/evidence.md", "formal_records", "document"
        )
        evidence_id = record_evidence(
            con,
            work_version,
            "document",
            str(tmp_path / "corpus/evidence.md"),
            "e" * 64,
            "derived",
            derived_text="safe work evidence",
        )
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, normalized_path, parser,
                parser_version, status, error
            ) VALUES (?, ?, ?, 'synthetic', 'v1', 'prior_good_retained', NULL)
            """,
            (work_version, work_source, str(tmp_path / "corpus/evidence.md")),
        )
        source(
            "data/.DS_Store",
            "formal_records",
            "metadata",
        )
        source(
            "data/note-inventory/report.txt",
            "inventory_discovery",
            "discovery",
            scope="Unknown",
        )

        pointer_source, pointer_version = source(
            "data/notes/Notes/Files/pointer.md",
            "capacities",
            "document",
            content=(
                "type: file\n"
                "url: https://example.test/file?X-Amz-Signature=secret-value\n"
            ),
        )
        con.execute(
            """
            INSERT INTO normalized_document (
                source_version_id, source_id, normalized_path, parser,
                parser_version, status, error
            ) VALUES (?, ?, ?, 'synthetic', 'v1', 'normalized', NULL)
            """,
            (
                pointer_version,
                pointer_source,
                str(tmp_path / "corpus/pointer.md"),
            ),
        )

        notion_page, _ = source(
            "data/notes/notion/page.html", "notion", "document"
        )
        source("data/notes/notion/database.csv", "notion", "table")
        source("data/notes/notion/attachment.png", "notion", "unknown")
        onenote_source, _ = source(
            "data/notes/Backup/notebook.one", "onenote", "archive"
        )

        media_source, media_version = source(
            "data/Zoom/2026-09-04 09.00.00 Work/audio.m4a",
            "zoom",
            "media",
        )
        group_id = "group-synthetic"
        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, meeting_date, media_source_id,
                media_version_id, status, updated_at
            ) VALUES (?, 'data/Zoom/2026-09-04 09.00.00 Work', '2026-09-04',
                      ?, ?, 'blocked', '2026-09-04T00:00:00Z')
            """,
            (group_id, media_source, media_version),
        )
        con.execute(
            """
            INSERT INTO transcription_job (
                job_id, group_id, media_source_id, media_version_id,
                approval_status, output_stem, status, error, completed_at
            ) VALUES ('job-synthetic', ?, ?, ?, 'approved', 'corpus/tx',
                      'blocked', 'local engine unavailable', '2026-09-04T00:00:00Z')
            """,
            (group_id, media_source, media_version),
        )
        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, meeting_date, status, updated_at
            ) VALUES ('transcript-only', 'data/Zoom/2026-09-03 09.00.00 Transcript',
                      '2026-09-03', 'transcript_only', '2026-09-04T00:00:00Z')
            """
        )

        record_review_item(
            con,
            "scope_review",
            {"scope": "Mixed", "url": "https://example.test/?sig=secret-value"},
            source_id=notion_page,
        )
        entity_id = create_entity(con, "project", "synthetic", "Synthetic Project")
        add_alias(con, entity_id, "Synthetic", evidence_id=evidence_id, review_status="valid")
        record_review_item(
            con,
            "entity_collision",
            {"candidate_entity_ids": [entity_id, "other"]},
            evidence_id=evidence_id,
        )
        con.execute(
            """
            INSERT INTO task (
                task_id, action, source_event_date, event_date, candidate_status,
                task_status, source_evidence_id, source_date_basis
            ) VALUES ('historical-task', 'Review the archive', '2020-01-01',
                      '2020-01-01', 'historical', 'open', ?, 'event_date')
            """,
            (evidence_id,),
        )
        con.execute(
            """
            INSERT INTO ingestion_checkpoint (
                checkpoint_id, provider, cursor, item_count, updated_at
            ) VALUES ('granola-checkpoint', 'granola', 'snapshot:0', 1,
                      '2026-09-04T00:00:00Z')
            """
        )
        con.execute(
            """
            INSERT INTO mcp_item (
                item_id, source_id, provider, original_response_sha256,
                checkpoint_id, updated_at
            ) VALUES ('mcp-synthetic', ?, 'granola', ?, 'granola-checkpoint',
                      '2026-09-04T00:00:00Z')
            """,
            (work_source, "r" * 64),
        )
        con.commit()

        (config.state_dir / "onenote_acceptance.json").write_text(
            json.dumps(
                {
                    "files": 1,
                    "status_counts": {"blocked": 1},
                    "pages_extracted": 0,
                    "converter_available": False,
                    "raw_read": False,
                }
            ),
            encoding="utf-8",
        )
        (config.state_dir / "raw_immutability.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "before_files": 1,
                    "after_files": 1,
                    "before_bytes": 1,
                    "after_bytes": 1,
                    "mismatch_count": 0,
                }
            ),
            encoding="utf-8",
        )
        (config.state_dir / "index_rebuild.json").write_text(
            json.dumps({"fts_rows": 1, "relationship_rows": 0}),
            encoding="utf-8",
        )
        summary = build_report(config, con)
    finally:
        con.close()

    required = {
        "physical",
        "source_counts_by_root",
        "discovery_excluded",
        "normalization",
        "zoom",
        "onenote",
        "capacities",
        "notion",
        "review_queues",
        "entities",
        "tasks",
        "indexes",
        "mcp_feed_freshness",
        "raw_immutability",
    }
    assert required <= summary.keys()
    assert summary["physical"]["substantive_files"] == 8
    assert summary["discovery_excluded"]["normalized_documents"] == 0
    assert summary["capacities"]["pointer_only_payloads"] == 1
    assert summary["notion"]["page_count"] == 1
    assert summary["notion"]["database_count"] == 1
    assert summary["notion"]["attachment_count"] == 1
    assert summary["onenote"]["files"] == 1
    assert summary["raw_immutability"]["status"] == "passed"
    assert summary["zoom_missing_transcripts"] == 1
    assert summary["zoom_media_without_terminal_status"] == 0
    assert summary["zoom_meeting_folders"] == 1
    assert summary["zoom_tracked_groups"] == 2

    serialized = json.dumps(summary, ensure_ascii=False)
    assert "secret-value" not in serialized
    for report_path in (config.corpus_dir / "reports").glob("*"):
        if report_path.is_file():
            assert "secret-value" not in report_path.read_text(encoding="utf-8")


def test_report_does_not_count_successful_generated_media_as_missing(
    tmp_path: Path,
):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "generated-report.sqlite")
    try:
        con.execute(
            """
            INSERT INTO source_root (root_key, relative_path, source_system, precedence)
            VALUES ('zoom', 'data/Zoom', 'zoom', 50)
            """
        )
        relative_path = "data/Zoom/2026-09-04 09.00.00 Work/audio.m4a"
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"media")
        source_id = upsert_source_record(
            con,
            root_key="zoom",
            relative_path=relative_path,
            source_system="zoom",
            kind="media",
            scope="Work",
            sensitivity="internal_review",
        )
        digest = hashlib.sha256(b"media").hexdigest()
        version_id = record_source_version(
            con,
            source_id,
            path.stat().st_size,
            path.stat().st_mtime_ns,
            digest,
        )
        con.execute(
            """
            UPDATE source_record
            SET absolute_path=?, extension='.m4a', size_bytes=?, mtime_ns=?,
                content_sha256=?, source_version_id=?, classification='Work',
                scope='Work', extraction_status='ready'
            WHERE source_id=?
            """,
            (
                str(path),
                path.stat().st_size,
                path.stat().st_mtime_ns,
                digest,
                version_id,
                source_id,
            ),
        )
        con.execute(
            """
            INSERT INTO meeting_group (
                group_id, folder_relative_path, meeting_date, media_source_id,
                media_version_id, status, transcript_path, updated_at
            ) VALUES ('generated-group', 'data/Zoom/2026-09-04 09.00.00 Work',
                      '2026-09-04', ?, ?, 'succeeded', 'corpus/generated.md', ?)
            """,
            (source_id, version_id, "2026-09-04T00:00:00Z"),
        )
        con.execute(
            """
            INSERT INTO transcription_job (
                job_id, group_id, media_source_id, media_version_id,
                approval_status, output_stem, status, output_path,
                output_sha256, completed_at
            ) VALUES ('generated-job', 'generated-group', ?, ?, 'approved',
                      'corpus/generated', 'succeeded', 'corpus/generated.md',
                      ?, '2026-09-04T00:00:00Z')
            """,
            (source_id, version_id, "a" * 64),
        )
        con.commit()
        summary = build_report(config, con)
    finally:
        con.close()

    assert summary["zoom"]["eligible_final_media_without_transcript"] == 0
    assert summary["zoom"]["terminal_local_status_counts"] == {"succeeded": 1}
    assert summary["zoom"]["output_hashes"] == 1
    assert summary["zoom_missing_transcripts"] == 0
