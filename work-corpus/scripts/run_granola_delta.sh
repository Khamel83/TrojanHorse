#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
python_bin="${WORK_CORPUS_PYTHON:-python3}"
granola_key="$(secrets get GRANOLA_API_KEY)"

if [[ -z "$granola_key" ]]; then
  echo "GRANOLA_API_KEY is not available from secrets" >&2
  exit 1
fi

export GRANOLA_API_KEY="$granola_key"
export PYTHONPATH="$repo_root/work-corpus/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$python_bin" -m work_corpus.granola_delta --root "$repo_root"
