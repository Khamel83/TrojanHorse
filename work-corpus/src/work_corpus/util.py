from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1")


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    ensure_dir(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
    finally:
        try:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_text_guess(path: Path, max_bytes: Optional[int] = None) -> str:
    size = path.stat().st_size
    if max_bytes is not None and size > max_bytes:
        raise ValueError(f"file exceeds configured text limit: {size} bytes")
    raw = path.read_bytes()
    for encoding in TEXT_ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


_SIGNED_URL_KEYS = re.compile(
    r"(?:"
    r"awsaccesskeyid|x-amz-(?:algorithm|credential|date|expires|security-token|signature)"
    r"|signature|sig|token|expires|se|sp|sr|st|sv"
    r")\s*=",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_QUOTED_SECRET_RE = re.compile(
    r"(?P<prefix>[\"']?\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
    r"client[_ -]?secret|secret[_ -]?key|client[_ -]?secret|token|credential|"
    r"secret|password|passwd|private[_ -]?key)\b[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.IGNORECASE | re.DOTALL,
)
_UNQUOTED_SECRET_RE = re.compile(
    r"(?P<prefix>[\"']?\b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|"
    r"client[_ -]?secret|secret[_ -]?key|client[_ -]?secret|token|credential|"
    r"secret|password|passwd|private[_ -]?key)\b[\"']?\s*[:=]\s*)"
    r"(?P<value>(?![\"'])[^\s,;]+)",
    re.IGNORECASE,
)
_AUTHORIZATION_RE = re.compile(
    r"(?P<prefix>\b(?:authorization\s*:\s*bearer|bearer)\s+)"
    r"(?P<value>[^\s,;]+)",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\bsk-[A-Za-z0-9_-]{20,}\b")


def scrub_derived_text(value: str) -> str:
    """Remove signed URLs and secret-like values from derived text only."""
    text = value

    def redact_url(match: re.Match[str]) -> str:
        candidate = match.group(0).rstrip(".,;)")
        query = candidate.split("?", 1)[1] if "?" in candidate else ""
        if query and _SIGNED_URL_KEYS.search(query):
            return "[REDACTED_SIGNED_URL]"
        return candidate

    text = _URL_RE.sub(redact_url, text)
    text = _QUOTED_SECRET_RE.sub(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}"
            "[REDACTED_SECRET]"
            f"{match.group('quote')}"
        ),
        text,
    )
    text = _UNQUOTED_SECRET_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED_SECRET]",
        text,
    )
    text = _AUTHORIZATION_RE.sub(
        lambda match: f"{match.group('prefix')}[REDACTED_SECRET]",
        text,
    )
    return _TOKEN_RE.sub("[REDACTED_SECRET]", text)


def scrub_fts_text(value: str) -> str:
    """Remove all URLs and secret-like values before FTS indexing."""
    text = scrub_derived_text(value)
    return _URL_RE.sub("[REDACTED_URL]", text)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _identity_digest(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def stable_source_id(root_key: str, relative_path: str) -> str:
    """Return the immutable identity of a physical source location."""
    return _identity_digest("source-file:v1", root_key, relative_path)


def stable_source_version_id(source_id: str, content_sha256: str) -> Optional[str]:
    """Return a content identity, or None until the file has been hashed."""
    if not content_sha256:
        return None
    return _identity_digest("source-version:v1", source_id, content_sha256)


def stable_evidence_id(source_version_id: str, locator: str) -> str:
    """Return the immutable identity of a locator within one source version."""
    if not source_version_id:
        raise ValueError("evidence requires a source version")
    return _identity_digest("evidence:v1", source_version_id, locator)


def stable_id(prefix: str, *parts: Any) -> str:
    basis = "\0".join("" if p is None else str(p) for p in parts)
    return prefix + "_" + hashlib.blake2b(basis.encode("utf-8"), digest_size=16).hexdigest()


def slugify(value: str, limit: int = 80) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    value = re.sub(r"-+", "-", value).strip("-._")
    return (value or "item")[:limit]


def safe_relpath(path: Path, root: Path) -> str:
    # Prefer the lexical path so a data/zoom symlink remains classified as
    # data/zoom rather than being rewritten to its external target.
    try:
        return path.absolute().relative_to(root.absolute()).as_posix()
    except Exception:
        pass
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False)).as_posix()
    except Exception:
        return path.resolve(strict=False).as_posix()


def human_bytes(value: int) -> str:
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if number < 1024 or unit == "PB":
            return f"{number:.1f} {unit}"
        number /= 1024
    return str(value)


def run_command(args: Sequence[str], timeout: Optional[int] = None, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except Exception as exc:
        return 1, "", str(exc)


def executable(name: str) -> Optional[str]:
    return shutil.which(name)


def parse_date_hint(value: str) -> str:
    patterns = (
        (r"(?<!\d)(20\d{2})[-_. ](0?[1-9]|1[0-2])[-_. ](0?[1-9]|[12]\d|3[01])(?!\d)", (1, 2, 3)),
        (r"(?<!\d)(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)", (1, 2, 3)),
        (r"(?<!\d)(0?[1-9]|1[0-2])[-_. ](0?[1-9]|[12]\d|3[01])[-_. ](20\d{2})(?!\d)", (3, 1, 2)),
    )
    for pattern, order in patterns:
        match = re.search(pattern, value)
        if not match:
            continue
        try:
            year = int(match.group(order[0]))
            month = int(match.group(order[1]))
            day = int(match.group(order[2]))
            return dt.date(year, month, day).isoformat()
        except ValueError:
            pass
    year_match = re.search(r"(?<!\d)(20\d{2})(?!\d)", value)
    return year_match.group(1) if year_match else ""


def detect_source_system(relative_path: str) -> str:
    low = relative_path.lower().replace("\\", "/")
    mapping = (
        ("granola", "granola"),
        ("wispr_flow", "wispr_flow"),
        ("wispr flow", "wispr_flow"),
        ("wisprflow", "wispr_flow"),
        ("capacities", "capacities"),
        ("notion", "notion"),
        ("onenote", "onenote"),
        ("one note", "onenote"),
        ("/zoom/", "zoom"),
        ("zoom_", "zoom"),
        ("outlook", "outlook"),
        ("/email/", "email"),
        ("performance review", "formal_records"),
        ("formal_records", "formal_records"),
        ("/inventory/", "inventory"),
        ("/databases/", "database_extract"),
    )
    padded = "/" + low.strip("/") + "/"
    for token, system in mapping:
        if token in low or token in padded:
            return system
    return "other"


MEDIA_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".opus", ".caf",
}
TRANSCRIPT_EXTENSIONS = {".vtt", ".srt"}
EMAIL_EXTENSIONS = {".eml", ".mbox", ".mbx"}
DOCUMENT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".rtf", ".html", ".htm", ".pdf",
    ".doc", ".docx", ".ppt", ".pptx",
}
TABLE_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
DATABASE_EXTENSIONS = {".sqlite", ".sqlite3", ".db"}
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar", ".olm", ".pst", ".ost", ".one", ".onepkg"}
JSON_EXTENSIONS = {".json", ".jsonl"}


def effective_extension(path: Path) -> str:
    """Return the real extension when macOS appended a duplicate suffix."""
    duplicate = re.search(r"(\.[A-Za-z0-9]+)\s+\(\d+\)$", path.name)
    if duplicate:
        return duplicate.group(1).casefold()
    return path.suffix.casefold()


def detect_kind(path: Path, source_system: str) -> str:
    ext = effective_extension(path)
    name = path.name.lower()
    if (
        source_system == "zoom"
        and name.startswith("client_config")
        and ext in {".json", ".xml", ".plist"}
    ):
        return "metadata"
    if ext in MEDIA_EXTENSIONS:
        return "media"
    if ext in TRANSCRIPT_EXTENSIONS:
        return "transcript"
    if ext in EMAIL_EXTENSIONS:
        return "email"
    if ext in TABLE_EXTENSIONS:
        return "table"
    if ext in DATABASE_EXTENSIONS:
        return "database"
    if ext in ARCHIVE_EXTENSIONS:
        return "archive"
    if ext in JSON_EXTENSIONS:
        if source_system in {"granola", "wispr_flow"}:
            return "mcp"
        if source_system in {"email", "outlook"}:
            return "email_data"
        return "structured_text"
    if ext in DOCUMENT_EXTENSIONS:
        if source_system == "zoom" and ("transcript" in name or "caption" in name or name.endswith(".txt")):
            return "transcript_candidate"
        return "document"
    if name in {"chat.txt", "meeting_saved_chat.txt"}:
        return "meeting_chat"
    return "unknown"


def quote_header_value(value: Any) -> str:
    text = "" if value is None else str(value)
    return json.dumps(text, ensure_ascii=False)


def provenance_header(metadata: Dict[str, Any]) -> str:
    lines = ["---"]
    for key in (
        "source_id", "source_version_id", "source_system", "original_path",
        "relative_path", "original_date", "source_date_basis", "file_type",
        "parser", "parser_version", "locator", "generated_at",
    ):
        if key in metadata:
            lines.append(f"{key}: {quote_header_value(metadata[key])}")
    lines.extend(["---", ""])
    return "\n".join(lines)


class _HTMLToText(HTMLParser):
    BLOCKS = {
        "p", "div", "section", "article", "header", "footer", "li", "ul", "ol",
        "table", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "br",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            return
        if self.skip_depth == 0 and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth == 0 and tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth == 0:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(value)
        text = "".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


TIMESTAMP_LINE = re.compile(
    r"^\s*(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}\s*-->\s*(?:\d{1,2}:)?\d{1,2}:\d{2}[.,]\d{3}"
)


def vtt_or_srt_to_markdown(text: str, title: str = "Transcript") -> str:
    lines = text.replace("\ufeff", "").splitlines()
    output = [f"# {title}", ""]
    current_stamp = ""
    current_text: List[str] = []

    def flush() -> None:
        nonlocal current_stamp, current_text
        body = " ".join(part.strip() for part in current_text if part.strip()).strip()
        body = re.sub(r"<[^>]+>", "", body)
        if body:
            output.append(f"**{current_stamp}**  " if current_stamp else "")
            output.append(body)
            output.append("")
        current_stamp = ""
        current_text = []

    for raw in lines:
        line = raw.strip()
        if not line or line == "WEBVTT" or line.startswith("NOTE"):
            flush()
            continue
        if line.isdigit() and not current_text:
            continue
        if TIMESTAMP_LINE.match(line):
            flush()
            current_stamp = line
            continue
        if line.startswith(("Kind:", "Language:")):
            continue
        current_text.append(line)
    flush()
    return "\n".join(output).strip() + "\n"


def canonical_subject(subject: str) -> str:
    value = subject or ""
    while True:
        new = re.sub(r"^\s*(re|fw|fwd)\s*:\s*", "", value, flags=re.I)
        if new == value:
            break
        value = new
    return re.sub(r"\s+", " ", value).strip().lower()


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
