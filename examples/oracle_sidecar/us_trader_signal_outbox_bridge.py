#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROFILE = "us_trader_oracle_v1"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


@dataclass(frozen=True)
class BridgeConfig:
    base_url: str
    mode: str
    profile: str
    outbox: Path
    processed: Path | None
    failed: Path | None
    state_path: Path
    secret: str | None
    timeout: float
    dry_run: bool
    move_files: bool


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only sidecar bridge for US Trader Oracle signal outbox JSON files. "
            "Default mode is normalize-preview; review mode must be requested explicitly."
        )
    )
    parser.add_argument(
        "--outbox",
        default=os.getenv("US_TRADER_SIGNAL_OUTBOX_DIR", "examples/oracle_sidecar/sample_outbox"),
        help="Directory containing signal JSON files.",
    )
    parser.add_argument(
        "--processed",
        default=os.getenv("US_TRADER_SIGNAL_PROCESSED_DIR") or None,
        help="Optional processed directory. Used only with --move-files.",
    )
    parser.add_argument(
        "--failed",
        default=os.getenv("US_TRADER_SIGNAL_FAILED_DIR") or None,
        help="Optional failed directory. Used only with --move-files.",
    )
    parser.add_argument(
        "--state",
        default=os.getenv("US_TRADER_SIGNAL_STATE_PATH"),
        help="State JSON path for duplicate suppression.",
    )
    parser.add_argument(
        "--mode",
        choices=["preview", "review"],
        default=os.getenv("US_TRADER_BRIDGE_MODE", "preview"),
        help="preview calls normalize-preview; review calls trade-signal.",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("US_TRADER_BRIDGE_PROFILE", DEFAULT_PROFILE),
        help=f"AI Council mapping profile. Default: {DEFAULT_PROFILE}.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL),
        help=f"AI Council base URL. Default: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--secret",
        default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET") or None,
        help="Webhook secret for review mode. Defaults to AI_COUNCIL_WEBHOOK_SECRET.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")),
        help="HTTP timeout in seconds.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not call AI Council or write state.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print final JSON summary.")
    parser.add_argument("--move-files", action="store_true", help="Move successful/failed files to processed/failed directories.")
    parser.add_argument("--watch", action="store_true", help="Continuously poll the outbox. Disabled by default.")
    parser.add_argument("--poll-seconds", type=float, default=10.0, help="Polling interval for --watch.")
    args = parser.parse_args()

    config = build_config(args)
    if args.watch:
        return run_watch_loop(config, args.poll_seconds, pretty=args.pretty)

    summary = run_once(config)
    print_json(summary, pretty=args.pretty)
    return 0 if summary["status"] == "passed" else 1


def build_config(args: argparse.Namespace) -> BridgeConfig:
    outbox = Path(args.outbox).expanduser()
    state_path = Path(args.state).expanduser() if args.state else default_state_path(outbox)
    processed = Path(args.processed).expanduser() if args.processed else None
    failed = Path(args.failed).expanduser() if args.failed else None
    return BridgeConfig(
        base_url=args.base_url.rstrip("/"),
        mode=args.mode,
        profile=args.profile,
        outbox=outbox,
        processed=processed,
        failed=failed,
        state_path=state_path,
        secret=args.secret,
        timeout=args.timeout,
        dry_run=args.dry_run,
        move_files=args.move_files,
    )


def default_state_path(outbox: Path) -> Path:
    sample_state = outbox.parent / "sample_state"
    if sample_state.exists():
        return sample_state / "bridge_state.json"
    return outbox.parent / ".us_trader_signal_outbox_bridge_state.json"


def run_watch_loop(config: BridgeConfig, poll_seconds: float, *, pretty: bool) -> int:
    while True:
        summary = run_once(config)
        print_json(summary, pretty=pretty)
        sys.stdout.flush()
        time.sleep(max(poll_seconds, 1.0))


def run_once(config: BridgeConfig) -> dict[str, Any]:
    state = load_state(config.state_path)
    processed_ids = set(state.get("processed_signal_ids", []))
    files = sorted(config.outbox.glob("*.json")) if config.outbox.exists() else []
    results = []
    failures = 0

    for path in files:
        try:
            payload = load_payload(path)
            signal_identity = build_signal_identity(payload, path)
            if signal_identity in processed_ids:
                results.append(
                    {
                        "file": path.name,
                        "status": "skipped_duplicate",
                        "signal_identity": signal_identity,
                        "order_execution_allowed": False,
                    }
                )
                continue
            response = process_signal(path, payload, config)
            validate_ai_council_response(path.name, response, config.mode, config.dry_run)
            result = {
                "file": path.name,
                "status": response.get("status", "dry_run" if config.dry_run else "processed"),
                "mode": config.mode,
                "signal_identity": signal_identity,
                "ticker": extract_ticker(response),
                "adapter_warnings": extract_warnings(response),
                "order_execution_allowed": False,
                "dry_run": config.dry_run,
            }
            results.append(result)
            if not config.dry_run:
                mark_processed(state, signal_identity, path, result)
                processed_ids.add(signal_identity)
                if config.move_files:
                    move_to_directory(path, config.processed, "processed")
        except Exception as exc:
            failures += 1
            results.append(
                {
                    "file": path.name,
                    "status": "failed",
                    "error": str(exc),
                    "order_execution_allowed": False,
                }
            )
            if not config.dry_run:
                mark_failed(state, path, exc)
                if config.move_files:
                    move_to_directory(path, config.failed, "failed")

    if not config.dry_run:
        save_state(config.state_path, state)

    return {
        "status": "failed" if failures else "passed",
        "mode": config.mode,
        "profile": config.profile,
        "outbox": str(config.outbox),
        "files_seen": len(files),
        "processed_count": len([item for item in results if item["status"] not in {"failed", "skipped_duplicate"}]),
        "duplicate_count": len([item for item in results if item["status"] == "skipped_duplicate"]),
        "failed_count": failures,
        "results": results,
        "state_path": str(config.state_path),
        "dry_run": config.dry_run,
        "safety": {
            "broker_api_used": False,
            "oracle_service_touched": False,
            "oracle_live_bot_modified": False,
            "order_execution_allowed_all_false": True,
            "review_mode_creates_ai_council_review_only": config.mode == "review",
        },
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def process_signal(path: Path, payload: dict[str, Any], config: BridgeConfig) -> dict[str, Any]:
    request_body = {
        "profile": config.profile,
        "payload": payload,
    }
    if config.dry_run:
        return {
            "status": "dry_run",
            "request_body": request_body,
            "webhook_called": False,
            "broker_api_called": False,
            "oracle_service_touched": False,
            "order_execution_allowed": False,
            "adapter_warnings": local_adapter_warnings(payload),
        }

    endpoint = "/api/webhooks/normalize-preview" if config.mode == "preview" else "/api/webhooks/trade-signal"
    return post_json(
        f"{config.base_url}{endpoint}",
        request_body,
        config.secret if config.mode == "review" else None,
        config.timeout,
    )


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: signal file must contain a JSON object")
    return payload


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed_signal_ids": [], "processed": [], "failed": []}
    with path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)
    if not isinstance(state, dict):
        return {"processed_signal_ids": [], "processed": [], "failed": []}
    state.setdefault("processed_signal_ids", [])
    state.setdefault("processed", [])
    state.setdefault("failed", [])
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)


def build_signal_identity(payload: dict[str, Any], path: Path) -> str:
    source = str(payload.get("source") or "us_trader_oracle").strip() or "us_trader_oracle"
    signal_id = str(payload.get("signal_id") or payload.get("id") or path.stem).strip() or path.stem
    return f"{source}:{signal_id}"


def mark_processed(state: dict[str, Any], signal_identity: str, path: Path, result: dict[str, Any]) -> None:
    if signal_identity not in state["processed_signal_ids"]:
        state["processed_signal_ids"].append(signal_identity)
    state["processed"].append(
        {
            "signal_identity": signal_identity,
            "file": path.name,
            "processed_at": now_iso(),
            "result": result,
            "order_execution_allowed": False,
        }
    )


def mark_failed(state: dict[str, Any], path: Path, exc: Exception) -> None:
    state["failed"].append(
        {
            "file": path.name,
            "failed_at": now_iso(),
            "error": str(exc),
            "order_execution_allowed": False,
        }
    )


def move_to_directory(path: Path, target_dir: Path | None, label: str) -> None:
    if target_dir is None:
        raise ValueError(f"--move-files requires --{label} directory")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if target.exists():
        target = target_dir / f"{path.stem}_{int(time.time())}{path.suffix}"
    shutil.move(str(path), str(target))


def post_json(url: str, payload: dict[str, Any], secret: str | None, timeout: float) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if secret:
        headers[SECRET_HEADER] = secret
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("AI Council returned JSON that is not an object")
    return data


def validate_ai_council_response(filename: str, response: dict[str, Any], mode: str, dry_run: bool) -> None:
    if response.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: expected order_execution_allowed=false")
    if dry_run:
        return
    normalized = response.get("normalized_payload") or {}
    if normalized and normalized.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: normalized payload must keep order_execution_allowed=false")
    if mode == "preview" and response.get("trade_review_created") is not False:
        raise RuntimeError(f"{filename}: normalize-preview must not create trade reviews")


def extract_ticker(response: dict[str, Any]) -> str | None:
    normalized = response.get("normalized_payload") or {}
    if normalized.get("ticker"):
        return normalized["ticker"]
    request_payload = response.get("request_body", {}).get("payload", {})
    return request_payload.get("ticker") or request_payload.get("symbol")


def extract_warnings(response: dict[str, Any]) -> list[str]:
    warnings = response.get("adapter_warnings")
    if isinstance(warnings, list):
        return [str(item) for item in warnings]
    normalized = response.get("normalized_payload") or {}
    normalized_warnings = normalized.get("adapter_warnings")
    if isinstance(normalized_warnings, list):
        return [str(item) for item in normalized_warnings]
    return []


def local_adapter_warnings(payload: dict[str, Any]) -> list[str]:
    order_like_fields = sorted(
        field
        for field in (
            "order_id",
            "order_type",
            "quantity",
            "qty",
            "shares",
            "notional",
            "take_profit",
            "stop_loss",
            "broker",
            "account",
            "route",
            "tif",
            "extended_hours",
            "submit_order",
            "place_order",
        )
        if field in payload
    )
    warnings = []
    if order_like_fields:
        warnings.append("order-like fields ignored for safety: " + ", ".join(order_like_fields))
    raw_side = str(payload.get("side") or payload.get("action") or payload.get("direction") or "").lower()
    if raw_side in {"buy", "sell", "entry", "exit", "long", "short"}:
        warnings.append(f"buy/sell side was treated as review context only: {raw_side}")
    return warnings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
