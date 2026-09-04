from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from work_corpus import cli
from work_corpus.config import ConfigurationError, load_config


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
    assert config.source_root("zoom").path == config.data_dir / "zoom"


def test_derived_path_rejects_data_child():
    config = load_config(REPOSITORY_ROOT)

    with pytest.raises(ConfigurationError, match="derived path.*data"):
        config.assert_derived_path(config.data_dir / "normalized" / "meeting.md")


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
