#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PROFILE = "us_trader_oracle_v1"
DEFAULT_LOCAL_INBOX = ROOT / "tmp" / "oracle_pull" / "inbox"
DEFAULT_STATE = ROOT / "tmp" / "oracle_operations" / "preview_loop_state.json"
DEFAULT_LOG = ROOT / "tmp" / "oracle_operations" / "preview_loop.log"
DEFAULT_PORTFOLIO_NAME = "Oracle Preview Paper Portfolio"
SECRET_HEADER = "X-AI-Council-Webhook-Secret"
TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
SAFE_ENTRY_RISK_LEVELS = {"low", "medium"}
SKIP_DECISIONS = {"HOLD", "BLOCK", "NEED_MORE_DATA"}
REQUIRED_SIGNAL_FIELDS = {
    "source",
    "signal_id",
    "signal",
    "action",
    "price",
    "volume",
    "timestamp",
}
ORDER_LIKE_FIELDS = {
    "order_id",
    "order_type",
    "quantity",
    "qty",
    "shares",
    "notional",
    "take_profit",
    "stop_loss",
    "account",
    "route",
    "tif",
    "extended_hours",
}
SAFETY_BOUNDARY = (
    "AI Council preview operations loop creates read-only reviews and simulation-only "
    "Paper Trading records. It does not execute trades, modify the Oracle bot, move "
    "Oracle outbox files, or operate Oracle systemd services."
)
ALERT_TITLE = "AI Council Oracle Preview Loop 알림"


@dataclass(frozen=True)
class LoopConfig:
    base_url: str
    profile: str
    local_inbox: Path
    state_path: Path
    log_path: Path
    portfolio_name: str
    secret: str | None
    timeout: float
    skip_remote_pull: bool
    oracle_host: str | None
    oracle_user: str | None
    oracle_key: str | None
    oracle_outbox_dir: str | None
    paper_policy: str
    max_notional_per_trade: float
    allow_only_decision: bool
    telegram_alerts_enabled: bool
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    telegram_timeout: float


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the local preview-only Oracle outbox to AI Council Paper Trading loop."
    )
    parser.add_argument("--run-once", action="store_true", help="Process one pass. This is the default.")
    parser.add_argument("--poll", action="store_true", help="Continuously poll. Must be requested explicitly.")
    parser.add_argument("--poll-interval-seconds", type=float, default=60.0)
    parser.add_argument("--max-iterations", type=int, default=None)
    parser.add_argument("--base-url", default=os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--profile", default=os.getenv("ORACLE_PULL_PROFILE", DEFAULT_PROFILE))
    parser.add_argument("--local-inbox", default=os.getenv("ORACLE_PULL_LOCAL_INBOX", str(DEFAULT_LOCAL_INBOX)))
    parser.add_argument("--state", default=os.getenv("ORACLE_PREVIEW_LOOP_STATE", str(DEFAULT_STATE)))
    parser.add_argument("--log", default=os.getenv("ORACLE_PREVIEW_LOOP_LOG", str(DEFAULT_LOG)))
    parser.add_argument("--portfolio-name", default=os.getenv("PAPER_PORTFOLIO_NAME", DEFAULT_PORTFOLIO_NAME))
    parser.add_argument("--secret", default=os.getenv("AI_COUNCIL_WEBHOOK_SECRET") or None)
    parser.add_argument("--timeout", type=float, default=float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--skip-remote-pull", action="store_true", help="Process the local inbox only.")
    parser.add_argument("--oracle-host", default=os.getenv("ORACLE_HOST") or None)
    parser.add_argument("--oracle-user", default=os.getenv("ORACLE_USER") or None)
    parser.add_argument("--oracle-key", default=os.getenv("ORACLE_SSH_KEY") or None)
    parser.add_argument("--oracle-outbox-dir", default=os.getenv("ORACLE_OUTBOX_DIR") or None)
    parser.add_argument("--paper-policy", default="risk_gate_conservative")
    parser.add_argument("--max-notional-per-trade", type=float, default=100.0)
    parser.add_argument("--allow-only-decision", action="store_true")
    parser.add_argument(
        "--telegram-alerts",
        action="store_true",
        default=env_bool("ORACLE_PREVIEW_LOOP_TELEGRAM_ALERTS", env_bool("TELEGRAM_ENABLED", False)),
        help="Send Telegram alerts for invalid/problem signals when Telegram credentials are configured.",
    )
    parser.add_argument("--telegram-bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN") or None)
    parser.add_argument("--telegram-chat-id", default=os.getenv("TELEGRAM_CHAT_ID") or None)
    parser.add_argument("--telegram-timeout", type=float, default=float(os.getenv("TELEGRAM_TIMEOUT_SECONDS", "10")))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    config = LoopConfig(
        base_url=args.base_url.rstrip("/"),
        profile=args.profile,
        local_inbox=Path(args.local_inbox).expanduser(),
        state_path=Path(args.state).expanduser(),
        log_path=Path(args.log).expanduser(),
        portfolio_name=args.portfolio_name,
        secret=args.secret,
        timeout=args.timeout,
        skip_remote_pull=args.skip_remote_pull,
        oracle_host=args.oracle_host,
        oracle_user=args.oracle_user,
        oracle_key=args.oracle_key,
        oracle_outbox_dir=args.oracle_outbox_dir,
        paper_policy=args.paper_policy,
        max_notional_per_trade=args.max_notional_per_trade,
        allow_only_decision=args.allow_only_decision,
        telegram_alerts_enabled=bool(args.telegram_alerts),
        telegram_bot_token=args.telegram_bot_token,
        telegram_chat_id=args.telegram_chat_id,
        telegram_timeout=args.telegram_timeout,
    )

    if args.poll:
        return run_poll(config, args.poll_interval_seconds, args.max_iterations, pretty=args.pretty)

    summary = run_once(config)
    print_json(summary, pretty=args.pretty)
    return 0 if summary["status"] == "completed" else 1


def run_poll(config: LoopConfig, poll_interval: float, max_iterations: int | None, *, pretty: bool) -> int:
    iteration = 0
    final_status = 0
    while True:
        iteration += 1
        summary = run_once(config)
        summary["poll_iteration"] = iteration
        print_json(summary, pretty=pretty)
        sys.stdout.flush()
        if summary["status"] != "completed":
            final_status = 1
        if max_iterations is not None and iteration >= max_iterations:
            return final_status
        time.sleep(max(poll_interval, 1.0))


def run_once(config: LoopConfig) -> dict[str, Any]:
    started_at = now_iso()
    state = load_state(config.state_path)
    telegram_alerts: list[dict[str, Any]] = []
    try:
        pull_summary = run_remote_pull(config)
        webhook_status = get_json(f"{config.base_url}/api/webhooks/status", config.timeout)
        validate_webhook_status(webhook_status)
        portfolio = get_or_create_portfolio(config)
    except Exception as exc:
        error = safe_error_message(exc)
        result = {
            "status": "failed",
            "started_at": started_at,
            "completed_at": now_iso(),
            "mode": "run_once",
            "profile": config.profile,
            "local_inbox": str(config.local_inbox),
            "state_path": str(config.state_path),
            "log_path": str(config.log_path),
            "signals_seen": 0,
            "signals_processed": 0,
            "signals_skipped_duplicate": 0,
            "signals_failed": 1,
            "trade_reviews_created": 0,
            "trade_reviews_reused": 0,
            "paper_simulations_created": 0,
            "simulated_entries": 0,
            "simulated_skips": 0,
            "remote_pull": {"status": "failed", "error": error, "order_execution_allowed": False},
            "remote_delete_performed": False,
            "remote_move_performed": False,
            "oracle_live_bot_modified": False,
            "oracle_systemd_touched": False,
            "paper_policy": config.paper_policy,
            "order_execution_allowed": False,
            "simulation_only": True,
            "telegram_alerts": {},
            "safety_boundary": SAFETY_BOUNDARY,
            "results": [
                {
                    "status": "failed",
                    "stage": "setup",
                    "error": error,
                    "order_execution_allowed": False,
                    "simulation_only": True,
                }
            ],
        }
        alert = send_problem_alert(
            config,
            "preview_loop_setup_failed",
            {"stage": "setup", "error": error, "order_execution_allowed": False, "simulation_only": True},
        )
        result["telegram_alerts"] = summarize_alerts(config, [alert])
        append_log(config.log_path, {"summary": result, "order_execution_allowed": False, "simulation_only": True})
        state["updated_at"] = now_iso()
        state["remote_delete_performed"] = False
        state["remote_move_performed"] = False
        state["order_execution_allowed"] = False
        state["simulation_only"] = True
        save_state(config.state_path, state)
        return result

    files = sorted(config.local_inbox.glob("*.json")) if config.local_inbox.exists() else []
    processed_ids = set(state.get("processed_signal_ids", []))
    results: list[dict[str, Any]] = []
    failures = 0
    duplicate_count = 0
    processed_count = 0
    review_created_count = 0
    review_reused_count = 0
    paper_simulation_count = 0
    simulated_entries = 0
    simulated_skips = 0

    for path in files:
        try:
            payload = load_signal_payload(path)
            validate_signal_payload(payload)
            signal_identity = build_signal_identity(payload, path)
            if signal_identity in processed_ids:
                duplicate_count += 1
                result = {
                    "file": path.name,
                    "status": "skipped_duplicate",
                    "signal_identity": signal_identity,
                    "order_execution_allowed": False,
                    "simulation_only": True,
                }
                results.append(result)
                append_log(config.log_path, result)
                mark_duplicate(state, signal_identity, path)
                continue

            review_response = create_trade_review(payload, config)
            review_result = extract_review_result(review_response)
            if review_result["duplicated"]:
                review_reused_count += 1
            else:
                review_created_count += 1

            simulation_response = simulate_review(
                review_result["trade_review_id"],
                portfolio["id"],
                config,
            )
            simulation_result = extract_simulation_result(simulation_response)
            validate_simulation_against_review(review_result, simulation_result)
            paper_simulation_count += 1
            simulated_entries += simulation_result["simulated_entries"]
            simulated_skips += simulation_result["simulated_skips"]
            processed_count += 1

            result = {
                "file": path.name,
                "status": "processed",
                "signal_identity": signal_identity,
                "trade_review_id": review_result["trade_review_id"],
                "linked_meeting_id": review_result["linked_meeting_id"],
                "webhook_status": review_response.get("status"),
                "webhook_duplicated": review_result["duplicated"],
                "ticker": review_result["ticker"],
                "decision": review_result["decision"],
                "risk_level": review_result["risk_level"],
                "trade_allowed": review_result["trade_allowed"],
                "raw_side": review_result["raw_side"],
                "side": review_result["side"],
                "adapter_warnings": review_result["adapter_warnings"],
                "paper_portfolio_id": portfolio["id"],
                "paper_trade_ids": simulation_result["paper_trade_ids"],
                "simulation_actions": simulation_result["actions"],
                "simulation_statuses": simulation_result["simulation_statuses"],
                "order_execution_allowed": False,
                "simulation_only": True,
            }
            results.append(result)
            mark_processed(state, signal_identity, path, result)
            append_log(config.log_path, result)
            processed_ids.add(signal_identity)
        except Exception as exc:
            failures += 1
            error = safe_error_message(exc)
            result = {
                "file": path.name,
                "status": "failed",
                "error": error,
                "order_execution_allowed": False,
                "simulation_only": True,
            }
            results.append(result)
            mark_failed(state, path, error)
            append_log(config.log_path, result)
            alert = send_problem_alert(
                config,
                "signal_processing_failed",
                {
                    "file": path.name,
                    "error": error,
                    "order_execution_allowed": False,
                    "simulation_only": True,
                },
            )
            telegram_alerts.append(alert)

    state["updated_at"] = now_iso()
    state["remote_delete_performed"] = False
    state["remote_move_performed"] = False
    state["order_execution_allowed"] = False
    state["simulation_only"] = True
    save_state(config.state_path, state)

    summary = {
        "status": "failed" if failures else "completed",
        "started_at": started_at,
        "completed_at": now_iso(),
        "mode": "run_once",
        "profile": config.profile,
        "local_inbox": str(config.local_inbox),
        "state_path": str(config.state_path),
        "log_path": str(config.log_path),
        "portfolio_id": portfolio["id"],
        "portfolio_name": portfolio["name"],
        "signals_seen": len(files),
        "signals_processed": processed_count,
        "signals_skipped_duplicate": duplicate_count,
        "signals_failed": failures,
        "trade_reviews_created": review_created_count,
        "trade_reviews_reused": review_reused_count,
        "paper_simulations_created": paper_simulation_count,
        "simulated_entries": simulated_entries,
        "simulated_skips": simulated_skips,
        "remote_pull": pull_summary,
        "remote_delete_performed": False,
        "remote_move_performed": False,
        "oracle_live_bot_modified": False,
        "oracle_systemd_touched": False,
        "paper_policy": config.paper_policy,
        "order_execution_allowed": False,
        "simulation_only": True,
        "telegram_alerts": summarize_alerts(config, telegram_alerts),
        "safety_boundary": SAFETY_BOUNDARY,
        "results": results,
    }
    append_log(config.log_path, {"summary": summary, "order_execution_allowed": False, "simulation_only": True})
    return summary


def run_remote_pull(config: LoopConfig) -> dict[str, Any]:
    if config.skip_remote_pull:
        return {
            "status": "skipped",
            "reason": "local inbox only",
            "remote_delete_performed": False,
            "remote_move_performed": False,
            "order_execution_allowed": False,
        }
    remote_values = [config.oracle_host, config.oracle_user, config.oracle_key, config.oracle_outbox_dir]
    if not all(remote_values):
        return {
            "status": "skipped",
            "reason": "Oracle connection values were not provided; processing local inbox only.",
            "remote_delete_performed": False,
            "remote_move_performed": False,
            "order_execution_allowed": False,
        }
    helper = ROOT / "examples" / "oracle_pull" / "oracle_outbox_pull_preview.py"
    command = [
        sys.executable,
        str(helper),
        "--host",
        str(config.oracle_host),
        "--user",
        str(config.oracle_user),
        "--key",
        str(config.oracle_key),
        "--outbox-dir",
        str(config.oracle_outbox_dir),
        "--local-inbox",
        str(config.local_inbox),
        "--enable-readonly-copy",
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=config.timeout + 30)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"remote pull helper timed out after {exc.timeout} seconds") from exc
    except subprocess.CalledProcessError as exc:
        output = sanitize_text((exc.stderr or exc.stdout or "").strip())
        detail = f": {output}" if output else ""
        raise RuntimeError(f"remote pull helper failed with exit code {exc.returncode}{detail}") from exc
    stdout = result.stdout.strip()
    payload = json.loads(stdout) if stdout else {}
    if payload.get("remote_delete_performed") is not False:
        raise RuntimeError("remote delete is not allowed")
    if payload.get("remote_move_performed") is not False:
        raise RuntimeError("remote move is not allowed")
    if payload.get("order_execution_allowed") is not False:
        raise RuntimeError("pull helper must keep order_execution_allowed=false")
    return {
        "status": payload.get("status", "passed"),
        "mode": payload.get("mode"),
        "remote_files_seen": payload.get("remote_files_seen", 0),
        "copied_files": payload.get("copied_files", []),
        "local_inbox": payload.get("local_inbox", str(config.local_inbox)),
        "remote_delete_performed": False,
        "remote_move_performed": False,
        "order_execution_allowed": False,
    }


def validate_webhook_status(status: dict[str, Any]) -> None:
    if status.get("order_execution_allowed") is not False:
        raise RuntimeError("webhook status must keep order_execution_allowed=false")
    if status.get("enabled") is not True or status.get("configured") is not True:
        raise RuntimeError("AI Council trade-signal webhook is not enabled/configured for local preview loop")


def create_trade_review(payload: dict[str, Any], config: LoopConfig) -> dict[str, Any]:
    request_body = {"profile": config.profile, "payload": payload}
    response = post_json(
        f"{config.base_url}/api/webhooks/trade-signal",
        request_body,
        config.secret,
        config.timeout,
    )
    if response.get("order_execution_allowed") is not False:
        raise RuntimeError("trade-signal response must keep order_execution_allowed=false")
    return response


def get_or_create_portfolio(config: LoopConfig) -> dict[str, Any]:
    portfolios = get_json(f"{config.base_url}/api/paper/portfolios", config.timeout)
    if not isinstance(portfolios, list):
        raise RuntimeError("paper portfolio list response must be an array")
    for portfolio in portfolios:
        if portfolio.get("name") == config.portfolio_name and portfolio.get("status", "active") == "active":
            return portfolio
    created = post_json(
        f"{config.base_url}/api/paper/portfolios",
        {
            "name": config.portfolio_name,
            "description": "Oracle preview-only operations loop portfolio. Simulation only; no broker orders.",
            "starting_cash": 10000,
        },
        None,
        config.timeout,
    )
    if created.get("order_execution_allowed") not in {None, False}:
        raise RuntimeError("paper portfolio response must not allow order execution")
    return created


def simulate_review(trade_review_id: str, portfolio_id: str, config: LoopConfig) -> dict[str, Any]:
    response = post_json(
        f"{config.base_url}/api/paper/portfolios/{portfolio_id}/simulate-review",
        {
            "source_type": "trade_review",
            "source_id": trade_review_id,
            "simulation_policy": config.paper_policy,
            "max_notional_per_trade": config.max_notional_per_trade,
            "allow_only_decision": config.allow_only_decision,
            "simulation_only": True,
        },
        None,
        config.timeout,
    )
    if response.get("order_execution_allowed") is not False:
        raise RuntimeError("simulate-review response must keep order_execution_allowed=false")
    if response.get("simulation_only") is not True:
        raise RuntimeError("simulate-review response must keep simulation_only=true")
    return response


def extract_review_result(response: dict[str, Any]) -> dict[str, Any]:
    review = response.get("trade_review") or {}
    event = response.get("event") or {}
    normalized = event.get("normalized_payload") or review.get("input_payload") or {}
    decision_payload = response.get("structured_decision") or review.get("structured_decision") or {}
    trade_review_id = review.get("id") or response.get("trade_review_id")
    if not trade_review_id:
        raise RuntimeError("trade-signal response did not include trade_review_id")
    if decision_payload.get("order_execution_allowed") is not False:
        raise RuntimeError("structured decision must keep order_execution_allowed=false")
    return {
        "trade_review_id": trade_review_id,
        "linked_meeting_id": review.get("linked_meeting_id"),
        "duplicated": bool(response.get("duplicated")),
        "ticker": review.get("ticker") or normalized.get("ticker"),
        "decision": str(decision_payload.get("decision") or "NEED_MORE_DATA").upper(),
        "risk_level": str(decision_payload.get("risk_level") or "high").lower(),
        "trade_allowed": bool(decision_payload.get("trade_allowed") is True),
        "raw_side": normalized.get("risk_context", {}).get("raw_side"),
        "side": normalized.get("side") or review.get("side"),
        "adapter_warnings": normalized.get("adapter_warnings") or response.get("adapter_warnings") or [],
        "order_execution_allowed": False,
    }


def extract_simulation_result(response: dict[str, Any]) -> dict[str, Any]:
    trades = response.get("trades") or []
    if not isinstance(trades, list):
        raise RuntimeError("simulate-review trades must be an array")
    actions = [str(trade.get("action") or "") for trade in trades]
    statuses = [str(trade.get("simulation_status") or "") for trade in trades]
    for trade in trades:
        if trade.get("order_execution_allowed") is not False:
            raise RuntimeError("paper trade must keep order_execution_allowed=false")
        if trade.get("simulation_only") is not True:
            raise RuntimeError("paper trade must keep simulation_only=true")
    return {
        "paper_trade_ids": [trade.get("id") for trade in trades if trade.get("id")],
        "actions": actions,
        "simulation_statuses": statuses,
        "simulated_entries": len([action for action in actions if action == "simulated_entry"]),
        "simulated_skips": len([action for action in actions if action == "simulated_skip"]),
        "order_execution_allowed": False,
        "simulation_only": True,
    }


def validate_simulation_against_review(review: dict[str, Any], simulation: dict[str, Any]) -> None:
    decision = str(review.get("decision") or "").upper()
    risk_level = str(review.get("risk_level") or "").lower()
    actions = set(simulation.get("actions") or [])
    if decision in SKIP_DECISIONS and "simulated_entry" in actions:
        raise RuntimeError(f"{decision} review must not create a simulated entry")
    if risk_level not in SAFE_ENTRY_RISK_LEVELS and "simulated_entry" in actions:
        raise RuntimeError(f"{risk_level} risk review must not create a simulated entry")
    if "simulated_entry" in actions and decision != "ALLOW":
        raise RuntimeError("only ALLOW decisions can create simulated entries")


def validate_signal_payload(payload: dict[str, Any]) -> None:
    missing = sorted(field for field in REQUIRED_SIGNAL_FIELDS if field not in payload)
    if "symbol" not in payload and "ticker" not in payload:
        missing.append("symbol_or_ticker")
    if missing:
        raise ValueError("signal JSON missing required fields: " + ", ".join(missing))
    if payload.get("order_execution_allowed") is not False:
        raise ValueError("signal JSON must include order_execution_allowed=false")
    if payload.get("review_only") is not True:
        raise ValueError("signal JSON must include review_only=true")
    if payload.get("simulation_only") is not True:
        raise ValueError("signal JSON must include simulation_only=true")
    if contains_secret_marker(payload):
        raise ValueError("signal JSON appears to contain secret-like markers")


def load_signal_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: expected JSON object")
    return payload


def build_signal_identity(payload: dict[str, Any], path: Path) -> str:
    source = str(payload.get("source") or "us_trader_oracle").strip() or "us_trader_oracle"
    signal_id = str(payload.get("signal_id") or payload.get("id") or path.stem).strip() or path.stem
    return f"{source}:{signal_id}"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "created_at": now_iso(),
            "processed_signal_ids": [],
            "processed": [],
            "skipped_duplicates": [],
            "failed": [],
            "remote_delete_performed": False,
            "remote_move_performed": False,
            "order_execution_allowed": False,
            "simulation_only": True,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("preview loop state must be a JSON object")
    payload.setdefault("version", 1)
    payload.setdefault("processed_signal_ids", [])
    payload.setdefault("processed", [])
    payload.setdefault("skipped_duplicates", [])
    payload.setdefault("failed", [])
    payload["order_execution_allowed"] = False
    payload["simulation_only"] = True
    return payload


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)


def mark_processed(state: dict[str, Any], signal_identity: str, path: Path, result: dict[str, Any]) -> None:
    if signal_identity not in state["processed_signal_ids"]:
        state["processed_signal_ids"].append(signal_identity)
    state["processed"].append(
        {
            "signal_identity": signal_identity,
            "file": path.name,
            "processed_at": now_iso(),
            "trade_review_id": result.get("trade_review_id"),
            "paper_portfolio_id": result.get("paper_portfolio_id"),
            "paper_trade_ids": result.get("paper_trade_ids", []),
            "simulation_actions": result.get("simulation_actions", []),
            "order_execution_allowed": False,
            "simulation_only": True,
        }
    )


def mark_duplicate(state: dict[str, Any], signal_identity: str, path: Path) -> None:
    state["skipped_duplicates"].append(
        {
            "signal_identity": signal_identity,
            "file": path.name,
            "skipped_at": now_iso(),
            "order_execution_allowed": False,
            "simulation_only": True,
        }
    )


def mark_failed(state: dict[str, Any], path: Path, error: str) -> None:
    state["failed"].append(
        {
            "file": path.name,
            "failed_at": now_iso(),
            "error": error,
            "order_execution_allowed": False,
            "simulation_only": True,
        }
    )


def append_log(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"logged_at": now_iso(), **item}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")


def get_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    return read_json_response(request, timeout)


def post_json(url: str, payload: dict[str, Any], secret: str | None, timeout: float) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if secret:
        headers[SECRET_HEADER] = secret
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    data = read_json_response(request, timeout)
    if not isinstance(data, dict):
        raise RuntimeError("AI Council returned non-object JSON")
    return data


def read_json_response(request: urllib.request.Request, timeout: float) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"connection failed: {exc.reason}") from exc


def send_problem_alert(config: LoopConfig, reason: str, context: dict[str, Any]) -> dict[str, Any]:
    status = telegram_alert_status(config)
    base = {
        "reason": reason,
        "enabled": status["enabled"],
        "configured": status["configured"],
        "sent": False,
        "status": "disabled" if not status["configured"] else "not_sent",
        "order_execution_allowed": False,
        "simulation_only": True,
    }
    if not status["enabled"]:
        return {**base, "detail": "Telegram alerts are disabled for the preview loop."}
    if not status["configured"]:
        return {
            **base,
            "detail": "Telegram alerts are enabled but credentials are not configured.",
            "missing": status["missing"],
        }

    message = format_problem_alert_message(reason, context)
    payload = {
        "chat_id": config.telegram_chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }
    request = urllib.request.Request(
        TELEGRAM_SEND_MESSAGE_URL.format(token=config.telegram_bot_token or ""),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.telegram_timeout) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = sanitize_text(exc.read().decode("utf-8", errors="replace"))
        return {**base, "status": "error", "detail": f"Telegram HTTP {exc.code}: {detail}"}
    except urllib.error.URLError as exc:
        return {**base, "status": "error", "detail": sanitize_text(f"Telegram connection failed: {exc.reason}")}

    sent = bool(response_payload.get("ok", False))
    return {
        **base,
        "sent": sent,
        "status": "sent" if sent else "error",
        "detail": sanitize_text(response_payload.get("description") or "Telegram API response received"),
    }


def telegram_alert_status(config: LoopConfig) -> dict[str, Any]:
    missing = []
    if config.telegram_alerts_enabled and not config.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if config.telegram_alerts_enabled and not config.telegram_chat_id:
        missing.append("TELEGRAM_CHAT_ID")
    return {
        "enabled": bool(config.telegram_alerts_enabled),
        "configured": bool(config.telegram_alerts_enabled and config.telegram_bot_token and config.telegram_chat_id),
        "missing": missing,
        "order_execution_allowed": False,
        "simulation_only": True,
    }


def summarize_alerts(config: LoopConfig, alerts: list[dict[str, Any]]) -> dict[str, Any]:
    status = telegram_alert_status(config)
    return {
        "enabled": status["enabled"],
        "configured": status["configured"],
        "attempted": len(alerts),
        "sent": len([alert for alert in alerts if alert.get("sent") is True]),
        "failed": len([alert for alert in alerts if alert.get("status") == "error"]),
        "disabled": len([alert for alert in alerts if alert.get("status") == "disabled"]),
        "results": alerts,
        "order_execution_allowed": False,
        "simulation_only": True,
    }


def format_problem_alert_message(reason: str, context: dict[str, Any]) -> str:
    safe_context = sanitize_value(context)
    lines = [
        ALERT_TITLE,
        f"문제 유형: {sanitize_text(reason)}",
        "모드: preview-only",
        "실제 주문 실행: 없음",
        "브로커 API 호출: 없음",
        "Oracle 원격 파일 삭제/이동: 없음",
        "order_execution_allowed=false",
        "simulation_only=true",
    ]
    labels = {
        "file": "파일",
        "signal_identity": "Signal ID",
        "stage": "단계",
        "error": "오류",
    }
    for key in ["file", "signal_identity", "stage", "error"]:
        value = safe_context.get(key)
        if value not in {None, ""}:
            lines.append(f"{labels[key]}: {value}")
    lines.extend(
        [
            "조치: 로컬 preview loop 로그와 Oracle outbox read-only 상태를 확인하세요.",
            f"안전 경계: {SAFETY_BOUNDARY}",
        ]
    )
    return "\n".join(lines)[:3500]


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {sanitize_text(str(key)): sanitize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def safe_error_message(exc: Exception) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        output = (exc.stderr or exc.stdout or "").strip()
        detail = f": {output}" if output else ""
        return sanitize_text(f"command failed with exit code {exc.returncode}{detail}")
    return sanitize_text(str(exc))


def sanitize_text(text: str) -> str:
    sanitized = str(text)
    replacements = [
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", "<redacted-private-key>"),
        (r"/Users/[^\s'\";]+/\.ssh/[^\s'\";]+", "<path-to-private-key>"),
        (r"/home/[^\s'\";]+/\.ssh/[^\s'\";]+", "<path-to-private-key>"),
        (r"ssh-key-[0-9A-Za-z_.-]+", "<path-to-private-key>"),
        (
            r"(?i)(telegram[_-]?bot[_-]?token|webhook[_-]?secret|api[_-]?key|access[_-]?token)\s*[:=]\s*[^\s,;]+",
            r"\1=<redacted>",
        ),
        (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<redacted-ip>"),
    ]
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.DOTALL)
    return sanitized


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def contains_secret_marker(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    markers = [
        "private key",
        "begin openssh",
        "api_key",
        "apikey",
        "access_token",
        "secret_token",
        "webhook_secret",
        "kis_config",
    ]
    return any(marker in text for marker in markers)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
