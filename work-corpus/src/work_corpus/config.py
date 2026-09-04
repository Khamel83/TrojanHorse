from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": {"data": "data", "corpus": "corpus", "state": "state"},
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
    "email": {
        "since": "2024-01-01",
        "attachments": "metadata_only",
        "legacy_outlook_folders": ["Inbox", "Sent Items"],
        "legacy_outlook_max_messages_per_folder": 2000,
    },
    "mcp": {
        "granola_inbox": "data/mcp/granola",
        "wispr_flow_inbox": "data/mcp/wispr_flow",
    },
}


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

    def resolve_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.root / path).resolve()

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.payload.get(section, {}).get(key, default)

    def section(self, section: str) -> Dict[str, Any]:
        return dict(self.payload.get(section, {}))


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
