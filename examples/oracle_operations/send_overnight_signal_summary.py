#!/usr/bin/env python3
"""Send a Korean Telegram summary of signals processed overnight.

Reads the preview loop state file for signals processed within the window,
fetches each trade review's structured decision from the AI Council backend,
adds the paper portfolio snapshot, and sends one Telegram message.

Report-only: no broker calls, no order execution, no Oracle file changes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8100"
DEFAULT_STATE = ROOT / "tmp" / "oracle_operations" / "preview_loop_state.json"
DEFAULT_PORTFOLIO_NAME = "Oracle Preview Paper Portfolio"
TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"
DECISION_ORDER = ["ALLOW", "HOLD", "BLOCK", "NEED_MORE_DATA"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send overnight signal processing summary to Telegram.")
    parser.add_argument("--env-file", default=None, help="Optional KEY=VALUE env file to load first.")
    parser.add_argument("--hours", type=float, default=24.0, help="Look-back window in hours.")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--portfolio-name", default=None)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending.")
    args = parser.parse_args()

    if args.env_file:
        load_env_file(Path(args.env_file))

    base_url = (args.base_url or os.getenv("AI_COUNCIL_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
    state_path = Path(args.state or os.getenv("ORACLE_PREVIEW_LOOP_STATE", str(DEFAULT_STATE)))
    portfolio_name = args.portfolio_name or os.getenv("PAPER_PORTFOLIO_NAME", DEFAULT_PORTFOLIO_NAME)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=max(args.hours, 0.5))
    state = load_state(state_path)
    processed = entries_in_window(state.get("processed", []), "processed_at", since)
    failed = entries_in_window(state.get("failed", []), "last_failed_at", since)

    reviews = []
    for entry in processed:
        review = fetch_review_summary(base_url, entry.get("trade_review_id"), args.timeout)
        reviews.append({**entry, **review})

    paper = fetch_paper_snapshot(base_url, portfolio_name, args.timeout)
    message = build_summary_message(reviews, failed, paper, args.hours, now)

    if args.dry_run:
        print(message)
        return 0

    result = send_telegram(message, args.timeout)
    print(json.dumps({"sent": result["sent"], "detail": result["detail"], "signals": len(reviews)}, ensure_ascii=False))
    return 0 if result["sent"] else 1


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key.strip()] = value


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def entries_in_window(entries: list[dict[str, Any]], key: str, since: datetime) -> list[dict[str, Any]]:
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stamp = parse_iso(entry.get(key))
        if stamp is not None and stamp >= since:
            kept.append(entry)
    return kept


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def fetch_review_summary(base_url: str, review_id: str | None, timeout: float) -> dict[str, Any]:
    empty = {"ticker": None, "decision": None, "risk_level": None}
    if not review_id:
        return empty
    try:
        payload = get_json(f"{base_url}/api/trade-reviews/{review_id}", timeout)
    except Exception:
        return empty
    review = payload.get("trade_review") or payload
    decision = review.get("structured_decision") or {}
    return {
        "ticker": review.get("ticker"),
        "decision": str(decision.get("decision") or "").upper() or None,
        "risk_level": str(decision.get("risk_level") or "").lower() or None,
    }


def fetch_paper_snapshot(base_url: str, portfolio_name: str, timeout: float) -> dict[str, Any] | None:
    try:
        portfolios = get_json(f"{base_url}/api/paper/portfolios", timeout)
        for portfolio in portfolios if isinstance(portfolios, list) else []:
            if portfolio.get("name") == portfolio_name:
                detail = get_json(f"{base_url}/api/paper/portfolios/{portfolio['id']}", timeout)
                summary = detail.get("summary") or {}
                return {
                    "cash": summary.get("cash") or portfolio.get("cash"),
                    "total_value": summary.get("total_value") or summary.get("portfolio_value"),
                    "open_positions": len(detail.get("positions") or []),
                    "total_trades": len(detail.get("trades") or []),
                }
    except Exception:
        pass
    return None


def build_summary_message(
    reviews: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    paper: dict[str, Any] | None,
    window_hours: float,
    now: datetime,
) -> str:
    kst = now + timedelta(hours=9)
    lines = [
        "AI Council 야간 signal 처리 요약",
        f"기준: {kst.strftime('%Y-%m-%d %H:%M')} KST, 최근 {window_hours:.0f}시간",
        "",
    ]

    if not reviews and not failed:
        lines.append("밤새 신규 signal이 없었습니다. (봇 필터를 통과한 후보 없음)")
    else:
        decision_counts: dict[str, int] = {}
        entry_count = 0
        skip_count = 0
        for review in reviews:
            decision = review.get("decision") or "UNKNOWN"
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
            actions = review.get("simulation_actions") or []
            entry_count += sum(1 for action in actions if action == "simulated_entry")
            skip_count += sum(1 for action in actions if action == "simulated_skip")

        lines.append(f"처리된 signal: {len(reviews)}건 | 실패: {len(failed)}건")
        decision_parts = [
            f"{name} {decision_counts[name]}" for name in DECISION_ORDER if decision_counts.get(name)
        ]
        for name, count in decision_counts.items():
            if name not in DECISION_ORDER:
                decision_parts.append(f"{name} {count}")
        if decision_parts:
            lines.append("판단: " + " / ".join(decision_parts))
        lines.append(f"Paper: 가상 진입 {entry_count} / 가상 skip {skip_count}")
        lines.append("")
        for review in reviews[:15]:
            ticker = review.get("ticker") or "?"
            decision = review.get("decision") or "?"
            risk = review.get("risk_level") or "?"
            lines.append(f"- {ticker}: {decision} (risk {risk})")
        if len(reviews) > 15:
            lines.append(f"- 외 {len(reviews) - 15}건")
        for entry in failed[:5]:
            lines.append(f"- 실패: {entry.get('file')} ({str(entry.get('error'))[:80]})")

    if paper:
        lines.append("")
        cash = paper.get("cash")
        total = paper.get("total_value")
        lines.append(
            "Paper 포트폴리오: "
            + (f"총가치 ${total:,.2f} | " if isinstance(total, (int, float)) else "")
            + (f"현금 ${cash:,.2f} | " if isinstance(cash, (int, float)) else "")
            + f"보유 {paper.get('open_positions', 0)}종목 | 누적 가상거래 {paper.get('total_trades', 0)}건"
        )

    lines.extend(
        [
            "",
            "실제 주문 실행 없음 · simulation_only=true · order_execution_allowed=false",
        ]
    )
    return "\n".join(lines)[:3800]


def get_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def send_telegram(message: str, timeout: float) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"sent": False, "detail": "TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not configured"}
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    request = urllib.request.Request(
        TELEGRAM_SEND_MESSAGE_URL.format(token=token),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"sent": False, "detail": f"Telegram HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"sent": False, "detail": f"Telegram connection failed: {exc.reason}"}
    return {"sent": bool(body.get("ok")), "detail": body.get("description") or "ok"}


if __name__ == "__main__":
    raise SystemExit(main())
