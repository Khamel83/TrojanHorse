from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from typing import Dict, List, Tuple

from .config import Config
from .util import atomic_write_text, executable, now_iso, run_command


def _outlook_mode() -> str:
    if platform.system() != "Darwin":
        return "not-macOS"
    app = Path("/Applications/Microsoft Outlook.app")
    if not app.exists():
        return "not-installed"
    code, out, _err = run_command(
        ["/usr/bin/defaults", "read", "com.microsoft.Outlook", "IsRunningNewOutlook"],
        timeout=5,
    )
    if code == 0 and out.strip() == "1":
        return "new-outlook"
    if code == 0 and out.strip() == "0":
        return "legacy-outlook"
    return "unknown"


def doctor(config: Config) -> str:
    lines: List[str] = [
        "WORK CORPUS DOCTOR",
        "=" * 72,
        f"Generated: {now_iso()}",
        f"Project root: {config.root}",
        f"Python: {sys.version.splitlines()[0]}",
        f"Platform: {platform.platform()}",
        "",
        "PATHS",
        "-" * 72,
        f"data: {config.data_dir} (exists={config.data_dir.exists()})",
        f"corpus: {config.corpus_dir} (exists={config.corpus_dir.exists()})",
        f"state: {config.state_dir} (exists={config.state_dir.exists()})",
        "",
        "COMMANDS",
        "-" * 72,
    ]
    for name in ("ffmpeg", "ffprobe", "whisper-cli", "whisper", "osascript", "sdef"):
        lines.append(f"{name}: {executable(name) or 'not found'}")

    lines.extend(["", "OPTIONAL PYTHON MODULES", "-" * 72])
    for name in ("pypdf", "docx", "pptx", "openpyxl", "faster_whisper", "msal", "requests"):
        lines.append(f"{name}: {'available' if importlib.util.find_spec(name) else 'not installed'}")

    lines.extend(["", "OUTLOOK", "-" * 72])
    lines.append(f"mode: {_outlook_mode()}")
    lines.append(
        "Local AppleScript export is attempted only for legacy Outlook. "
        "New Outlook requires EML/MBOX/OLM export or permitted Microsoft Graph access."
    )

    lines.extend(["", "SECURITY", "-" * 72])
    lines.extend([
        "Core pipeline reads files under data/ and writes only to corpus/ and state/.",
        "No mailbox write scopes are requested.",
        "No Outlook cache, Keychain, browser cookie, token, or OST/HxStore extraction is included.",
    ])
    text = "\n".join(lines) + "\n"
    atomic_write_text(config.state_dir / "doctor.txt", text)
    return text
