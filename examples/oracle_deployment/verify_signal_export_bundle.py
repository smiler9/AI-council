#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_FILES = {
    "README.md",
    "ai_council_signal_exporter_module.py",
    "us_trader_signal_outbox_bridge.py",
    "mapping_profiles/us_trader_oracle_v1.json",
    "sample_outbox/us_trader_signal_001.json",
    "sample_outbox/us_trader_signal_order_like.json",
    "sample_outbox/us_trader_signal_high_risk.json",
    "oracle_env.example",
    "manual_apply_commands.example.sh",
    "sidecar_systemd_example.service",
    "sidecar_cron_example.txt",
}

SECRET_PATTERNS = [
    re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    re.compile(r"ssh-key-20\d{2}", re.IGNORECASE),
    re.compile(r"/Users/[^\\s'\"]*/\\.ssh/[^\\s'\"]+"),
    re.compile(r"\b168\.110\.101\.18\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
]

ORDER_TRUE_PATTERNS = [
    re.compile(r"order_execution_allowed\s*[:=]\s*true", re.IGNORECASE),
    re.compile(r'"order_execution_allowed"\s*:\s*true', re.IGNORECASE),
    re.compile(r"ORDER_EXECUTION_ALLOWED\s*=\s*true", re.IGNORECASE),
]

DANGEROUS_PATTERNS = [
    re.compile(r"\bsubmit_order\s*\("),
    re.compile(r"\bcreate_order\s*\("),
    re.compile(r"\bcancel_order\s*\("),
    re.compile(r"\bclose_position\s*\("),
    re.compile(r"\bmarket_order\s*\("),
    re.compile(r"\blimit_order\s*\("),
    re.compile(r"\bplace_order\s*\("),
    re.compile(r"\bcheck_exits\s*\("),
    re.compile(r"\bforce_close_all\s*\("),
    re.compile(r"\bsystemctl\s+(?:start|stop|restart|enable|disable)\b"),
    re.compile(r"\bservice\s+\S+\s+(?:start|stop|restart)\b"),
    re.compile(r"\bscp\s+"),
    re.compile(r"\brsync\s+"),
]

BROKER_CLIENT_PATTERNS = [
    re.compile(r"\balpaca_trade_api\b"),
    re.compile(r"\bib_insync\b"),
    re.compile(r"\bTradingClient\b"),
    re.compile(r"\bBrokerClient\b"),
    re.compile(r"\bOrderRequest\b"),
    re.compile(r"\bkis_order\b"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a local Oracle signal export bundle.")
    parser.add_argument("--bundle", required=True, help="Bundle directory.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = verify_bundle(Path(args.bundle))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    bundle = bundle_dir.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = bundle / "manifest.json"

    if not bundle.exists():
        return failure(f"bundle directory not found: {bundle}")
    if not manifest_path.exists():
        return failure(f"manifest.json not found in bundle: {bundle}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_files = {item["path"]: item for item in manifest.get("files", [])}
    missing_required = sorted(REQUIRED_FILES - set(manifest_files))
    if missing_required:
        errors.append(f"missing required manifest entries: {missing_required}")

    hash_failures = []
    for relative, entry in manifest_files.items():
        path = bundle / relative
        if not path.exists():
            errors.append(f"manifest file missing: {relative}")
            continue
        expected = entry.get("sha256")
        actual = sha256_file(path)
        if expected != actual:
            hash_failures.append({"path": relative, "expected": expected, "actual": actual})
    if hash_failures:
        errors.append("sha256 verification failed")

    scan_results = scan_bundle(bundle)
    if scan_results["secret_hits"]:
        errors.append("secret/private key/Oracle host marker found")
    if scan_results["order_true_hits"]:
        errors.append("order_execution_allowed=true pattern found")
    if scan_results["dangerous_hits"]:
        errors.append("dangerous broker/order/system command pattern found")
    if scan_results["broker_client_hits"]:
        errors.append("broker client import/use pattern found")

    if manifest.get("order_execution_allowed") is not False:
        errors.append("manifest order_execution_allowed must be false")
    if manifest.get("oracle_server_contacted") is not False:
        errors.append("manifest must state oracle_server_contacted=false")
    if manifest.get("manual_approval_required") is not True:
        warnings.append("manifest should state manual_approval_required=true")

    status = "failed" if errors else "ok"
    return {
        "status": status,
        "bundle_path": str(bundle),
        "manifest_path": str(manifest_path),
        "file_count": len(manifest_files),
        "missing_required": missing_required,
        "hash_failures": hash_failures,
        "secret_hits": scan_results["secret_hits"],
        "order_true_hits": scan_results["order_true_hits"],
        "dangerous_hits": scan_results["dangerous_hits"],
        "broker_client_hits": scan_results["broker_client_hits"],
        "warnings": warnings,
        "errors": errors,
        "manual_approval_required": bool(manifest.get("manual_approval_required")),
        "oracle_server_contacted": False,
        "oracle_systemd_touched": False,
        "order_execution_allowed": False,
    }


def scan_bundle(bundle: Path) -> dict[str, list[dict[str, Any]]]:
    result = {
        "secret_hits": [],
        "order_true_hits": [],
        "dangerous_hits": [],
        "broker_client_hits": [],
    }
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(bundle))
        add_pattern_hits(result["secret_hits"], SECRET_PATTERNS, relative, text)
        add_pattern_hits(result["order_true_hits"], ORDER_TRUE_PATTERNS, relative, text)
        add_pattern_hits(result["dangerous_hits"], DANGEROUS_PATTERNS, relative, text)
        add_pattern_hits(result["broker_client_hits"], BROKER_CLIENT_PATTERNS, relative, text)
    return result


def add_pattern_hits(target: list[dict[str, Any]], patterns: list[re.Pattern[str]], relative: str, text: str) -> None:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if pattern.search(line):
                target.append({"path": relative, "line": line_no, "pattern": pattern.pattern})


def failure(message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "errors": [message],
        "order_execution_allowed": False,
        "oracle_server_contacted": False,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
