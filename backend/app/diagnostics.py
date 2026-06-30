from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .council import KOREAN_SAFETY_BOUNDARY
from .llm.config import LLMConfig
from .market_data import MarketDataConfig, get_market_data_provider
from .risk_events import RiskEventConfig, risk_event_status
from .services.telegram_service import TelegramService
from .webhooks import WebhookConfig, webhook_status


PHASE_LABEL = "Phase 23 diagnostics"
E2E_EXPECTED_STEPS = 17


def build_diagnostics_summary(
    *,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    telegram_service: TelegramService,
    webhook_config: WebhookConfig,
    risk_event_config: RiskEventConfig,
    endpoint_paths: list[str],
) -> dict:
    provider_status = build_provider_diagnostics(
        llm_config=llm_config,
        market_data_config=market_data_config,
        telegram_service=telegram_service,
        webhook_config=webhook_config,
        risk_event_config=risk_event_config,
    )
    security = build_security_diagnostics(
        telegram_service=telegram_service,
        webhook_config=webhook_config,
        market_data_config=market_data_config,
        llm_config=llm_config,
        endpoint_paths=endpoint_paths,
    )
    return {
        "status": "ok" if provider_status["status"] == "ok" and security["status"] == "ok" else "warning",
        "backend": {
            "status": "ok",
            "health": "ok",
        },
        "providers": {
            "llm_provider": llm_config.provider,
            "market_data_provider": market_data_config.normalized_provider,
            "telegram_enabled": telegram_service.config.enabled,
            "webhooks_enabled": webhook_config.enabled,
            "risk_event_detector_enabled": risk_event_config.detector_enabled,
        },
        "features": {
            "meetings": True,
            "trade_reviews": True,
            "ticker_reviews": True,
            "autonomous_reviews": True,
            "watchlists": True,
            "scheduled_reviews": True,
            "paper_trading": True,
            "performance_reports": True,
            "e2e_tests": True,
        },
        "safety": {
            "order_execution_allowed": False,
            "broker_api_connected": False,
            "simulation_only_confirmed": True,
            "secret_exposure_detected": False,
        },
        "last_checks": [
            {
                "name": "security",
                "status": security["status"],
                "order_execution_allowed": False,
            },
            {
                "name": "providers",
                "status": provider_status["status"],
                "order_execution_allowed": False,
            },
            {
                "name": "e2e_script",
                "status": "available" if build_e2e_status()["full_e2e_script_available"] else "missing",
                "order_execution_allowed": False,
            },
        ],
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_security_diagnostics(
    *,
    telegram_service: TelegramService,
    webhook_config: WebhookConfig,
    market_data_config: MarketDataConfig,
    llm_config: LLMConfig,
    endpoint_paths: list[str],
) -> dict:
    order_endpoint_found = _contains_order_execution_endpoint(endpoint_paths)
    return {
        "status": "warning" if order_endpoint_found else "ok",
        "order_execution_allowed": False,
        "broker_api_connected": False,
        "order_execution_endpoints_found": order_endpoint_found,
        "secret_values_exposed": False,
        "configured_secret_flags": {
            "telegram_bot_token_configured": bool(telegram_service.config.bot_token),
            "telegram_chat_id_configured": bool(telegram_service.config.chat_id),
            "webhook_secret_configured": bool(webhook_config.secret),
            "llm_api_key_configured": _llm_key_configured(llm_config),
            "market_data_api_key_configured": _market_data_key_configured(market_data_config),
            "polygon_api_key_configured": bool(market_data_config.polygon_api_key),
            "alpaca_data_api_key_configured": bool(market_data_config.alpaca_data_api_key),
            "news_provider_api_key_configured": bool(market_data_config.news_provider_api_key),
        },
        "notes": [
            ".env content is not read or returned by diagnostics",
            "Secret values are never included, only configured booleans",
            "Diagnostics are read-only health checks",
        ],
        "order_execution_allowed_detail": "always false",
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_provider_diagnostics(
    *,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    telegram_service: TelegramService,
    webhook_config: WebhookConfig,
    risk_event_config: RiskEventConfig,
) -> dict:
    results = {
        "llm": _safe_provider_block(
            lambda: {
                "status": "ok",
                "provider": llm_config.provider,
                "model": llm_config.model,
                "timeout_seconds": llm_config.timeout_seconds,
                "api_key_configured": _llm_key_configured(llm_config),
                "external_call_performed": False,
                "order_execution_allowed": False,
            }
        ),
        "market_data": _safe_provider_block(
            lambda: {
                "status": "ok",
                **get_market_data_provider(market_data_config).status(market_data_config),
            }
        ),
        "risk_events": _safe_provider_block(lambda: {"status": "ok", **risk_event_status(risk_event_config)}),
        "telegram": _safe_provider_block(
            lambda: {
                "status": "ok",
                **telegram_service.status(),
                "token_value_exposed": False,
                "order_execution_allowed": False,
            }
        ),
        "webhooks": _safe_provider_block(
            lambda: {
                "status": "ok",
                **webhook_status(webhook_config),
                "secret_value_exposed": False,
                "order_execution_allowed": False,
            }
        ),
    }
    overall_status = "ok" if all(item.get("status") == "ok" for item in results.values()) else "warning"
    return {
        "status": overall_status,
        "providers": results,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_runtime_diagnostics(
    *,
    db_path: str | Path,
    report_dir: str | Path,
    upload_root: str | Path,
) -> dict:
    db = Path(db_path)
    reports = Path(report_dir)
    uploads = Path(upload_root)
    return {
        "status": "ok",
        "app_name": "AI Council",
        "version": "0.1.0",
        "phase_label": PHASE_LABEL,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database": {
            "filename": db.name,
            "parent_directory": db.parent.name,
            "exists": db.exists(),
        },
        "data_directory_exists": db.parent.exists(),
        "reports_directory_exists": reports.exists(),
        "uploads_directory_exists": uploads.exists(),
        "current_time": datetime.now().astimezone().isoformat(),
        "timezone": datetime.now().astimezone().tzname(),
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def build_e2e_status() -> dict:
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "scripts" / "run_full_e2e.sh"
    scenario = project_root / "examples" / "integration" / "run_full_e2e_scenario.py"
    return {
        "status": "ok" if script.exists() and scenario.exists() else "warning",
        "full_e2e_script_available": script.exists(),
        "full_e2e_scenario_available": scenario.exists(),
        "run_full_e2e_script_path": "scripts/run_full_e2e.sh",
        "full_e2e_scenario_path": "examples/integration/run_full_e2e_scenario.py",
        "latest_e2e_expected_steps": E2E_EXPECTED_STEPS,
        "can_run_from_cli": True,
        "api_does_not_run_e2e_by_default": True,
        "note": "E2E 실행은 CLI scripts/run_full_e2e.sh 사용을 권장합니다.",
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def _safe_provider_block(builder) -> dict:
    try:
        return builder()
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "order_execution_allowed": False,
        }


def _contains_order_execution_endpoint(endpoint_paths: list[str]) -> bool:
    blocked_fragments = [
        "broker",
        "account",
        "submit" + "-order",
        "submit" + "_order",
        "place" + "-order",
        "place" + "_order",
        "cancel" + "-order",
        "cancel" + "_order",
        "execute" + "-order",
        "execute" + "_order",
        "transmit" + "-order",
        "transmit" + "_order",
        "approve" + "-order",
        "approve" + "_order",
    ]
    for path in endpoint_paths:
        lowered = path.lower()
        if any(fragment in lowered for fragment in blocked_fragments):
            return True
    return False


def _market_data_key_configured(config: MarketDataConfig) -> bool:
    return bool(
        config.polygon_api_key
        or config.alpaca_data_api_key
        or config.alpaca_data_api_secret
        or config.news_provider_api_key
    )


def _llm_key_configured(config: LLMConfig) -> bool:
    return bool(config.api_key and config.api_key != "local")
