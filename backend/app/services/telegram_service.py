from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

import httpx

from ..council import SAFETY_BOUNDARY


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool = False
    bot_token: str | None = None
    chat_id: str | None = None
    timeout_seconds: float = 10.0
    auto_send_telegram: bool = False

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.bot_token and self.chat_id)


def load_telegram_config(environ: Mapping[str, str] | None = None) -> TelegramConfig:
    values = os.environ if environ is None else environ
    enabled = _as_bool(values.get("TELEGRAM_ENABLED", "false"))
    token = (values.get("TELEGRAM_BOT_TOKEN") or "").strip() or None
    chat_id = (values.get("TELEGRAM_CHAT_ID") or "").strip() or None
    timeout_raw = (values.get("TELEGRAM_TIMEOUT_SECONDS") or "10").strip()
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ValueError("TELEGRAM_TIMEOUT_SECONDS must be a number") from exc
    if timeout <= 0:
        raise ValueError("TELEGRAM_TIMEOUT_SECONDS must be greater than 0")
    return TelegramConfig(
        enabled=enabled,
        bot_token=token,
        chat_id=chat_id,
        timeout_seconds=timeout,
        auto_send_telegram=False,
    )


class TelegramService:
    def __init__(self, config: TelegramConfig):
        self.config = config

    def status(self) -> dict:
        missing = []
        if self.config.enabled and not self.config.bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if self.config.enabled and not self.config.chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        return {
            "enabled": self.config.enabled,
            "configured": self.config.configured,
            "disabled_reason": self._disabled_reason(missing),
            "missing": missing,
            "auto_send_telegram": self.config.auto_send_telegram,
        }

    def format_meeting_message(self, meeting: dict, report: dict | None = None) -> str:
        decision = meeting.get("structured_decision") or {}
        trade_review = meeting.get("trade_review") or {}
        primary_reasons = _bullet_lines(decision.get("primary_reasons", []))
        risk_flags = _bullet_lines(decision.get("risk_flags", []))
        follow_up = _bullet_lines(decision.get("required_follow_up", []))
        report_path = report.get("path") if report else None
        report_line = f"Report: {report_path}" if report_path else "Report: not generated yet"
        return "\n".join(
            [
                "AI Council",
                f"Meeting: {meeting.get('topic', 'Untitled meeting')}",
                f"Mode: {meeting.get('mode', 'quick_review')}",
                f"Decision: {decision.get('decision', 'PENDING')}",
                f"Confidence: {decision.get('confidence', 0):.2f}",
                f"Risk level: {decision.get('risk_level', 'unrated')}",
                f"Trade allowed: {str(decision.get('trade_allowed', False)).lower()}",
                "Order execution allowed: false",
                "Primary reasons:",
                primary_reasons,
                "Risk flags:",
                risk_flags,
                "Required follow-up:",
                follow_up,
                report_line,
                f"Review status: {trade_review.get('review_status', meeting.get('status', 'unknown'))}",
                f"Safety Boundary: {SAFETY_BOUNDARY}",
            ]
        )

    def send_message(self, text: str) -> dict:
        status = self.status()
        if not self.config.configured:
            return {
                "sent": False,
                "status": "disabled",
                "detail": status["disabled_reason"],
                "telegram_status": status,
            }
        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return {
                "sent": False,
                "status": "error",
                "detail": str(exc),
                "telegram_status": status,
            }
        return {
            "sent": bool(data.get("ok", False)),
            "status": "sent" if data.get("ok", False) else "error",
            "detail": data.get("description") or "Telegram API response received",
            "telegram_status": status,
        }

    def send_meeting_report(self, meeting: dict, report: dict | None = None) -> dict:
        text = self.format_meeting_message(meeting, report)
        result = self.send_message(text)
        return {
            **result,
            "message": text,
        }

    def _disabled_reason(self, missing: list[str]) -> str | None:
        if not self.config.enabled:
            return "Telegram notifications are disabled"
        if missing:
            return "Telegram is enabled but required settings are missing"
        return None


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bullet_lines(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- {value}" for value in values[:8])

