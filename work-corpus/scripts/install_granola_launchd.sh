#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/../.." && pwd -P)"
label="com.khamel83.work-corpus-granola-delta"
template="$repo_root/work-corpus/ops/launchd/$label.plist"
target="$HOME/Library/LaunchAgents/$label.plist"
python_bin="${WORK_CORPUS_PYTHON:-}"
if [[ -z "$python_bin" ]]; then
  for candidate in "$HOME"/.local/share/uv/python/cpython-3.12.*-macos-aarch64-none/bin/python3.12; do
    if [[ -x "$candidate" ]]; then
      python_bin="$candidate"
      break
    fi
  done
fi
if [[ -z "$python_bin" ]]; then
  python_bin="$(command -v python3 || true)"
fi

if [[ ! -f "$template" ]]; then
  echo "launchd template is missing: $template" >&2
  exit 1
fi
if [[ ! -x "$python_bin" ]]; then
  echo "WORK_CORPUS_PYTHON is not executable: $python_bin" >&2
  exit 1
fi
if [[ "$repo_root$HOME$python_bin" == *"|"* ]]; then
  echo "paths containing | are not supported by this installer" >&2
  exit 1
fi

mkdir -p "$(dirname "$target")"
mkdir -p "$HOME/Library/Logs"
temporary_path="$(mktemp "${TMPDIR:-/tmp}/$label.XXXXXX")"
trap 'rm -f "$temporary_path"' EXIT

sed \
  -e "s|__TROJANHORSE_ROOT__|$repo_root|g" \
  -e "s|__HOME__|$HOME|g" \
  -e "s|__WORK_CORPUS_PYTHON__|$python_bin|g" \
  "$template" > "$temporary_path"

if /usr/bin/grep -q '__[A-Z_][A-Z_]*__' "$temporary_path"; then
  echo "launchd template still contains unresolved placeholders" >&2
  exit 1
fi
if ! command -v plutil >/dev/null 2>&1; then
  echo "plutil is required on macOS" >&2
  exit 1
fi
plutil -lint "$temporary_path" >/dev/null
install -m 600 "$temporary_path" "$target"

domain="gui/$(id -u)"
launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
launchctl enable "$domain/$label"
launchctl bootstrap "$domain" "$target"

echo "installed and scheduled $label"
echo "plist: $target"
