from __future__ import annotations

import json
from pathlib import Path

from work_corpus.config import load_config
from work_corpus.db import connect, recover_stale_runs
from work_corpus.doctor import doctor


def test_recover_stale_runs_marks_only_old_running_rows(tmp_path: Path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "doctor.sqlite")
    try:
        con.execute(
            "INSERT INTO pipeline_run (run_id, command, started_at, status) "
            "VALUES ('old', 'query', '2020-01-01T00:00:00+00:00', 'running')"
        )
        con.execute(
            "INSERT INTO pipeline_run (run_id, command, started_at, status) "
            "VALUES ('done', 'report', '2020-01-01T00:00:00+00:00', 'complete')"
        )
        con.commit()

        assert recover_stale_runs(con, stale_after_hours=24) == 1
        old = con.execute(
            "SELECT status, completed_at, details_json FROM pipeline_run "
            "WHERE run_id='old'"
        ).fetchone()
        done = con.execute(
            "SELECT status FROM pipeline_run WHERE run_id='done'"
        ).fetchone()
    finally:
        con.close()

    assert old["status"] == "abandoned"
    assert old["completed_at"]
    assert "stale" in old["details_json"]
    assert done["status"] == "complete"


def test_doctor_writes_local_json_and_reports_sqlite_and_legacy_boundary(tmp_path: Path):
    (tmp_path / "TrojanHorse").mkdir()
    config = load_config(tmp_path)
    con = connect(config.state_dir / "doctor.sqlite")
    try:
        text = doctor(config, con)
    finally:
        con.close()

    payload = json.loads((config.state_dir / "doctor.json").read_text())
    assert payload["sqlite"]["quick_check"] == "ok"
    assert payload["sqlite"]["foreign_key_violations"] == 0
    assert payload["legacy_runtime"]["status"] == "quarantined"
    assert "Atlas" in text
    assert not (tmp_path / "data").exists()


def test_doctor_can_exclude_its_own_active_run(tmp_path: Path):
    config = load_config(tmp_path)
    con = connect(config.state_dir / "doctor.sqlite")
    try:
        con.execute(
            "INSERT INTO pipeline_run (run_id, command, started_at, status) "
            "VALUES ('doctor-run', 'doctor', '2026-09-07T10:00:00+00:00', 'running')"
        )
        con.commit()
        doctor(config, con, exclude_run_id="doctor-run")
    finally:
        con.close()

    payload = json.loads((config.state_dir / "doctor.json").read_text())
    assert payload["pipeline"]["running_rows_after_recovery"] == 0
