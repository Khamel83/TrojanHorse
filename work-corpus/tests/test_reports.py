from __future__ import annotations

import hashlib
import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import connect, record_source_version, upsert_source_record
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
