#!/usr/bin/env python3
"""Persist a connected-source response as an immutable local MCP snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROVIDERS = {"granola", "wispr_flow"}
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,120}$")


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    parser.add_argument("--capture-id", required=True)
    parser.add_argument("--records-key", required=True, choices=("meetings", "notes"))
    args = parser.parse_args()

    if not SAFE_ID.fullmatch(args.capture_id):
        raise SystemExit("capture-id contains unsafe characters")

    chunks: list[bytes] = []
    for line in sys.stdin.buffer:
        if line.strip() == b"__MCP_CAPTURE_EOF__":
            break
        chunks.append(line.rstrip(b"\r\n"))
    raw_input = b"".join(chunks)
    if b"\x04" in raw_input:
        raw_input = raw_input.split(b"\x04", 1)[0]
    payload = json.loads(raw_input.decode("utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("capture payload must be a JSON object")
    records = payload.get(args.records_key)
    if not isinstance(records, list):
        raise SystemExit(f"capture payload must contain a {args.records_key} list")

    root = args.root.expanduser().resolve()
    source_dir = root / "data" / "mcp" / args.provider
    state_dir = root / "work-corpus" / "state" / "mcp"
    snapshot_path = source_dir / f"{args.capture_id}.json"
    capture = {
        "schema_version": 1,
        "provider": args.provider,
        "capture_id": args.capture_id,
        "captured_at": payload.get("captured_at")
        or datetime.now(timezone.utc).isoformat(),
        args.records_key: records,
        "_capture": {
            "requests": payload.get("requests", []),
            "account": payload.get("account", {}),
            "raw_responses": payload.get("raw_responses", []),
            "retrieval_notes": payload.get("retrieval_notes", []),
        },
    }
    _atomic_json(snapshot_path, capture)

    encoded = snapshot_path.read_bytes()
    raw_responses = capture["_capture"]["raw_responses"]
    response_hashes = [
        _sha256_bytes(str(value).encode("utf-8"))
        for value in raw_responses
    ]
    manifest_path = state_dir / f"{args.provider}_capture_manifest.jsonl"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "capture_id": args.capture_id,
        "provider": args.provider,
        "captured_at": capture["captured_at"],
        "snapshot": str(snapshot_path),
        "snapshot_sha256": _sha256_bytes(encoded),
        "records_key": args.records_key,
        "record_count": len(records),
        "raw_response_count": len(raw_responses),
        "raw_response_sha256": response_hashes,
        "requests": capture["_capture"]["requests"],
    }
    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "snapshot": str(snapshot_path),
                "manifest": str(manifest_path),
                "record_count": len(records),
                "snapshot_sha256": entry["snapshot_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
