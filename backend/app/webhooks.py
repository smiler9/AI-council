from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Any
from uuid import uuid4

from .council import SAFETY_BOUNDARY

WEBHOOK_SECRET_HEADER = "X-AI-Council-Webhook-Secret"
WEBHOOK_ENDPOINT_PATH = "/api/webhooks/trade-signal"
WEBHOOK_NORMALIZE_PREVIEW_PATH = "/api/webhooks/normalize-preview"

TICKER_ALIASES = ("ticker", "symbol", "code", "stock", "instrument", "asset")
SIGNAL_ALIASES = ("strategy_signal", "signal", "setup", "pattern", "trigger", "reason")
SIDE_ALIASES = ("side", "direction", "action", "intent")
PRICE_ALIASES = (
    "price",
    "last_price",
    "close",
    "current_price",
    "entry_price",
    "trigger_price",
)
VOLUME_ALIASES = ("volume", "current_volume", "vol", "day_volume")
TIMEFRAME_ALIASES = ("timeframe", "interval", "tf", "candle_interval")
INDICATOR_ALIASES = ("technical_indicators", "indicators", "ta", "metrics")
NEWS_ALIASES = ("news_headlines", "headlines", "news", "catalysts")
RISK_ALIASES = ("risk_context", "risk", "risk_flags", "meta")
SAFE_SIDE_VALUES = {"review_only", "watch_only", "observe", "monitor"}
ORDER_SIDE_VALUES = {
    "buy",
    "sell",
    "long",
    "short",
    "entry",
    "exit",
    "order",
    "market_order",
    "limit_order",
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
    "broker",
    "account",
    "route",
    "tif",
    "extended_hours",
    "submit" + "_order",
    "place" + "_order",
}
RECOGNIZED_FIELDS = {
    "source",
    "signal_id",
    "id",
    "timestamp",
    "event_time",
    "notes",
    "auto_send_telegram",
    "bridge_profile",
    *TICKER_ALIASES,
    *SIGNAL_ALIASES,
    *SIDE_ALIASES,
    *PRICE_ALIASES,
    *VOLUME_ALIASES,
    *TIMEFRAME_ALIASES,
    *INDICATOR_ALIASES,
    *NEWS_ALIASES,
    *RISK_ALIASES,
    *ORDER_LIKE_FIELDS,
}


class WebhookInputError(ValueError):
    """Raised when an external webhook payload cannot be normalized."""

    def __init__(self, message: str, adapter_warnings: list[str] | None = None):
        super().__init__(message)
        self.adapter_warnings = adapter_warnings or []


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
        "normalize_preview_endpoint_path": WEBHOOK_NORMALIZE_PREVIEW_PATH,
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

    adapter_warnings = _adapter_warnings(raw_payload)
    source = _string_value(raw_payload, "source") or "external_webhook"
    signal_id = _string_value(raw_payload, "signal_id") or _string_value(raw_payload, "id")
    if not signal_id:
        signal_id = f"generated_{uuid4().hex}"
        adapter_warnings.append("missing signal_id; generated id for idempotency")

    ticker = _string_value(raw_payload, *TICKER_ALIASES)
    strategy_signal = _string_value(raw_payload, *SIGNAL_ALIASES)
    if not ticker:
        adapter_warnings.append("missing ticker")
        raise WebhookInputError("Webhook payload requires ticker, symbol, code, stock, instrument, or asset", adapter_warnings)
    if not strategy_signal:
        adapter_warnings.append("missing strategy_signal")
        raise WebhookInputError(
            "Webhook payload requires strategy_signal, signal, setup, pattern, trigger, or reason",
            adapter_warnings,
        )

    raw_side = _string_value(raw_payload, *SIDE_ALIASES)
    side, side_warnings = _safe_side(raw_side)
    adapter_warnings.extend(side_warnings)
    price = _number_value(raw_payload, *PRICE_ALIASES)
    volume = _int_value(raw_payload, *VOLUME_ALIASES)
    news_headlines = _headline_list_value(raw_payload, *NEWS_ALIASES)
    if price is None:
        adapter_warnings.append("missing price")
    if volume is None:
        adapter_warnings.append("missing volume")
    if not news_headlines:
        adapter_warnings.append("news data unavailable")

    risk_context = _risk_context_value(raw_payload)
    event_time = _string_value(raw_payload, "timestamp") or _string_value(raw_payload, "event_time")
    if event_time:
        risk_context["event_time"] = event_time
    risk_context["signal_id"] = signal_id
    if raw_side:
        risk_context["raw_side"] = raw_side.strip().lower()
    if adapter_warnings:
        risk_context["adapter_warnings"] = adapter_warnings

    notes = _string_value(raw_payload, "notes")
    if not notes:
        notes = f"candidate signal received from {source}"

    normalized = {
        "ticker": ticker.strip().upper(),
        "strategy_signal": strategy_signal.strip(),
        "side": side,
        "raw_side": raw_side.strip().lower() if raw_side else None,
        "price": price,
        "volume": volume,
        "timeframe": _string_value(raw_payload, *TIMEFRAME_ALIASES),
        "source": source.strip(),
        "notes": notes,
        "technical_indicators": _dict_value(raw_payload, *INDICATOR_ALIASES),
        "news_headlines": news_headlines,
        "risk_context": risk_context,
        "adapter_warnings": adapter_warnings,
        "input_payload_json": raw_payload,
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


def _headline_list_value(payload: dict, *keys: str) -> list[str]:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            headlines = []
            for item in value:
                if isinstance(item, dict):
                    title = item.get("title") or item.get("headline") or item.get("text")
                    if title:
                        headlines.append(str(title).strip())
                elif str(item).strip():
                    headlines.append(str(item).strip())
            return [headline for headline in headlines if headline]
        if isinstance(value, dict):
            nested = value.get("headlines") or value.get("items") or value.get("news")
            if isinstance(nested, list):
                return _headline_list_value({"nested": nested}, "nested")
            title = value.get("title") or value.get("headline") or value.get("text")
            if title:
                return [str(title).strip()]
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


def _safe_side(raw_side: str | None) -> tuple[str, list[str]]:
    if not raw_side:
        return "review_only", []
    value = raw_side.strip().lower()
    if value in SAFE_SIDE_VALUES:
        return value, []
    if value in ORDER_SIDE_VALUES:
        return "review_only", [f"buy/sell side was treated as review context only: {value}"]
    return "review_only", [f"unsupported side value treated as review context only: {value}"]


def _adapter_warnings(payload: dict) -> list[str]:
    warnings = []
    order_like_fields = sorted(key for key in payload if key in ORDER_LIKE_FIELDS)
    if order_like_fields:
        warnings.append(
            "order-like fields ignored for safety: " + ", ".join(order_like_fields)
        )
    unsupported = sorted(key for key in payload if key not in RECOGNIZED_FIELDS)
    warnings.extend(f"unsupported field ignored: {key}" for key in unsupported[:8])
    return warnings


def _risk_context_value(payload: dict) -> dict:
    context = {}
    for key in ("risk_context", "risk", "meta"):
        value = payload.get(key)
        if isinstance(value, dict):
            context.update(value)
    flags = payload.get("risk_flags")
    if isinstance(flags, list):
        context["risk_flags"] = [str(item) for item in flags if str(item).strip()]
    elif isinstance(flags, str) and flags.strip():
        context["risk_flags"] = [flags.strip()]
    return context
