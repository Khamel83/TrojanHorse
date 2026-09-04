from __future__ import annotations

import json
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


NOTION_EXPORT_DIRECTORY = (
    "40b7a161-92e3-450d-8dab-c2bb4a080adf_"
    "ExportBlock-7045c812-ccf8-4b28-b774-5502ee6696b2"
)
CAPACITIES_ARCHIVE_NAME = "Capacities (2026-09-03 14-19-01).zip"
DEFAULT_SKIP_CLASSIFICATIONS = (
    "Personal",
    "Mixed",
    "Unknown",
    "potential_personal",
    "mixed_or_review",
)


EXPLICIT_SOURCE_ROOTS: Dict[str, Dict[str, Any]] = {
    "inventory_discovery": {
        "path": "data/note-inventory-20260903-142816",
        "source_system": "inventory_discovery",
        "precedence": 10,
    },
    "notion_export": {
        "path": f"data/notes/{NOTION_EXPORT_DIRECTORY}",
        "source_system": "notion",
        "precedence": 20,
    },
    "notion_archive": {
        "path": f"data/notes/{NOTION_EXPORT_DIRECTORY}.zip",
        "source_system": "notion",
        "precedence": 21,
    },
    "capacities_markdown": {
        "path": "data/notes/Notes",
        "source_system": "capacities",
        "precedence": 30,
    },
    "capacities_archive": {
        "path": f"data/notes/{CAPACITIES_ARCHIVE_NAME}",
        "source_system": "capacities",
        "precedence": 31,
    },
    "onenote_backup": {
        "path": "data/notes/Backup",
        "source_system": "onenote",
        "precedence": 40,
    },
    "zoom": {
        "path": "data/Zoom",
        "source_system": "zoom",
        "precedence": 50,
    },
}


DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": {
        "data": "data",
        "corpus": "work-corpus/corpus",
        "state": "work-corpus/state",
    },
    "source_roots": {
        key: dict(value) for key, value in EXPLICIT_SOURCE_ROOTS.items()
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
        "skip_classifications": list(DEFAULT_SKIP_CLASSIFICATIONS),
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
    key: str
    relative_path: str
    source_system: str
    precedence: int
    enabled: bool = True
    _resolved_path: Optional[Path] = field(default=None, repr=False, compare=False)

    @property
    def name(self) -> str:
        """Compatibility alias for the Task 1 named-root interface."""
        return self.key

    @property
    def path(self) -> Path:
        """Return the configured filesystem path for existing callers."""
        return self._resolved_path or Path(self.relative_path)


@dataclass(frozen=True)
class SourceRootMatch:
    root: Optional[SourceRoot]
    relative_path: str
    kind: str


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
        if not _is_within(self.data_dir, self.root):
            raise ConfigurationError(
                f"data root must remain inside repository: {self.data_dir}"
            )
        self.corpus_dir = self.resolve_path(payload["paths"]["corpus"])
        self.state_dir = self.resolve_path(payload["paths"]["state"])
        configured_roots = payload.get("source_roots", {})
        self.source_roots = self._load_source_roots(configured_roots)
        self._source_root_lookup = {root.key: root for root in self.source_roots}
        self._source_root_lookup.update(self._load_legacy_source_roots(configured_roots))
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
            return self._source_root_lookup[name]
        except KeyError as exc:
            raise ConfigurationError(f"unknown source root: {name}") from exc

    def assert_derived_path(self, path: Path) -> None:
        resolved = path.expanduser().resolve()
        if not _is_within(resolved, self.root):
            raise ConfigurationError(
                f"derived path must remain inside repository: {resolved}"
            )
        if _is_within(resolved, self.data_dir):
            raise ConfigurationError(
                f"derived path must be outside data/: {resolved}"
            )

    def _load_source_roots(self, configured: Any) -> Tuple[SourceRoot, ...]:
        if not isinstance(configured, dict):
            raise ConfigurationError("source_roots must be an object")

        roots: list[SourceRoot] = []
        data_relative = self._normalise_source_path(self.payload["paths"]["data"])

        for key, base in EXPLICIT_SOURCE_ROOTS.items():
            configured_value = configured.get(key)
            definition = dict(base)
            if isinstance(configured_value, dict):
                definition.update(configured_value)

            raw_path = self._configured_path(configured_value) or definition.get("path")
            if not isinstance(raw_path, str) or not raw_path:
                raise ConfigurationError(f"source root {key!r} must define a path")
            if isinstance(configured_value, dict):
                relative_candidate = (
                    configured_value.get("relative_path")
                    or definition.get("relative_path")
                    or definition.get("path")
                )
            else:
                # A legacy string override supplies a compatibility path but
                # cannot change the reviewed canonical matching path.
                relative_candidate = base["path"]
            relative_path = self._normalise_source_path(
                relative_candidate
            )
            self._validate_source_root_path(relative_path, data_relative)
            source_system = definition.get("source_system")
            precedence = definition.get("precedence")
            if not isinstance(source_system, str) or not source_system:
                raise ConfigurationError(f"source root {key!r} must define a source system")
            if not isinstance(precedence, int):
                raise ConfigurationError(f"source root {key!r} must define precedence")
            enabled = definition.get("enabled", True)
            if not isinstance(enabled, bool):
                raise ConfigurationError(f"source root {key!r} enabled must be boolean")
            resolved_path = self.resolve_path(raw_path)
            if not _is_within(resolved_path, self.root) or not _is_within(
                resolved_path,
                self.data_dir,
            ):
                raise ConfigurationError(
                    f"source root must resolve inside data/: {raw_path!r}"
                )
            roots.append(
                SourceRoot(
                    key=key,
                    relative_path=relative_path,
                    source_system=source_system,
                    precedence=precedence,
                    enabled=enabled,
                    _resolved_path=resolved_path,
                )
            )

        for key, value in configured.items():
            if key in EXPLICIT_SOURCE_ROOTS:
                continue
            if not isinstance(value, dict):
                continue
            if "source_system" not in value or "precedence" not in value:
                continue
            raw_path = self._configured_path(value)
            if not raw_path:
                raise ConfigurationError(f"source root {key!r} must define a path")
            relative_path = self._normalise_source_path(
                value.get("relative_path") or raw_path
            )
            self._validate_source_root_path(relative_path, data_relative)
            source_system = value["source_system"]
            precedence = value["precedence"]
            enabled = value.get("enabled", True)
            if not isinstance(source_system, str) or not source_system:
                raise ConfigurationError(f"source root {key!r} must define a source system")
            if not isinstance(precedence, int):
                raise ConfigurationError(f"source root {key!r} must define precedence")
            if not isinstance(enabled, bool):
                raise ConfigurationError(f"source root {key!r} enabled must be boolean")
            resolved_path = self.resolve_path(raw_path)
            if not _is_within(resolved_path, self.root) or not _is_within(
                resolved_path,
                self.data_dir,
            ):
                raise ConfigurationError(
                    f"source root must resolve inside data/: {raw_path!r}"
                )
            roots.append(
                SourceRoot(
                    key=key,
                    relative_path=relative_path,
                    source_system=source_system,
                    precedence=precedence,
                    enabled=enabled,
                    _resolved_path=resolved_path,
                )
            )
        return tuple(sorted(roots, key=lambda root: (root.precedence, root.key)))

    def _load_legacy_source_roots(self, configured: Dict[str, Any]) -> Dict[str, SourceRoot]:
        source_systems = {
            "notes_onenote": "onenote",
            "notes_notion": "notion",
            "notes_capacities": "capacities",
            "notes_other": "other",
            "mcp_granola": "granola",
            "mcp_wispr_flow": "wispr_flow",
        }
        legacy: Dict[str, SourceRoot] = {}
        for key, value in configured.items():
            if key in EXPLICIT_SOURCE_ROOTS or not isinstance(value, str) or not value:
                continue
            relative_path = self._normalise_source_path(value)
            resolved_path = self.resolve_path(value)
            if not _is_within(resolved_path, self.root) or not _is_within(
                resolved_path,
                self.data_dir,
            ):
                raise ConfigurationError(
                    f"source root must resolve inside data/: {value!r}"
                )
            legacy[key] = SourceRoot(
                key=key,
                relative_path=relative_path,
                source_system=source_systems.get(key, "other"),
                precedence=100000,
                enabled=False,
                _resolved_path=resolved_path,
            )
        return legacy

    @staticmethod
    def _configured_path(value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            raw_path = value.get("path") or value.get("relative_path")
            return raw_path if isinstance(raw_path, str) else None
        return None

    @staticmethod
    def _normalise_source_path(value: Any) -> str:
        if not isinstance(value, str) or not value:
            raise ConfigurationError("source root path must be a non-empty string")
        raw = value.replace("\\", "/")
        if raw.startswith("/"):
            raise ConfigurationError(f"source root must be repository-relative: {value!r}")
        normalised = posixpath.normpath(raw)
        if normalised in {"", ".", ".."} or normalised.startswith("../"):
            raise ConfigurationError(f"source root escapes repository: {value!r}")
        return normalised

    @staticmethod
    def _validate_source_root_path(relative_path: str, data_relative: str) -> None:
        if relative_path != data_relative and not relative_path.startswith(data_relative + "/"):
            raise ConfigurationError(
                f"source root must be under data/: {relative_path}"
            )

    def _validate_derived_roots(self) -> None:
        if not _is_within(self.data_dir, self.root):
            raise ConfigurationError(
                f"data root must remain inside repository: {self.data_dir}"
            )
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
