#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "outbox_paths.example.json",
    "outbox_manual_checklist.md",
    "outbox_file_contract.md",
    "outbox_retention_policy.md",
    "outbox_rollback_plan.md",
    "outbox_apply_commands.example.sh",
}

SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\b"),
]
ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]
ACTIVE_DANGEROUS_PATTERNS = [
    re.compile(r"\bmkdir\s+"),
    re.compile(r"\btouch\s+"),
    re.compile(r"\bchmod\s+"),
    re.compile(r"\bchown\s+"),
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|reload|enable|disable)\b"),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart)\b"),
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
    re.compile(r"\bmarket_order\s*\("),
    re.compile(r"\blimit_order\s*\("),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Oracle outbox approval package.")
    parser.add_argument("--package", required=True, help="Package directory.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = verify_package(Path(args.package))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_package(package_dir: Path) -> dict[str, Any]:
    package = package_dir.expanduser().resolve()
    manifest_path = package / "manifest.json"
    errors: list[str] = []

    if not package.exists():
        return failure(f"package directory not found: {package}")
    if not manifest_path.exists():
        return failure(f"manifest.json not found in package: {package}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = {item["path"]: item for item in manifest.get("files", [])}
    missing_required = sorted(REQUIRED_FILES - set(manifest_files))
    if missing_required:
        errors.append(f"missing required manifest entries: {missing_required}")

    hash_failures = []
    for relative, entry in manifest_files.items():
        path = package / relative
        if not path.exists():
            errors.append(f"manifest file missing: {relative}")
            continue
        expected = entry.get("sha256")
        actual = sha256_file(path)
        if expected != actual:
            hash_failures.append({"path": relative, "expected": expected, "actual": actual})
    if hash_failures:
        errors.append("sha256 verification failed")

    scan_results = scan_package(package)
    if scan_results["secret_hits"]:
        errors.append("secret/private key/token marker found")
    if scan_results["order_true_hits"]:
        errors.append("order_execution_allowed true marker found")
    if scan_results["active_dangerous_hits"]:
        errors.append("active remote write/order/system command found")

    paths_payload = load_paths_payload(package / "outbox_paths.example.json", errors)
    if manifest.get("remote_delete") is not False:
        errors.append("manifest remote_delete must be false")
    if manifest.get("remote_move") is not False:
        errors.append("manifest remote_move must be false")
    if manifest.get("order_execution_allowed") is not False:
        errors.append("manifest order_execution_allowed must be false")
    if manifest.get("manual_approval_required") is not True:
        errors.append("manifest manual_approval_required must be true")
    if manifest.get("oracle_server_contacted") is not False:
        errors.append("manifest oracle_server_contacted must be false")
    if paths_payload:
        if paths_payload.get("remote_delete") is not False:
            errors.append("outbox paths remote_delete must be false")
        if paths_payload.get("remote_move") is not False:
            errors.append("outbox paths remote_move must be false")
        if paths_payload.get("order_execution_allowed") is not False:
            errors.append("outbox paths order_execution_allowed must be false")

    return {
        "status": "failed" if errors else "ok",
        "package_path": str(package),
        "manifest_path": str(manifest_path),
        "file_count": len(manifest_files),
        "missing_required": missing_required,
        "hash_failures": hash_failures,
        "secret_hits": scan_results["secret_hits"],
        "order_true_hits": scan_results["order_true_hits"],
        "active_dangerous_hits": scan_results["active_dangerous_hits"],
        "errors": errors,
        "manual_approval_required": bool(manifest.get("manual_approval_required")),
        "remote_delete": False,
        "remote_move": False,
        "oracle_server_contacted": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def load_paths_payload(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"outbox_paths.example.json is invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append("outbox_paths.example.json must contain an object")
        return None
    return payload


def scan_package(package: Path) -> dict[str, list[dict[str, Any]]]:
    result = {
        "secret_hits": [],
        "order_true_hits": [],
        "active_dangerous_hits": [],
    }
    for path in sorted(package.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(package))
        add_pattern_hits(result["secret_hits"], SECRET_PATTERNS, relative, text)
        add_pattern_hits(result["order_true_hits"], ORDER_TRUE_PATTERNS, relative, text)
        if path.suffix in {".sh", ".service", ".txt"}:
            add_active_dangerous_hits(result["active_dangerous_hits"], relative, text)
    return result


def add_pattern_hits(target: list[dict[str, Any]], patterns: list[re.Pattern[str]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def add_active_dangerous_hits(target: list[dict[str, Any]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("echo ") or stripped.startswith("printf "):
            continue
        for pattern in ACTIVE_DANGEROUS_PATTERNS:
            if pattern.search(stripped):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def failure(message: str) -> dict[str, Any]:
    return {"status": "failed", "errors": [message], "order_execution_allowed": False}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
