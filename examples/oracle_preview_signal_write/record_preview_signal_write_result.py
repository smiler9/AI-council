#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIGNAL = ROOT / "tmp" / "oracle_preview_signal_write" / "us_trader_preview_signal.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_signal_write" / "signal_write_result.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)
SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\b"),
]
IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a sanitized Oracle preview signal write result.")
    parser.add_argument("--input", help="Optional JSON signal write result input to sanitize and normalize.")
    parser.add_argument("--signal", default=str(DEFAULT_SIGNAL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--result-status", choices=["passed", "warning", "failed", "incomplete"], default="passed")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        payload = load_or_build_payload(args)
        sanitized = sanitize_payload(payload)
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(sanitized, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "result_path": str(output),
            "result_status": sanitized["result_status"],
            "file_uploaded_manually": sanitized["observations"]["file_uploaded_manually"],
            "systemd_changed": sanitized["safety"]["systemd_changed"],
            "live_bot_modified": sanitized["safety"]["live_bot_modified"],
            "broker_api_called": sanitized["safety"]["broker_api_called"],
            "order_execution_allowed": False,
        }
        if any(
            sanitized["safety"].get(key) is True
            for key in ["systemd_changed", "live_bot_modified", "penny_stock_bot_modified", "secrets_exposed", "broker_api_called"]
        ):
            result["status"] = "warning" if sanitized["result_status"] != "failed" else "failed"
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] in {"ok", "warning"} else 1


def load_or_build_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input:
        input_path = Path(args.input).expanduser().resolve()
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input JSON must contain an object")
        return payload
    return sample_result(Path(args.signal), result_status=args.result_status)


def sample_result(signal_path: Path, *, result_status: str) -> dict[str, Any]:
    signal = load_signal(signal_path)
    path = signal_path.expanduser().resolve()
    return {
        "result_status": result_status,
        "manual_operator": "<manual-operator>",
        "written_at": datetime.now(timezone.utc).isoformat(),
        "oracle_target": {
            "host": "<oracle-host>",
            "user": "<oracle-user>",
            "outbox_dir": "<oracle-outbox-dir>",
        },
        "signal_file": {
            "filename": "us_trader_preview_signal.json",
            "signal_id": signal.get("signal_id", "<signal-id>"),
            "sha256": sha256_file(path) if path.exists() else "<sha256>",
            "size_bytes": path.stat().st_size if path.exists() else 0,
        },
        "observations": {
            "file_uploaded_manually": True,
            "file_exists_in_outbox": True,
            "file_readable": True,
            "file_json_valid": True,
            "post_write_verify_readonly_only": True,
        },
        "safety": {
            "systemd_changed": False,
            "live_bot_modified": False,
            "penny_stock_bot_modified": False,
            "secrets_exposed": False,
            "broker_api_called": False,
            "order_execution_allowed": False,
        },
        "notes": ["Sample local record only. Do not store secret values."],
        "next_step_requested": "mac_pull_actual_preview_signal_rehearsal",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def load_signal(signal_path: Path) -> dict[str, Any]:
    path = signal_path.expanduser().resolve()
    if not path.exists():
        return {"signal_id": "<signal-id>"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"signal_id": "<signal-id>"}


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("secret/private key/token marker found in input")
    sanitized = json.loads(json.dumps(payload))
    sanitized.setdefault("result_status", "incomplete")
    sanitized.setdefault("manual_operator", "<manual-operator>")
    sanitized.setdefault("written_at", datetime.now(timezone.utc).isoformat())
    sanitized.setdefault("oracle_target", {})
    sanitized["oracle_target"]["host"] = sanitize_identifier(str(sanitized["oracle_target"].get("host", "<oracle-host>")), "<oracle-host>")
    sanitized["oracle_target"]["user"] = sanitize_identifier(str(sanitized["oracle_target"].get("user", "<oracle-user>")), "<oracle-user>")
    sanitized["oracle_target"]["outbox_dir"] = sanitize_path(str(sanitized["oracle_target"].get("outbox_dir", "<oracle-outbox-dir>")))
    sanitized.setdefault("signal_file", {})
    sanitized["signal_file"].setdefault("filename", "us_trader_preview_signal.json")
    sanitized["signal_file"].setdefault("signal_id", "<signal-id>")
    sanitized["signal_file"].setdefault("sha256", "<sha256>")
    sanitized["signal_file"].setdefault("size_bytes", 0)
    sanitized.setdefault("observations", {})
    sanitized.setdefault("safety", {})
    for key in ["file_uploaded_manually", "file_exists_in_outbox", "file_readable", "file_json_valid"]:
        sanitized["observations"][key] = bool(sanitized["observations"].get(key, False))
    sanitized["observations"]["post_write_verify_readonly_only"] = bool(
        sanitized["observations"].get("post_write_verify_readonly_only", True)
    )
    for key in ["systemd_changed", "live_bot_modified", "penny_stock_bot_modified", "secrets_exposed", "broker_api_called"]:
        sanitized["safety"][key] = bool(sanitized["safety"].get(key, False))
    sanitized["safety"]["order_execution_allowed"] = False
    sanitized.setdefault("notes", [])
    sanitized["next_step_requested"] = "mac_pull_actual_preview_signal_rehearsal"
    sanitized["safety_boundary"] = SAFETY_BOUNDARY
    return sanitized


def sanitize_identifier(value: str, placeholder: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    if IP_PATTERN.search(value):
        return placeholder
    return value


def sanitize_path(value: str) -> str:
    if value.startswith("<") and value.endswith(">"):
        return value
    if "/.ssh/" in value or value.startswith("/Users/"):
        return "<redacted-path>"
    if IP_PATTERN.search(value):
        return "<redacted-path>"
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
