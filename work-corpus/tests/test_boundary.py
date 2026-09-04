from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from work_corpus import cli
from work_corpus.config import ConfigurationError, load_config
import work_corpus.inventory as inventory_module
from work_corpus.db import connect
from work_corpus.normalize import _output_path
from work_corpus.report import build_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _command_names(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("work-corpus parser has no command set")


def _write_config(root: Path, payload: dict) -> None:
    config_dir = root / "work-corpus"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.json").write_text(json.dumps(payload), encoding="utf-8")


def test_config_resolves_data_and_derived_roots():
    config = load_config(REPOSITORY_ROOT)

    assert config.data_dir == REPOSITORY_ROOT / "data"
    assert config.corpus_dir != config.data_dir
    assert config.state_dir != config.data_dir
    assert config.source_root("zoom").path == config.data_dir / "Zoom"


def test_derived_path_rejects_data_child():
    config = load_config(REPOSITORY_ROOT)

    with pytest.raises(ConfigurationError, match="derived path.*data"):
        config.assert_derived_path(config.data_dir / "normalized" / "meeting.md")


def test_config_rejects_external_data_and_source_root_symlinks(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    data_dir = repository / "data"
    os.symlink(outside_dir, data_dir)

    with pytest.raises(ConfigurationError, match="data root"):
        load_config(repository)

    data_dir.unlink()
    data_dir.mkdir()
    os.symlink(outside_dir, data_dir / "linked")
    _write_config(
        repository,
        {
            "source_roots": {
                "zoom": {
                    "path": "data/linked",
                    "relative_path": "data/Zoom",
                }
            }
        },
    )

    with pytest.raises(ConfigurationError, match="source root"):
        load_config(repository)


def test_derived_path_rejects_external_symlink(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    config_dir = repository / "work-corpus"
    config_dir.mkdir()
    os.symlink(outside_dir, config_dir / "corpus")

    with pytest.raises(ConfigurationError, match="derived path"):
        load_config(repository)


def test_report_rejects_external_reports_symlink(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    config = load_config(repository)
    config.corpus_dir.mkdir(parents=True)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    os.symlink(outside_dir, config.corpus_dir / "reports")
    con = connect(config.state_dir / "report-boundary.sqlite")
    try:
        with pytest.raises(ConfigurationError, match="derived path"):
            build_report(config, con)
    finally:
        con.close()


def test_normalized_output_slugifies_untrusted_source_system(tmp_path: Path):
    config = load_config(tmp_path)

    output = _output_path(config, "../../outside", "version")

    assert output == config.corpus_dir / "normalized" / "outside" / "version.md"


def test_cli_command_set_has_no_email_or_atlas_command():
    parser = cli._parser()
    commands = _command_names(parser)

    assert commands == {
        "inventory",
        "normalize",
        "zoom-scan",
        "transcribe",
        "report",
        "query",
        "mcp-import",
    }
    assert "email-import" not in commands
    assert "promote-to-atlas" not in commands
    assert "--atlas-url" not in {
        option
        for action in parser._actions
        for option in action.option_strings
    }


def test_bootstrap_creates_only_derived_directories(tmp_path: Path):
    config = load_config(tmp_path)

    cli.bootstrap(config)

    assert not config.data_dir.exists()
    assert config.corpus_dir.is_dir()
    assert config.state_dir.is_dir()
    assert all((config.corpus_dir / rel).is_dir() for rel in cli.CORPUS_SUBDIRS)
    assert all((config.state_dir / rel).is_dir() for rel in cli.STATE_SUBDIRS)


def test_inventory_cli_does_not_create_raw_data_directory(tmp_path: Path):
    exit_code = cli.main(["--root", str(tmp_path), "inventory"])

    assert exit_code == 0
    assert not (tmp_path / "data").exists()


def test_inventory_does_not_follow_external_directory_symlink(tmp_path: Path):
    data_dir = tmp_path / "data"
    outside_dir = tmp_path / "outside"
    data_dir.mkdir()
    outside_dir.mkdir()
    (outside_dir / "secret.txt").write_text("outside boundary\n", encoding="utf-8")
    os.symlink(outside_dir, data_dir / "linked")

    config = load_config(tmp_path)
    con = connect(config.state_dir / "symlink.sqlite")
    try:
        inventory_module.inventory(config, con)
        rows = con.execute("SELECT relative_path FROM source_record").fetchall()
    finally:
        con.close()

    assert all(not row["relative_path"].startswith("data/linked/") for row in rows)


def test_source_root_rejects_unknown_name_from_synthetic_root(tmp_path: Path):
    config = load_config(tmp_path)

    with pytest.raises(ConfigurationError, match="unknown source root: missing"):
        config.source_root("missing")


@pytest.mark.parametrize(
    "zoom_config",
    [
        {"engine": "openai"},
        {"engine": "deepgram"},
        {"engine": "custom", "provider": "assemblyai"},
        {"engine": "custom", "api_key": "not-local"},
    ],
)
def test_local_transcription_is_the_only_allowed_transcription_mode(tmp_path: Path, zoom_config: dict):
    _write_config(tmp_path, {"zoom": zoom_config})

    with pytest.raises(ConfigurationError, match="local transcription"):
        load_config(tmp_path)

    _write_config(
        tmp_path,
        {
            "zoom": {
                "engine": "custom",
                "custom_command": ["/usr/local/bin/local-transcriber", "{input}", "{output_vtt}"],
            }
        },
    )
    config = load_config(tmp_path)

    assert config.get("zoom", "engine") == "custom"
