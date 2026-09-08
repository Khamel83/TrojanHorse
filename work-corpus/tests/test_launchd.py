from __future__ import annotations

from pathlib import Path
import plistlib


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "work-corpus" / "ops" / "launchd" / "com.khamel83.work-corpus-granola-delta.plist"
INSTALLER = ROOT / "work-corpus" / "scripts" / "install_granola_launchd.sh"


def test_granola_launchd_template_runs_the_local_delta_every_five_minutes() -> None:
    payload = plistlib.loads(TEMPLATE.read_bytes())

    assert payload["Label"] == "com.khamel83.work-corpus-granola-delta"
    assert payload["ProgramArguments"] == [
        "/bin/bash",
        "-c",
        'key="$(/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=8 homelab secrets get GRANOLA_API_KEY)" || exit 1; [ -n "$key" ] || exit 1; export GRANOLA_API_KEY="$key"; exec "$1" -m "$2" --root "$3"',
        "work-corpus-granola-delta",
        "__WORK_CORPUS_PYTHON__",
        "work_corpus.granola_delta",
        "__TROJANHORSE_ROOT__",
    ]
    assert "WorkingDirectory" not in payload
    assert payload["RunAtLoad"] is True
    assert payload["StartInterval"] == 300
    assert payload["ThrottleInterval"] == 60
    assert payload["EnvironmentVariables"] == {
        "HOME": "__HOME__",
        "PATH": "__HOME__/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "__TROJANHORSE_ROOT__/work-corpus/src",
        "WORK_CORPUS_PYTHON": "__WORK_CORPUS_PYTHON__",
    }
    assert payload["StandardOutPath"] == "__HOME__/Library/Logs/work-corpus-granola-delta.out.log"
    assert payload["StandardErrorPath"] == "__HOME__/Library/Logs/work-corpus-granola-delta.err.log"


def test_launchd_template_does_not_store_the_granola_secret() -> None:
    text = TEMPLATE.read_text(encoding="utf-8")

    assert "GRANOLA_API_KEY" in text
    assert "grn_" not in text


def test_launchd_installer_renders_and_bootstraps_the_job() -> None:
    text = INSTALLER.read_text(encoding="utf-8")

    assert "plutil -lint" in text
    assert "launchctl bootstrap" in text
    assert "launchctl enable" in text
    assert text.index("launchctl enable") < text.index("launchctl bootstrap")
    assert "launchctl kickstart" not in text
    assert "GRANOLA_API_KEY" not in text
    assert "cpython-3.12.*-macos-aarch64-none/bin/python3.12" in text
