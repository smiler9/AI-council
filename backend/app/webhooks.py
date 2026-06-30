from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Any
from uuid import uuid4

from .council import SAFETY_BOUNDARY

WEBHOOK_SECRET_HEADER = "X-AI-Council-Webhook-Secret"
WEBHOOK_ENDPOINT_PATH = "/api/webhooks/trade-signal"


class WebhookInputError(ValueError):
    """Raised when an external webhook payload cannot be normalized."""


@dataclass(frozen=True)
class WebhookConfig:
    enabled: bool = False
    secret: str | None = None
    require_secret: bool = True

    @property
    def configured(self) -> bool:
        if not self.enabled:
            return False
        if self.require_secret and not self.secret:
            return False
        return True


def load_webhook_config(environ: Mapping[str, str] | None = None) -> WebhookConfig:
    values = os.environ if environ is None else environ
    return WebhookConfig(
        enabled=_as_bool(values.get("WEBHOOKS_ENABLED", "false")),
        secret=(values.get("WEBHOOK_SECRET") or "").strip() or None,
        require_secret=_as_bool(values.get("WEBHOOK_REQUIRE_SECRET", "true")),
    )


def webhook_status(config: WebhookConfig) -> dict:
    missing = []
    if config.enabled and config.require_secret and not config.secret:
        missing.append("WEBHOOK_SECRET")
    return {
        "enabled": config.enabled,
        "configured": config.configured,
        "require_secret": config.require_secret,
        "secret_configured": bool(config.secret),
        "secret_header": WEBHOOK_SECRET_HEADER,
        "endpoint_path": WEBHOOK_ENDPOINT_PATH,
        "missing": missing,
        "disabled_reason": _disabled_reason(config, missing),
        "safety_boundary": SAFETY_BOUNDARY,
        "order_execution_allowed": False,
    }


def validate_webhook_secret(config: WebhookConfig, received_secret: str | None) -> bool:
    if not config.require_secret:
        return True
    if not config.secret:
        return False
    return received_secret == config.secret


def normalize_trade_signal_payload(raw_payload: dict[str, Any]) -> dict:
    if not isinstance(raw_payload, dict):
        raise WebhookInputError("Webhook payload must be a JSON object")

    source = _string_value(raw_payload, "source") or "external_webhook"
    signal_id = _string_value(raw_payload, "signal_id") or _string_value(raw_payload, "id")
    if not signal_id:
        signal_id = f"generated_{uuid4().hex}"

    ticker = _string_value(raw_payload, "ticker") or _string_value(raw_payload, "symbol")
    strategy_signal = (
        _string_value(raw_payload, "strategy_signal")
        or _string_value(raw_payload, "signal")
        or _string_value(raw_payload, "setup")
    )
    if not ticker:
        raise WebhookInputError("Webhook payload requires ticker or symbol")
    if not strategy_signal:
        raise WebhookInputError("Webhook payload requires strategy_signal, signal, or setup")

    risk_context = _dict_value(raw_payload, "risk_context") or _dict_value(raw_payload, "risk")
    risk_context = dict(risk_context)
    event_time = _string_value(raw_payload, "timestamp") or _string_value(raw_payload, "event_time")
    if event_time:
        risk_context["event_time"] = event_time
    risk_context["signal_id"] = signal_id

    notes = _string_value(raw_payload, "notes")
    if not notes:
        notes = f"candidate signal received from {source}"

    normalized = {
        "ticker": ticker.strip().upper(),
        "strategy_signal": strategy_signal.strip(),
        "side": (_string_value(raw_payload, "side") or "review_only").strip().lower()
        or "review_only",
        "price": _number_value(raw_payload, "price", "last_price"),
        "volume": _int_value(raw_payload, "volume", "current_volume"),
        "timeframe": _string_value(raw_payload, "timeframe")
        or _string_value(raw_payload, "interval"),
        "source": source.strip(),
        "notes": notes,
        "technical_indicators": _dict_value(raw_payload, "technical_indicators")
        or _dict_value(raw_payload, "indicators"),
        "news_headlines": _list_value(raw_payload, "news_headlines", "headlines"),
        "risk_context": risk_context,
        "order_execution_allowed": False,
        "review_only": True,
        "webhook": {
            "source": source,
            "signal_id": signal_id,
            "event_type": "trade_signal",
        },
    }
    return normalized


def webhook_identity(normalized_payload: dict) -> tuple[str, str]:
    webhook = normalized_payload.get("webhook") or {}
    return str(webhook.get("source") or "external_webhook"), str(
        webhook.get("signal_id") or f"generated_{uuid4().hex}"
    )


def auto_send_requested(raw_payload: dict, query_value: bool = False) -> bool:
    return bool(query_value or raw_payload.get("auto_send_telegram") is True)


def _disabled_reason(config: WebhookConfig, missing: list[str]) -> str | None:
    if not config.enabled:
        return "Webhooks are disabled"
    if missing:
        return "Webhooks require a secret but WEBHOOK_SECRET is not configured"
    return None


def _as_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _string_value(payload: dict, *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value).strip()
    return None


def _dict_value(payload: dict, *keys: str) -> dict:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _list_value(payload: dict, *keys: str) -> list[str]:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
    return []


def _number_value(payload: dict, *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _int_value(payload: dict, *keys: str) -> int | None:
    value = _number_value(payload, *keys)
    return int(value) if value is not None else None
