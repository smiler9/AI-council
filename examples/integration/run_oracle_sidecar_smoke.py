#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
SIDECAR_SCRIPT = ROOT / "examples" / "oracle_sidecar" / "us_trader_signal_outbox_bridge.py"
SAMPLE_OUTBOX = ROOT / "examples" / "oracle_sidecar" / "sample_outbox"
SAMPLE_FILES = [
    "us_trader_signal_001.json",
    "us_trader_signal_order_like.json",
    "us_trader_signal_high_risk.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Oracle sidecar signal bridge.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL),
        help=f"AI Council base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")),
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print final summary JSON.")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    steps: list[dict[str, Any]] = []

    try:
        health = get_json(f"{base_url}/health", args.timeout)
        assert_not_order_enabled(health, "health")
        steps.append({"name": "health", "status": health.get("status")})

        diagnostics = get_json(f"{base_url}/api/diagnostics/summary", args.timeout)
        assert_not_order_enabled(diagnostics, "diagnostics")
        steps.append({"name": "diagnostics", "status": diagnostics.get("status")})

        samples = validate_sample_json()
        steps.append({"name": "sample_json", "count": len(samples)})

        with tempfile.TemporaryDirectory(prefix="ai_council_sidecar_smoke_") as tmp:
            tmp_root = Path(tmp)
            outbox = tmp_root / "outbox"
            state = tmp_root / "state.json"
            shutil.copytree(SAMPLE_OUTBOX, outbox)

            dry_run = run_sidecar(outbox, state, base_url, args.timeout, dry_run=True)
            validate_sidecar_summary(dry_run, expected_mode="preview", dry_run=True)
            steps.append({"name": "sidecar_dry_run", "status": dry_run.get("status")})

            preview = run_sidecar(outbox, state, base_url, args.timeout, dry_run=False)
            validate_sidecar_summary(preview, expected_mode="preview", dry_run=False)
            steps.append({"name": "sidecar_preview", "status": preview.get("status")})

            duplicate = run_sidecar(outbox, state, base_url, args.timeout, dry_run=False)
            if duplicate.get("duplicate_count") != len(SAMPLE_FILES):
                raise RuntimeError("sidecar duplicate suppression did not skip all sample signals")
            steps.append({"name": "sidecar_duplicate_suppression", "duplicates": duplicate.get("duplicate_count")})

        summary = {
            "status": "passed",
            "sample_count": len(samples),
            "dry_run": summarize_run(dry_run),
            "preview": summarize_run(preview),
            "safety": {
                "order_execution_allowed_all_false": True,
                "broker_api_used": False,
                "oracle_server_contacted": False,
                "oracle_live_bot_touched": False,
                "review_mode_executed": False,
            },
            "steps": steps,
        }
    except Exception as exc:
        summary = {
            "status": "failed",
            "error": str(exc),
            "safety": {
                "broker_api_used": False,
                "oracle_server_contacted": False,
                "oracle_live_bot_touched": False,
                "review_mode_executed": False,
            },
            "steps": steps,
        }
        print_json(summary, pretty=args.pretty)
        return 1

    print_json(summary, pretty=args.pretty)
    return 0


def validate_sample_json() -> list[dict[str, Any]]:
    samples = []
    for filename in SAMPLE_FILES:
        path = SAMPLE_OUTBOX / filename
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise RuntimeError(f"{filename}: expected JSON object")
        if not str(payload.get("symbol", "")).startswith("TEST"):
            raise RuntimeError(f"{filename}: sample ticker must start with TEST")
        if payload.get("order_execution_allowed") is not False:
            raise RuntimeError(f"{filename}: expected order_execution_allowed=false")
        samples.append(payload)
    return samples


def run_sidecar(outbox: Path, state: Path, base_url: str, timeout: float, *, dry_run: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        str(SIDECAR_SCRIPT),
        "--outbox",
        str(outbox),
        "--state",
        str(state),
        "--mode",
        "preview",
        "--base-url",
        base_url,
        "--timeout",
        str(timeout),
    ]
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("sidecar returned non-object JSON")
    return payload


def validate_sidecar_summary(summary: dict[str, Any], *, expected_mode: str, dry_run: bool) -> None:
    if summary.get("status") != "passed":
        raise RuntimeError(f"sidecar summary failed: {summary}")
    if summary.get("mode") != expected_mode:
        raise RuntimeError(f"expected mode={expected_mode}")
    if summary.get("dry_run") is not dry_run:
        raise RuntimeError(f"expected dry_run={dry_run}")
    if summary.get("order_execution_allowed") is not False:
        raise RuntimeError("summary must keep order_execution_allowed=false")
    if summary.get("files_seen") != len(SAMPLE_FILES):
        raise RuntimeError("sidecar did not see all sample files")
    warning_text = " ".join(
        warning
        for item in summary.get("results", [])
        for warning in item.get("adapter_warnings", [])
    )
    if "order-like fields ignored for safety" not in warning_text:
        raise RuntimeError("missing order-like field safety warning")
    for item in summary.get("results", []):
        if item.get("order_execution_allowed") is not False:
            raise RuntimeError("result item must keep order_execution_allowed=false")


def summarize_run(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": summary.get("status"),
        "files_seen": summary.get("files_seen"),
        "processed_count": summary.get("processed_count"),
        "duplicate_count": summary.get("duplicate_count"),
        "failed_count": summary.get("failed_count"),
        "dry_run": summary.get("dry_run"),
        "order_execution_allowed": summary.get("order_execution_allowed"),
    }


def get_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("expected JSON object response")
    return payload


def assert_not_order_enabled(payload: dict[str, Any], label: str) -> None:
    if payload.get("order_execution_allowed") is True:
        raise RuntimeError(f"{label}: order_execution_allowed must not be true")


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
