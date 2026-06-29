from __future__ import annotations

import csv
import json
import re
from io import StringIO
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

from .database import PROJECT_ROOT
from .repository import now_iso


UPLOAD_ROOT = PROJECT_ROOT / "data" / "uploads"
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log", ".pdf"}
TEXT_EXTENSIONS = {".txt", ".md", ".log"}
MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_CONTEXT_SUMMARY_CHARS = 2400


class FileContextError(ValueError):
    """Raised when an uploaded context file is invalid or unsupported."""


def build_context_file_record(
    meeting_id: str,
    filename: str,
    data: bytes,
    upload_root: str | Path | None = None,
) -> dict:
    safe_name = sanitize_filename(filename)
    extension = Path(safe_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise FileContextError(f"Unsupported file extension '{extension}'. Allowed: {allowed}")
    if len(data) > MAX_UPLOAD_BYTES:
        limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise FileContextError(f"File is too large. Maximum size is {limit_mb}MB")
    if not data:
        raise FileContextError("Uploaded file is empty")

    file_id = uuid4().hex
    meeting_dir = Path(upload_root or UPLOAD_ROOT) / meeting_id
    meeting_dir.mkdir(parents=True, exist_ok=True)
    stored_path = meeting_dir / f"{file_id}_{safe_name}"

    if extension == ".pdf":
        stored_path.write_bytes(data)
        summary = (
            f"{safe_name}: PDF upload stored, but PDF text extraction is not implemented in Phase 3. "
            "TODO: add a dedicated PDF parser before using PDF content as council context."
        )
        return {
            "id": file_id,
            "meeting_id": meeting_id,
            "original_filename": safe_name,
            "stored_path": str(stored_path),
            "file_type": extension.lstrip("."),
            "file_size": len(data),
            "extracted_text_path": None,
            "summary": summary,
            "status": "unsupported",
            "created_at": now_iso(),
        }

    text = decode_text_file(data)
    extracted_text, summary = parse_context_text(safe_name, extension, text)
    extracted_path = meeting_dir / f"{file_id}_extracted.txt"
    summary_path = meeting_dir / f"{file_id}_summary.txt"
    stored_path.write_bytes(data)
    extracted_path.write_text(extracted_text, encoding="utf-8")
    summary_path.write_text(summary, encoding="utf-8")
    return {
        "id": file_id,
        "meeting_id": meeting_id,
        "original_filename": safe_name,
        "stored_path": str(stored_path),
        "file_type": extension.lstrip("."),
        "file_size": len(data),
        "extracted_text_path": str(extracted_path),
        "summary": summary,
        "status": "ready",
        "created_at": now_iso(),
    }


def sanitize_filename(filename: str) -> str:
    raw = (filename or "").replace("\\", "/")
    name = Path(raw).name.strip()
    if not name or name in {".", ".."}:
        raise FileContextError("Filename is required")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._")
    if not name:
        raise FileContextError("Filename does not contain safe characters")
    return name[:120]


def decode_text_file(data: bytes) -> str:
    sample = data[:4096]
    if b"\x00" in sample:
        raise FileContextError("Binary files are not accepted for this file type")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise FileContextError("File must be UTF-8 text") from exc


def parse_context_text(filename: str, extension: str, text: str) -> tuple[str, str]:
    if extension in TEXT_EXTENSIONS:
        return text, _plain_text_summary(filename, text)
    if extension == ".csv":
        return _csv_summary(filename, text)
    if extension == ".json":
        return _json_summary(filename, text)
    raise FileContextError(f"Parser is not implemented for '{extension}'")


def read_extracted_text(record: dict, max_chars: int = 20000) -> str:
    path = record.get("extracted_text_path")
    if not path:
        return ""
    extracted_path = Path(path)
    if not extracted_path.exists():
        return ""
    return extracted_path.read_text(encoding="utf-8")[:max_chars]


def remove_context_file_artifacts(record: dict, upload_root: str | Path | None = None) -> None:
    root = Path(upload_root or UPLOAD_ROOT).resolve()
    paths = [
        record.get("stored_path"),
        record.get("extracted_text_path"),
    ]
    extracted = record.get("extracted_text_path")
    if extracted:
        paths.append(str(Path(extracted).with_name(Path(extracted).name.replace("_extracted.txt", "_summary.txt"))))
    for raw_path in paths:
        if not raw_path:
            continue
        path = Path(raw_path)
        resolved = path.resolve()
        if path.exists() and (root == resolved or root in resolved.parents):
            path.unlink()


def build_meeting_context_summary(context_files: list[dict]) -> str:
    ready_files = [file for file in context_files if file.get("status") == "ready"]
    unsupported_files = [file for file in context_files if file.get("status") != "ready"]
    if not context_files:
        return "No attached context files."
    lines = [
        f"{len(context_files)} attached context file(s); {len(ready_files)} ready for analysis.",
    ]
    for file in context_files:
        lines.append(f"- {file['original_filename']} ({file['file_type']}, {file['status']}): {file['summary']}")
    if unsupported_files:
        lines.append("Unsupported files were stored but excluded from evidence-based analysis.")
    return "\n".join(lines)[:MAX_CONTEXT_SUMMARY_CHARS]


def _plain_text_summary(filename: str, text: str) -> str:
    lines = text.splitlines()
    excerpt = _compact(" ".join(line.strip() for line in lines if line.strip()))[:700]
    return (
        f"{filename}: plain text context with {len(lines)} line(s), {len(text)} character(s). "
        f"Excerpt: {excerpt or 'No non-empty text found.'}"
    )[:MAX_CONTEXT_SUMMARY_CHARS]


def _csv_summary(filename: str, text: str) -> tuple[str, str]:
    reader = csv.DictReader(StringIO(text))
    columns = reader.fieldnames or []
    rows = list(reader)
    sample_rows = rows[:5]
    numeric_summary = _numeric_summary(rows, columns)
    extracted = json.dumps(
        {
            "filename": filename,
            "columns": columns,
            "row_count": len(rows),
            "sample_rows": sample_rows,
            "numeric_summary": numeric_summary,
        },
        indent=2,
        sort_keys=True,
    )
    summary = (
        f"{filename}: CSV with {len(columns)} column(s) and {len(rows)} row(s). "
        f"Columns: {', '.join(columns) or 'none'}. "
        f"Sample rows: {json.dumps(sample_rows[:2], ensure_ascii=False)}. "
        f"Numeric summary: {json.dumps(numeric_summary, ensure_ascii=False)}."
    )
    return extracted, summary[:MAX_CONTEXT_SUMMARY_CHARS]


def _json_summary(filename: str, text: str) -> tuple[str, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FileContextError("JSON file is not valid JSON") from exc
    extracted = json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)
    structure = _describe_json_structure(parsed)
    if isinstance(parsed, dict):
        keys = list(parsed.keys())
        sample = {key: parsed[key] for key in keys[:5]}
        summary = (
            f"{filename}: JSON object with {len(keys)} top-level key(s). "
            f"Keys: {', '.join(map(str, keys[:12])) or 'none'}. "
            f"Structure: {structure}. Sample: {json.dumps(sample, ensure_ascii=False)[:800]}"
        )
    elif isinstance(parsed, list):
        summary = (
            f"{filename}: JSON array with {len(parsed)} item(s). "
            f"Structure: {structure}. Sample: {json.dumps(parsed[:3], ensure_ascii=False)[:800]}"
        )
    else:
        summary = f"{filename}: JSON scalar. Structure: {structure}. Value sample: {str(parsed)[:500]}"
    return extracted, summary[:MAX_CONTEXT_SUMMARY_CHARS]


def _numeric_summary(rows: list[dict], columns: list[str]) -> dict:
    summary = {}
    for column in columns:
        values = []
        for row in rows:
            value = (row.get(column) or "").strip()
            if value == "":
                continue
            try:
                values.append(float(value))
            except ValueError:
                continue
        if values:
            summary[column] = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": round(mean(values), 4),
            }
    return summary


def _describe_json_structure(value: Any, depth: int = 0) -> str:
    if depth >= 2:
        return type(value).__name__
    if isinstance(value, dict):
        items = list(value.items())[:6]
        inner = ", ".join(f"{key}: {_describe_json_structure(child, depth + 1)}" for key, child in items)
        return f"object({inner})"
    if isinstance(value, list):
        if not value:
            return "array(empty)"
        return f"array[{len(value)}]({_describe_json_structure(value[0], depth + 1)})"
    return type(value).__name__


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
