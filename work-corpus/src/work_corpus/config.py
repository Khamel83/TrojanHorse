from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": {
        "data": "data",
        "corpus": "work-corpus/corpus",
        "state": "work-corpus/state",
    },
    "source_roots": {
        "zoom": "data/zoom",
        "notes_onenote": "data/notes/onenote",
        "notes_notion": "data/notes/notion",
        "notes_capacities": "data/notes/capacities",
        "notes_other": "data/notes/other",
        "mcp_granola": "data/mcp/granola",
        "mcp_wispr_flow": "data/mcp/wispr_flow",
    },
    "inventory": {
        "ignore_directories": [".git", "node_modules", "__pycache__", ".venv", "venv", "corpus", "state"],
        "hash_files_up_to_mb": 32,
        "follow_directory_symlinks": True,
        "max_archive_entries_to_list": 100000,
    },
    "normalization": {
        "max_text_file_mb": 200,
        "max_table_rows": 100000,
        "extract_pdf_when_pypdf_available": True,
        "extract_docx_when_available": True,
        "extract_pptx_when_available": True,
        "extract_xlsx_when_available": True,
        "skip_classifications": ["potential_personal", "mixed_or_review"],
    },
    "zoom": {
        "language": "en",
        "engine": "auto",
        "model": "small.en",
        "whisper_cpp_command": "whisper-cli",
        "whisper_cpp_model": "",
        "ffmpeg_command": "ffmpeg",
        "ffprobe_command": "ffprobe",
        "local_models_only": True,
        "auto_transcribe_max_files": 0,
        "keep_temporary_wav": False,
        "custom_command": [],
        "custom_output_format": "vtt",
    },
    "mcp": {
        "granola_inbox": "data/mcp/granola",
        "wispr_flow_inbox": "data/mcp/wispr_flow",
    },
}


LOCAL_TRANSCRIPTION_ENGINES = {
    "auto",
    "custom",
    "whisper_cpp",
    "faster_whisper",
    "openai_whisper",
}
REMOTE_TRANSCRIPTION_OPTIONS = {
    "api_key",
    "api_token",
    "base_url",
    "endpoint",
    "organization",
    "project",
    "provider",
}


class ConfigurationError(ValueError):
    """Raised when a configuration crosses the local corpus boundary."""


@dataclass(frozen=True)
class SourceRoot:
    name: str
    path: Path


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


class Config:
    def __init__(self, root: Path, payload: Dict[str, Any]) -> None:
        self.root = root.resolve()
        self.payload = payload
        self.data_dir = self.resolve_path(payload["paths"]["data"])
        self.corpus_dir = self.resolve_path(payload["paths"]["corpus"])
        self.state_dir = self.resolve_path(payload["paths"]["state"])
        self.source_roots = self._load_source_roots(payload.get("source_roots", {}))
        self._validate_derived_roots()
        self._validate_local_transcription()

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.root / path).resolve()

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.payload.get(section, {}).get(key, default)

    def section(self, section: str) -> Dict[str, Any]:
        return dict(self.payload.get(section, {}))

    def source_root(self, name: str) -> SourceRoot:
        try:
            return self.source_roots[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown source root: {name}") from exc

    def assert_derived_path(self, path: Path) -> None:
        resolved = path.expanduser().resolve()
        if _is_within(resolved, self.data_dir):
            raise ConfigurationError(
                f"derived path must be outside data/: {resolved}"
            )

    def _load_source_roots(self, configured: Any) -> Dict[str, SourceRoot]:
        if not isinstance(configured, dict):
            raise ConfigurationError("source_roots must be an object")

        roots: Dict[str, SourceRoot] = {}
        for name, value in configured.items():
            raw_path = value.get("path") if isinstance(value, dict) else value
            if not isinstance(raw_path, str) or not raw_path:
                raise ConfigurationError(f"source root {name!r} must define a path")
            roots[name] = SourceRoot(name=name, path=self.resolve_path(raw_path))
        return roots

    def _validate_derived_roots(self) -> None:
        self.assert_derived_path(self.corpus_dir)
        self.assert_derived_path(self.state_dir)

    def _validate_local_transcription(self) -> None:
        zoom = self.section("zoom")
        engine = zoom.get("engine", "auto")
        if engine not in LOCAL_TRANSCRIPTION_ENGINES:
            raise ConfigurationError(
                f"local transcription engine required; got {engine!r}"
            )

        remote_options = REMOTE_TRANSCRIPTION_OPTIONS.intersection(zoom)
        if remote_options:
            names = ", ".join(sorted(remote_options))
            raise ConfigurationError(
                f"local transcription configuration cannot include remote options: {names}"
            )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def load_config(root: Path) -> Config:
    config_path = root / "work-corpus" / "config.json"
    local_path = root / "work-corpus" / "config.local.json"
    payload: Dict[str, Any] = {}
    if config_path.exists():
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    merged = _merge(DEFAULT_CONFIG, payload)
    if local_path.exists():
        merged = _merge(merged, json.loads(local_path.read_text(encoding="utf-8")))
    return Config(root, merged)
