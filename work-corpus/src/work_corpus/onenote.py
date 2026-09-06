from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import shlex
import shutil
from typing import Any, Dict, Optional, Sequence, Tuple

from .config import Config
from .util import (
    atomic_write_json,
    atomic_write_text,
    now_iso,
    read_json,
    read_text_guess,
    run_command,
    scrub_derived_text,
    slugify,
)


ADAPTER_VERSION = "v2"
PARSER_NAME = "onenote_exporter:v1"
TERMINATOR_NODE_WORKAROUND = "tolerant-binary-terminator-v2"


@dataclass(frozen=True)
class ConverterSpec:
    command: Tuple[str, ...]
    root: Optional[Path]
    version: str


@dataclass
class OneNoteResult:
    status: str
    parser: str = PARSER_NAME
    parser_version: str = ADAPTER_VERSION
    text: str = ""
    locators: Tuple[str, ...] = ()
    error: str = ""
    output_path: Optional[str] = None
    converter: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _command_value(value: Any) -> list[str]:
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, (list, tuple)):
        return [str(part) for part in value]
    return []


def _configured_version(config: Config) -> str:
    configured = (
        config.get("onenote", "converter_version", "")
        or os.environ.get("ONENOTE_CONVERTER_VERSION", "")
    )
    return str(configured).strip() or "configured-unknown"


def _resolve_command(
    parts: Sequence[str],
    root: Optional[Path],
) -> Optional[Tuple[str, ...]]:
    if not parts:
        return None
    command = list(parts)
    first = Path(command[0]).expanduser()
    if not first.is_absolute() and root is not None:
        rooted = root / first
        if rooted.exists():
            command[0] = str(rooted)
            first = rooted
    if first.is_file() and os.access(first, os.X_OK):
        return tuple(command)
    if shutil.which(command[0]):
        return tuple(command)
    return None


def configured_converter(config: Config) -> Optional[ConverterSpec]:
    """Resolve a configured local command without touching any OneNote payload."""
    section = config.section("onenote")
    raw_root = (
        section.get("converter_root")
        or section.get("root")
        or os.environ.get("ONENOTE_CONVERTER_ROOT", "")
    )
    root: Optional[Path] = None
    if raw_root:
        root = Path(str(raw_root)).expanduser()
        if not root.is_dir():
            return None

    raw_command = (
        section.get("converter_command")
        or section.get("command")
        or os.environ.get("ONENOTE_CONVERTER_COMMAND", "")
    )
    parts = _command_value(raw_command)
    if not parts and root is not None:
        for candidate in (
            root / "bin" / "onenote-exporter",
            root / "onenote-exporter",
            root / "onenote_exporter",
            root / "onenote_exporter.py",
        ):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                parts = [str(candidate)]
                break

    command = _resolve_command(parts, root)
    if command is None:
        return None
    return ConverterSpec(command=command, root=root, version=_configured_version(config))


def _record_converter(config: Config, spec: ConverterSpec) -> Dict[str, Any]:
    path = config.state_dir / "tool_versions.json"
    config.assert_derived_path(path)
    payload = read_json(path, default={})
    if not isinstance(payload, dict):
        payload = {}
    tools = payload.setdefault("tools", {})
    if not isinstance(tools, dict):
        tools = {}
        payload["tools"] = tools
    record = {
        "adapter_version": ADAPTER_VERSION,
        "command": list(spec.command),
        "root": str(spec.root) if spec.root else "",
        "version": spec.version,
        "recorded_at": now_iso(),
        "local_only": True,
        "terminator_node_workaround": TERMINATOR_NODE_WORKAROUND,
    }
    tools["onenote"] = record
    atomic_write_json(path, payload)
    return record


def _locators(text: str) -> Tuple[str, ...]:
    found: list[str] = []
    section_number = 0
    page_number = 0
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped.casefold().startswith("section:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                locator = f"section:{value}"
                if locator not in found:
                    found.append(locator)
        elif stripped.casefold().startswith("page:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                locator = f"page:{value}"
                if locator not in found:
                    found.append(locator)
        elif stripped.casefold().startswith("page "):
            value = stripped.split(None, 1)[1].strip()
            if value:
                locator = f"page:{value}"
                if locator not in found:
                    found.append(locator)
        elif stripped.casefold() == "page":
            page_number += 1
            found.append(f"page:{page_number}")
        elif stripped.casefold() == "section":
            section_number += 1
            found.append(f"section:{section_number}")
    return tuple(found)


def _format_command(
    spec: ConverterSpec,
    source_path: Path,
    output_path: Path,
) -> list[str]:
    values = {
        "input": str(source_path),
        "output": str(output_path),
        "output_path": str(output_path),
        "output_dir": str(output_path.parent),
        "format": "markdown",
    }
    try:
        return [part.format(**values) for part in spec.command]
    except KeyError as exc:
        raise RuntimeError(
            f"unsupported OneNote command placeholder: {exc.args[0]}"
        ) from exc


def convert_one(
    config: Config,
    source_path: Path,
    *,
    output_path: Optional[Path] = None,
) -> OneNoteResult:
    """Convert one OneNote file through an explicitly configured local command."""
    spec = configured_converter(config)
    if spec is None:
        return OneNoteResult(
            status="blocked",
            error=(
                "local OneNote converter is not configured or unavailable; "
                "the OneNote payload was not read"
            ),
            metadata={
                "adapter_version": ADAPTER_VERSION,
                "terminator_node_workaround": TERMINATOR_NODE_WORKAROUND,
            },
        )

    output = output_path or (
        config.state_dir
        / "tmp"
        / f"onenote-{slugify(source_path.stem)}-{os.getpid()}.md"
    )
    config.assert_derived_path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    converter_record = _record_converter(config, spec)
    try:
        command = _format_command(spec, source_path, output)
        code, stdout, stderr = run_command(command, timeout=None)
        if code != 0:
            raise RuntimeError(
                f"local OneNote converter failed: {(stderr or stdout).strip()}"
            )
        if not output.is_file():
            raise RuntimeError("local OneNote converter did not create its output")
        text = scrub_derived_text(read_text_guess(output))
        if not text.strip():
            raise RuntimeError("local OneNote converter produced empty output")
        atomic_write_text(output, text)
        return OneNoteResult(
            status="succeeded",
            text=text,
            locators=_locators(text),
            output_path=str(output),
            converter=converter_record,
            metadata={
                "adapter_version": ADAPTER_VERSION,
                "terminator_node_workaround": TERMINATOR_NODE_WORKAROUND,
            },
        )
    except Exception as exc:
        return OneNoteResult(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            output_path=str(output) if output.exists() else None,
            converter=converter_record,
            metadata={
                "adapter_version": ADAPTER_VERSION,
                "terminator_node_workaround": TERMINATOR_NODE_WORKAROUND,
            },
        )
    finally:
        if output_path is None and output.exists():
            try:
                output.unlink()
            except OSError:
                pass
