#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "examples" / "oracle_sidecar" / "patch_drafts" / "ai_council_signal_exporter_module.py"
SIDECAR_SCRIPT = ROOT / "examples" / "oracle_sidecar" / "us_trader_signal_outbox_bridge.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight the Oracle export hook draft locally.")
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
    parser.add_argument("--pretty", action="store_true", help="Pretty-print final JSON summary.")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        exporter = load_exporter_module()
        with tempfile.TemporaryDirectory(prefix="ai_council_export_hook_preflight_") as tmp:
            tmp_root = Path(tmp)
            outbox = tmp_root / "outbox"
            state = tmp_root / "state.json"
            payload = exporter.build_ai_council_signal(
                symbol="TESTA",
                strategy_signal="RSI_DIP+VOLUME_EXPLOSION",
                raw_side="buy",
                price=0.82,
                volume=12500000,
                timeframe="5m",
                indicators={
                    "rsi": 68,
                    "volume_ratio": 5.2,
                    "signal_score": 3.1,
                },
                risk_context={
                    "source_function": "scan_and_enter",
                    "breakout_ok": True,
                },
                news_headlines=["TESTA sample preflight headline"],
                notes="Preflight-generated review-only signal.",
                extra_context={
                    "quantity": 1000,
                    "order_type": "limit",
                    "safety_note": "order-like fields remain review context only",
                },
            )
            payload["quantity"] = 1000
            payload["order_type"] = "limit"
            exporter.validate_export_payload(payload)
            exported_path = exporter.export_ai_council_signal(payload, outbox)
            exported_payload = json.loads(exported_path.read_text(encoding="utf-8"))
            validate_exported_payload(exported_payload)

            dry_run = run_sidecar(outbox, state, base_url, args.timeout, dry_run=True)
            validate_sidecar_summary(dry_run, dry_run=True)

            preview = None
            backend_available = backend_is_available(base_url, args.timeout)
            if backend_available:
                preview = run_sidecar(outbox, state, base_url, args.timeout, dry_run=False)
                validate_sidecar_summary(preview, dry_run=False)

        summary = {
            "status": "passed",
            "generated_payload": {
                "source": exported_payload.get("source"),
                "symbol": exported_payload.get("symbol"),
                "signal": exported_payload.get("signal"),
                "action": exported_payload.get("action"),
                "price": exported_payload.get("price"),
                "volume": exported_payload.get("volume"),
                "review_only": exported_payload.get("review_only"),
                "simulation_only": exported_payload.get("simulation_only"),
                "order_execution_allowed": exported_payload.get("order_execution_allowed"),
                "adapter_warnings": exported_payload.get("adapter_warnings", []),
            },
            "dry_run": summarize_sidecar(dry_run),
            "preview": summarize_sidecar(preview) if preview else {"status": "skipped", "reason": "backend unavailable"},
            "safety": {
                "broker_api_used": False,
                "oracle_server_contacted": False,
                "oracle_live_bot_touched": False,
                "review_mode_executed": False,
                "order_execution_allowed_all_false": True,
            },
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
        }
        print_json(summary, pretty=args.pretty)
        return 1

    print_json(summary, pretty=args.pretty)
    return 0


def load_exporter_module():
    spec = importlib.util.spec_from_file_location("ai_council_signal_exporter_module", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError("could not load exporter module")
    spec.loader.exec_module(module)
    return module


def validate_exported_payload(payload: dict[str, Any]) -> None:
    if payload.get("source") != "us_trader_oracle":
        raise RuntimeError("generated payload source mismatch")
    if payload.get("order_execution_allowed") is not False:
        raise RuntimeError("generated payload must keep order_execution_allowed=false")
    if payload.get("review_only") is not True:
        raise RuntimeError("generated payload must keep review_only=true")
    if not str(payload.get("symbol", "")).startswith("TEST"):
        raise RuntimeError("generated payload must use TEST ticker")


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


def validate_sidecar_summary(summary: dict[str, Any], *, dry_run: bool) -> None:
    if summary.get("status") != "passed":
        raise RuntimeError(f"sidecar failed: {summary}")
    if summary.get("dry_run") is not dry_run:
        raise RuntimeError(f"expected sidecar dry_run={dry_run}")
    if summary.get("order_execution_allowed") is not False:
        raise RuntimeError("sidecar summary must keep order_execution_allowed=false")
    for item in summary.get("results", []):
        if item.get("order_execution_allowed") is not False:
            raise RuntimeError("sidecar result must keep order_execution_allowed=false")


def backend_is_available(base_url: str, timeout: float) -> bool:
    request = urllib.request.Request(f"{base_url}/health", headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok"


def summarize_sidecar(summary: dict[str, Any] | None) -> dict[str, Any]:
    if not summary:
        return {}
    return {
        "status": summary.get("status"),
        "mode": summary.get("mode"),
        "dry_run": summary.get("dry_run"),
        "files_seen": summary.get("files_seen"),
        "processed_count": summary.get("processed_count"),
        "failed_count": summary.get("failed_count"),
        "order_execution_allowed": summary.get("order_execution_allowed"),
    }


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
