from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import connect, record_source_version, upsert_source_record
from work_corpus.inventory import inventory
from work_corpus.zoom import scan_zoom


def _config_and_db(tmp_path: Path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "zoom.sqlite")
    con.execute(
        """
        INSERT INTO source_root (
            root_key, relative_path, source_system, precedence, enabled
        ) VALUES ('zoom', 'data/Zoom', 'zoom', 50, 1)
        """
    )
    con.commit()
    return config, con


def _add_source(
    config,
    con,
    relative_path: str,
    content: bytes,
    *,
    kind: str,
    extraction_status: str = "ready",
    status: str = "present",
    classification: str = "Work",
    metadata: dict | None = None,
    hash_content: bool = True,
):
    path = config.root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    source_id = upsert_source_record(
        con,
        root_key="zoom",
        relative_path=relative_path,
        source_system="zoom",
        kind=kind,
        scope=classification,
        sensitivity="internal_review",
        status=status,
    )
    digest = hashlib.sha256(content).hexdigest() if hash_content else None
    con.execute(
        """
        UPDATE source_record
        SET absolute_path=?, extension=?, size_bytes=?, mtime_ns=?,
            content_sha256=?, classification=?, scope=?, extraction_status=?,
            metadata_json=?
        WHERE source_id=?
        """,
        (
            str(path),
            path.suffix.lower(),
            len(content),
            path.stat().st_mtime_ns,
            digest,
            classification,
            classification,
            extraction_status,
            json.dumps(metadata or {}, sort_keys=True),
            source_id,
        ),
    )
    version_id = None
    if digest:
        version_id = record_source_version(
            con,
            source_id=source_id,
            size_bytes=len(content),
            mtime_ns=path.stat().st_mtime_ns,
            content_sha256=digest,
        )
    con.commit()
    return source_id, version_id


def _usable_vtt(text: str = "hello") -> bytes:
    return (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:01.000\n"
        f"{text}\n"
    ).encode()


def test_inventory_queue_preserves_provenance_fks_and_waits_for_approval(
    tmp_path: Path,
):
    meeting = "data/Zoom/2026-09-04 11.00.00 Team Sync"
    media_path = tmp_path / meeting / "meeting.m4a"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"synthetic eligible media bytes")
    config = load_config(tmp_path)
    con = connect(config.state_dir / "inventory-zoom.sqlite")
    try:
        inventory(config, con)
        result = scan_zoom(config, con)
        source = con.execute(
            """
            SELECT source_id, source_version_id, content_sha256
            FROM source_record WHERE relative_path=?
            """,
            (f"{meeting}/meeting.m4a",),
        ).fetchone()
        version = con.execute(
            """
            SELECT source_version_id, source_id, content_sha256
            FROM source_version WHERE source_version_id=?
            """,
            (source["source_version_id"],),
        ).fetchone()
        group = con.execute(
            """
            SELECT media_source_id, media_version_id, status
            FROM meeting_group
            """
        ).fetchone()
        job = con.execute(
            """
            SELECT media_source_id, media_version_id, status, approval_status
            FROM transcription_job
            """
        ).fetchone()
        foreign_key_violations = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        con.close()

    assert result["queued_for_transcription"] == 1
    assert source is not None
    assert version is not None
    assert dict(group) == {
        "media_source_id": source["source_id"],
        "media_version_id": source["source_version_id"],
        "status": "pending_approval",
    }
    assert dict(job) == {
        "media_source_id": source["source_id"],
        "media_version_id": source["source_version_id"],
        "status": "pending_approval",
        "approval_status": "pending_approval",
    }
    assert source["source_id"] == version["source_id"]
    assert source["content_sha256"] == version["content_sha256"]
    assert foreign_key_violations == []


def test_stale_media_version_is_blocked_without_foreign_key_failure(
    tmp_path: Path,
):
    config, con = _config_and_db(tmp_path)
    try:
        source_id, _version_id = _add_source(
            config,
            con,
            "data/Zoom/2026-09-07 Stale Version/recording.mp4",
            b"synthetic media",
            kind="media",
        )
        con.execute(
            "UPDATE source_record SET source_version_id=? WHERE source_id=?",
            ("stale-version-id", source_id),
        )
        con.commit()

        result = scan_zoom(config, con)
        group = con.execute(
            "SELECT media_source_id, media_version_id, status FROM meeting_group"
        ).fetchone()
        job = con.execute(
            "SELECT media_source_id, media_version_id, status FROM transcription_job"
        ).fetchone()
        foreign_key_violations = con.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        con.close()

    assert result["blocked"] == 1
    assert group["media_source_id"] == source_id
    assert group["media_version_id"] is None
    assert group["status"] == "blocked"
    assert job["media_source_id"] == source_id
    assert job["media_version_id"] is None
    assert job["status"] == "blocked"
    assert foreign_key_violations == []


def test_nested_audio_record_belongs_to_parent_group(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-01 Team Sync/meeting.mp4",
            b"video",
            kind="media",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-01 Team Sync/Audio Record/audio.m4a",
            b"audio",
            kind="media",
        )

        result = scan_zoom(config, con)

        groups = con.execute(
            "SELECT group_id, folder_relative_path FROM meeting_group"
        ).fetchall()
        jobs = con.execute(
            "SELECT media_source_id, media_version_id, status FROM transcription_job"
        ).fetchall()
    finally:
        con.close()

    assert result["meeting_folders"] == 1
    assert len(groups) == 1
    assert groups[0]["folder_relative_path"] == "data/Zoom/2026-09-01 Team Sync"
    assert len(jobs) == 2
    assert {row["status"] for row in jobs} == {"pending_approval"}
    assert all(row["media_version_id"] for row in jobs)


def test_existing_transcript_wins_over_media_queue(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-02 Planning/recording.mp4",
            b"video",
            kind="media",
        )
        transcript_id, _ = _add_source(
            config,
            con,
            "data/Zoom/2026-09-02 Planning/meeting_transcript.vtt",
            _usable_vtt(),
            kind="transcript",
        )

        result = scan_zoom(config, con)
        group = con.execute("SELECT * FROM meeting_group").fetchone()
        jobs = con.execute("SELECT * FROM transcription_job").fetchall()
    finally:
        con.close()

    assert result["with_existing_transcript"] == 1
    assert group["status"] == "existing_transcript"
    assert group["transcript_source_id"] == transcript_id
    assert not jobs


def test_transcript_only_group_is_not_title_matched(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-03 Product Sync/recording.mp4",
            b"video",
            kind="media",
        )
        transcript_id, _ = _add_source(
            config,
            con,
            "data/Zoom/2026-09-04 Product Sync/meeting_transcript.vtt",
            _usable_vtt("transcript only"),
            kind="transcript",
        )

        scan_zoom(config, con)
        groups = con.execute(
            """
            SELECT folder_relative_path, media_source_id, transcript_source_id, status
            FROM meeting_group ORDER BY folder_relative_path
            """
        ).fetchall()
        reviews = con.execute(
            """
            SELECT issue_type, source_id, proposed_result_json
            FROM review_item WHERE issue_type='zoom_transcript_match'
            """
        ).fetchall()
    finally:
        con.close()

    assert len(groups) == 2
    media_group, transcript_group = groups
    assert media_group["transcript_source_id"] is None
    assert transcript_group["media_source_id"] is None
    assert transcript_group["transcript_source_id"] == transcript_id
    assert transcript_group["status"] == "transcript_only"
    assert reviews
    proposal = json.loads(reviews[0]["proposed_result_json"])
    assert proposal["transcript_group_id"] != proposal["candidate_group_id"]


def test_transcript_precedence_and_chat_exclusion(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-05 Review/recording.mp4",
            b"video",
            kind="media",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-05 Review/chat.txt",
            b"not a transcript",
            kind="meeting_chat",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-05 Review/meeting_transcript.txt",
            b"plain transcript",
            kind="transcript_candidate",
        )
        srt_id, _ = _add_source(
            config,
            con,
            "data/Zoom/2026-09-05 Review/meeting.srt",
            b"1\n00:00:00,000 --> 00:00:01,000\nSRT wins\n",
            kind="transcript",
        )
        vtt_id, _ = _add_source(
            config,
            con,
            "data/Zoom/2026-09-05 Review/meeting.vtt",
            _usable_vtt("VTT wins"),
            kind="transcript",
        )

        scan_zoom(config, con)
        group = con.execute("SELECT * FROM meeting_group").fetchone()
    finally:
        con.close()

    assert group["status"] == "existing_transcript"
    assert group["transcript_source_id"] == vtt_id
    assert group["transcript_source_id"] != srt_id


def test_scan_queue_report_contains_all_final_media_and_artifacts(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-06 Coverage/one.mp4",
            b"one",
            kind="media",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-06 Coverage/two.m4a",
            b"two",
            kind="media",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-06 Coverage/recording.tmp",
            b"temporary",
            kind="unknown",
        )
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-06 Coverage/recording.zoom",
            b"unvalidated",
            kind="unknown",
        )

        scan_zoom(config, con)
        rows = list(
            csv.DictReader(
                (config.state_dir / "transcription_queue.csv").open(
                    encoding="utf-8-sig", newline=""
                )
            )
        )
    finally:
        con.close()

    assert len([row for row in rows if row["media_path"].endswith((".mp4", ".m4a"))]) == 2
    assert {row["status"] for row in rows if row["media_path"].endswith((".tmp", ".zoom"))} == {"artifact"}


def test_queue_report_preserves_each_media_source_version(tmp_path: Path):
    config, con = _config_and_db(tmp_path)
    try:
        relative_path = "data/Zoom/2026-09-07 Versioned/recording.mp4"
        _add_source(config, con, relative_path, b"first", kind="media")
        scan_zoom(config, con)
        first = con.execute(
            "SELECT media_version_id FROM transcription_job"
        ).fetchone()["media_version_id"]

        _add_source(config, con, relative_path, b"second", kind="media")
        scan_zoom(config, con)
        rows = list(
            csv.DictReader(
                (config.state_dir / "transcription_queue.csv").open(
                    encoding="utf-8-sig", newline=""
                )
            )
        )
    finally:
        con.close()

    version_ids = {
        row["media_version_id"]
        for row in rows
        if row["relative_path"] == relative_path
    }
    assert first
    assert len(version_ids) == 2
    assert len([row for row in rows if row["relative_path"] == relative_path]) == 2


def test_missing_existing_transcript_requeues_the_same_media_version(
    tmp_path: Path,
):
    config, con = _config_and_db(tmp_path)
    transcript_path = config.root / (
        "data/Zoom/2026-09-08 Transcript Recovery/meeting_transcript.vtt"
    )
    try:
        _add_source(
            config,
            con,
            "data/Zoom/2026-09-08 Transcript Recovery/recording.mp4",
            b"media",
            kind="media",
        )
        scan_zoom(config, con)
        original = con.execute(
            "SELECT job_id, media_version_id, status FROM transcription_job"
        ).fetchone()

        _add_source(
            config,
            con,
            "data/Zoom/2026-09-08 Transcript Recovery/meeting_transcript.vtt",
            _usable_vtt(),
            kind="transcript",
        )
        scan_zoom(config, con)
        covered = con.execute(
            "SELECT status, approval_status FROM transcription_job WHERE job_id=?",
            (original["job_id"],),
        ).fetchone()
        transcript_path.unlink()

        scan_zoom(config, con)
        requeued = con.execute(
            "SELECT job_id, media_version_id, status, approval_status "
            "FROM transcription_job WHERE job_id=?",
            (original["job_id"],),
        ).fetchone()
    finally:
        con.close()

    assert original["status"] == "pending_approval"
    assert covered["status"] == "not_needed"
    assert covered["approval_status"] == "not_needed"
    assert requeued["job_id"] == original["job_id"]
    assert requeued["media_version_id"] == original["media_version_id"]
    assert requeued["status"] == "pending_approval"
    assert requeued["approval_status"] == "pending_approval"
