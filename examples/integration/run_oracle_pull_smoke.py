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
PULL_DIR = ROOT / "examples" / "oracle_pull"
PROCESS_SCRIPT = PULL_DIR / "process_pulled_signals.py"
VERIFY_PLAN_SCRIPT = PULL_DIR / "verify_pull_plan.py"
SAMPLE_PLAN = PULL_DIR / "sample_pull_plan.json"
SAMPLE_SIGNALS = PULL_DIR / "sample_pulled_signals"
SAMPLE_FILES = [
    "pulled_us_trader_signal_001.json",
    "pulled_us_trader_signal_order_like.json",
    "pulled_us_trader_signal_high_risk.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Mac pull Oracle outbox preview pipeline.")
    parser.add_argument("--base-url", default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--pretty", action="store_true")
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

        verify_plan = run_verify_plan()
        steps.append({"name": "verify_pull_plan", "status": verify_plan.get("status")})

        samples = validate_sample_json()
        steps.append({"name": "sample_json", "count": len(samples)})

        with tempfile.TemporaryDirectory(prefix="ai_council_oracle_pull_") as tmp:
            tmp_root = Path(tmp)
            inbox = tmp_root / "inbox"
            state = tmp_root / "state.json"
            shutil.copytree(SAMPLE_SIGNALS, inbox)

            preview = run_process(inbox, state, base_url, args.timeout)
            validate_process_summary(preview, dry_run=False)
            steps.append({"name": "process_preview", "status": preview.get("status")})

            duplicate = run_process(inbox, state, base_url, args.timeout)
            if duplicate.get("duplicate_count") != len(SAMPLE_FILES):
                raise RuntimeError("duplicate suppression did not skip all sample signals")
            steps.append({"name": "duplicate_suppression", "duplicates": duplicate.get("duplicate_count")})

        summary = {
            "status": "passed",
            "sample_count": len(samples),
            "plan_verify": summarize_verify(verify_plan),
            "preview": summarize_process(preview),
            "safety": {
                "order_execution_allowed_all_false": True,
                "broker_api_used": False,
                "oracle_server_contacted": False,
                "remote_delete_performed": False,
                "remote_move_performed": False,
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
                "remote_delete_performed": False,
                "remote_move_performed": False,
                "review_mode_executed": False,
            },
            "steps": steps,
        }
        print_json(summary, pretty=args.pretty)
        return 1

    print_json(summary, pretty=args.pretty)
    return 0


def run_verify_plan() -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(VERIFY_PLAN_SCRIPT), "--plan", str(SAMPLE_PLAN), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if payload.get("status") != "ok":
        raise RuntimeError(f"pull plan verify failed: {payload}")
    return payload


def validate_sample_json() -> list[dict[str, Any]]:
    samples = []
    for filename in SAMPLE_FILES:
        path = SAMPLE_SIGNALS / filename
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError(f"{filename}: expected JSON object")
        if not str(payload.get("symbol", "")).startswith("TEST"):
            raise RuntimeError(f"{filename}: sample ticker must start with TEST")
        if payload.get("order_execution_allowed") is not False:
            raise RuntimeError(f"{filename}: order_execution_allowed must be false")
        samples.append(payload)
    return samples


def run_process(inbox: Path, state: Path, base_url: str, timeout: float) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            str(PROCESS_SCRIPT),
            "--inbox",
            str(inbox),
            "--state",
            str(state),
            "--mode",
            "preview",
            "--base-url",
            base_url,
            "--timeout",
            str(timeout),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("process script returned non-object JSON")
    return payload


def validate_process_summary(summary: dict[str, Any], *, dry_run: bool) -> None:
    if summary.get("status") != "passed":
        raise RuntimeError(f"process summary failed: {summary}")
    if summary.get("mode") != "preview":
        raise RuntimeError("process mode must be preview")
    if summary.get("dry_run") is not dry_run:
        raise RuntimeError(f"expected dry_run={dry_run}")
    if summary.get("order_execution_allowed") is not False:
        raise RuntimeError("summary must keep order_execution_allowed=false")
    if summary.get("remote_delete_performed") is not False or summary.get("remote_move_performed") is not False:
        raise RuntimeError("remote files must not be deleted or moved")
    if summary.get("files_seen") != len(SAMPLE_FILES):
        raise RuntimeError("process script did not see all sample files")
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


def summarize_verify(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "mode": payload.get("mode"),
        "remote_delete": payload.get("remote_delete"),
        "remote_move": payload.get("remote_move"),
        "order_execution_allowed": payload.get("order_execution_allowed"),
    }


def summarize_process(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "files_seen": payload.get("files_seen"),
        "processed_count": payload.get("processed_count"),
        "duplicate_count": payload.get("duplicate_count"),
        "failed_count": payload.get("failed_count"),
        "order_execution_allowed": payload.get("order_execution_allowed"),
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
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
