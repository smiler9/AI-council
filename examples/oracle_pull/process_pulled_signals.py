#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROFILE = "us_trader_oracle_v1"
DEFAULT_INBOX = ROOT / "examples" / "oracle_pull" / "sample_pulled_signals"
DEFAULT_STATE = ROOT / "tmp" / "oracle_pull" / "state.json"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
ORDER_LIKE_FIELDS = {
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
}
SAFETY_BOUNDARY = (
    "AI Council does not execute trades or connect to broker APIs. "
    "This output is for review, risk analysis, and decision support only."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Process locally pulled Oracle US Trader signal JSON files.")
    parser.add_argument("--inbox", default=os.getenv("ORACLE_PULL_LOCAL_INBOX", str(DEFAULT_INBOX)))
    parser.add_argument("--state", default=os.getenv("ORACLE_PULL_STATE_PATH", str(DEFAULT_STATE)))
    parser.add_argument("--failed-dir", default=os.getenv("ORACLE_PULL_FAILED_DIR") or None)
    parser.add_argument("--mode", choices=["preview", "review"], default=os.getenv("ORACLE_PULL_MODE", "preview"))
    parser.add_argument("--profile", default=os.getenv("ORACLE_PULL_PROFILE", DEFAULT_PROFILE))
    parser.add_argument("--base-url", default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--secret", default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET") or None)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--dry-run", action="store_true", help="Do not call AI Council and do not write state.")
    parser.add_argument("--copy-failed", action="store_true", help="Copy failed local files to --failed-dir.")
    parser.add_argument(
        "--enable-paper-simulation",
        action="store_true",
        help="Reserved for a later phase. This script still does not place orders.",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    summary = run(args)
    print_json(summary, pretty=args.pretty)
    return 0 if summary["status"] == "passed" else 1


def run(args: argparse.Namespace) -> dict[str, Any]:
    inbox = Path(args.inbox).expanduser()
    state_path = Path(args.state).expanduser()
    state = load_state(state_path)
    processed_ids = set(state.get("processed_signal_ids", []))
    files = sorted(inbox.glob("*.json")) if inbox.exists() else []
    results: list[dict[str, Any]] = []
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

            response = process_signal(payload, args)
            validate_response(path.name, response, args.mode, args.dry_run)
            warnings = extract_warnings(response) or local_adapter_warnings(payload)
            result = {
                "file": path.name,
                "status": response.get("status", "dry_run" if args.dry_run else "processed"),
                "mode": args.mode,
                "signal_identity": signal_identity,
                "ticker": extract_ticker(response, payload),
                "adapter_warnings": warnings,
                "paper_simulation_requested": bool(args.enable_paper_simulation),
                "paper_simulation_executed": False,
                "order_execution_allowed": False,
                "dry_run": args.dry_run,
            }
            results.append(result)
            processed_ids.add(signal_identity)
            if not args.dry_run:
                mark_processed(state, signal_identity, path, result)
        except Exception as exc:
            failures += 1
            results.append({"file": path.name, "status": "failed", "error": str(exc), "order_execution_allowed": False})
            if not args.dry_run:
                mark_failed(state, path, exc)
                if args.copy_failed:
                    copy_failed(path, args.failed_dir)

    if not args.dry_run:
        save_state(state_path, state)

    return {
        "status": "failed" if failures else "passed",
        "mode": args.mode,
        "profile": args.profile,
        "inbox": str(inbox),
        "files_seen": len(files),
        "processed_count": len([item for item in results if item["status"] not in {"failed", "skipped_duplicate"}]),
        "duplicate_count": len([item for item in results if item["status"] == "skipped_duplicate"]),
        "failed_count": failures,
        "results": results,
        "state_path": str(state_path),
        "dry_run": args.dry_run,
        "remote_delete_performed": False,
        "remote_move_performed": False,
        "paper_simulation_enabled": bool(args.enable_paper_simulation),
        "paper_simulation_executed": False,
        "safety": {
            "broker_api_used": False,
            "oracle_server_contacted": False,
            "oracle_live_bot_modified": False,
            "oracle_systemd_touched": False,
            "remote_delete_performed": False,
            "remote_move_performed": False,
            "order_execution_allowed_all_false": True,
        },
        "simulation_only": bool(args.enable_paper_simulation),
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def process_signal(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    request_body = {"profile": args.profile, "payload": payload}
    if args.dry_run:
        return {
            "status": "dry_run",
            "request_body": request_body,
            "webhook_called": False,
            "adapter_warnings": local_adapter_warnings(payload),
            "order_execution_allowed": False,
        }
    endpoint = "/api/webhooks/normalize-preview" if args.mode == "preview" else "/api/webhooks/trade-signal"
    return post_json(
        f"{args.base_url.rstrip('/')}{endpoint}",
        request_body,
        args.secret if args.mode == "review" else None,
        args.timeout,
    )


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: expected JSON object")
    return payload


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed_signal_ids": [], "processed": [], "failed": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"processed_signal_ids": [], "processed": [], "failed": []}
    payload.setdefault("processed_signal_ids", [])
    payload.setdefault("processed", [])
    payload.setdefault("failed", [])
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


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


def copy_failed(path: Path, failed_dir: str | None) -> None:
    if not failed_dir:
        raise ValueError("--copy-failed requires --failed-dir")
    target_dir = Path(failed_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target_dir / path.name)


def post_json(url: str, payload: dict[str, Any], secret: str | None, timeout: float) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if secret:
        headers[SECRET_HEADER] = secret
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("AI Council returned non-object JSON")
    return data


def validate_response(filename: str, response: dict[str, Any], mode: str, dry_run: bool) -> None:
    if response.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: expected order_execution_allowed=false")
    if dry_run:
        return
    normalized = response.get("normalized_payload") or {}
    if normalized and normalized.get("order_execution_allowed") is not False:
        raise RuntimeError(f"{filename}: normalized payload must keep order_execution_allowed=false")
    if mode == "preview" and response.get("trade_review_created") is not False:
        raise RuntimeError(f"{filename}: normalize-preview must not create trade reviews")


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
    warnings = []
    order_like_fields = sorted(field for field in ORDER_LIKE_FIELDS if field in payload)
    if order_like_fields:
        warnings.append("order-like fields ignored for safety: " + ", ".join(order_like_fields))
    raw_side = str(payload.get("side") or payload.get("action") or payload.get("direction") or "").lower()
    if raw_side in {"buy", "sell", "entry", "exit", "long", "short"}:
        warnings.append(f"buy/sell side was treated as review context only: {raw_side}")
    if not payload.get("news_headlines") and not payload.get("headlines") and not payload.get("news"):
        warnings.append("news data unavailable")
    return warnings


def extract_ticker(response: dict[str, Any], payload: dict[str, Any]) -> str | None:
    normalized = response.get("normalized_payload") or {}
    return normalized.get("ticker") or payload.get("ticker") or payload.get("symbol")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
