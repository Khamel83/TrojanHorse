from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import Config
from .util import (
    atomic_write_text,
    now_iso,
    provenance_header,
    read_text_guess,
    stable_id,
    write_csv,
)


def _first(obj: Dict[str, Any], names: Iterable[str], default: Any = "") -> Any:
    for name in names:
        if name in obj and obj[name] not in (None, ""):
            return obj[name]
    return default


def _content_from_obj(obj: Dict[str, Any]) -> str:
    value = _first(
        obj,
        (
            "transcript", "text", "content", "notes", "summary",
            "description", "body", "raw_text",
        ),
        "",
    )
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False)


def _flatten_records(path: Path) -> List[Dict[str, Any]]:
    ext = path.suffix.lower()
    if ext in {".md", ".markdown", ".txt"}:
        return [{
            "external_id": "",
            "title": path.stem,
            "event_date": "",
            "content": read_text_guess(path),
            "source_uri": "",
            "fetched_at": "",
        }]

    if ext == ".jsonl":
        records: List[Dict[str, Any]] = []
        for line in read_text_guess(path).splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
        return records

    if ext == ".json":
        payload = json.loads(read_text_guess(path))
        if isinstance(payload, list):
            return [obj for obj in payload if isinstance(obj, dict)]
        if isinstance(payload, dict):
            for key in ("meetings", "notes", "items", "results", "data", "value"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [obj for obj in value if isinstance(obj, dict)]
            return [payload]
    return []


def ingest_mcp_sources(config: Config, con: sqlite3.Connection) -> Dict[str, int]:
    rows = con.execute(
        """
        SELECT *
        FROM source_item
        WHERE status='present'
          AND source_system IN ('granola', 'wispr_flow')
          AND extension IN ('.json','.jsonl','.md','.markdown','.txt')
        ORDER BY source_system, relative_path
        """
    ).fetchall()

    result = {"items": 0, "source_files": 0, "errors": 0}
    errors: List[str] = []

    for row in rows:
        path = Path(row["absolute_path"])
        provider = row["source_system"]
        try:
            records = _flatten_records(path)
        except Exception as exc:
            result["errors"] += 1
            errors.append(f"{path}: {type(exc).__name__}: {exc}")
            continue

        for index, obj in enumerate(records):
            if "content" in obj and set(obj).issubset(
                {"external_id", "title", "event_date", "content", "source_uri", "fetched_at"}
            ):
                external_id = str(obj.get("external_id") or "")
                title = str(obj.get("title") or path.stem)
                event_date = str(obj.get("event_date") or "")
                content = str(obj.get("content") or "")
                source_uri = str(obj.get("source_uri") or "")
                fetched_at = str(obj.get("fetched_at") or "")
            else:
                external_id = str(_first(obj, ("id", "meeting_id", "note_id", "uuid", "external_id"), ""))
                title = str(_first(obj, ("title", "name", "topic", "meeting_title"), path.stem))
                event_date = str(
                    _first(
                        obj,
                        ("date", "event_date", "meeting_date", "start_time", "created_at", "updated_at"),
                        "",
                    )
                )
                content = _content_from_obj(obj)
                source_uri = str(_first(obj, ("source_uri", "uri", "url", "meeting_uri"), ""))
                fetched_at = str(_first(obj, ("fetched_at", "retrieved_at", "ingested_at"), ""))

            item_id = stable_id(
                "mcp",
                provider,
                external_id or row["source_id"],
                index,
                title,
                event_date,
            )
            output = config.corpus_dir / "mcp" / provider / f"{item_id}.md"
            header = provenance_header({
                "source_id": row["source_id"],
                "source_system": provider,
                "original_path": row["absolute_path"],
                "relative_path": row["relative_path"],
                "original_date": event_date,
                "file_type": "mcp_item",
                "parser": "mcp_generic",
                "generated_at": now_iso(),
            })
            text = "\n".join([
                header,
                f"# {title}",
                "",
                f"- **Provider:** {provider}",
                f"- **External ID:** {external_id}",
                f"- **Event date:** {event_date}",
                f"- **Source URI:** {source_uri}",
                f"- **Fetched at:** {fetched_at}",
                "",
                "## Content",
                "",
                content.strip(),
                "",
            ])
            atomic_write_text(output, text)

            con.execute(
                """
                INSERT INTO mcp_item (
                    item_id, source_id, provider, external_id, title, event_date,
                    normalized_path, source_uri, fetched_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    source_id=excluded.source_id,
                    provider=excluded.provider,
                    external_id=excluded.external_id,
                    title=excluded.title,
                    event_date=excluded.event_date,
                    normalized_path=excluded.normalized_path,
                    source_uri=excluded.source_uri,
                    fetched_at=excluded.fetched_at,
                    updated_at=excluded.updated_at
                """,
                (
                    item_id,
                    row["source_id"],
                    provider,
                    external_id,
                    title,
                    event_date,
                    str(output),
                    source_uri,
                    fetched_at,
                    now_iso(),
                ),
            )
            result["items"] += 1
        result["source_files"] += 1

    con.commit()

    index_rows = [
        dict(row)
        for row in con.execute(
            """
            SELECT item_id, provider, external_id, title, event_date,
                   normalized_path, source_uri, fetched_at, source_id
            FROM mcp_item
            ORDER BY provider, event_date DESC, title
            """
        )
    ]
    write_csv(
        config.corpus_dir / "reports" / "mcp_index.csv",
        index_rows,
        [
            "item_id", "provider", "external_id", "title", "event_date",
            "normalized_path", "source_uri", "fetched_at", "source_id",
        ],
    )
    (config.state_dir / "mcp_ingest_errors.txt").write_text(
        "\n".join(errors) + ("\n" if errors else ""),
        encoding="utf-8",
    )
    return result
