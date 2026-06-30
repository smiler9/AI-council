from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .council import KOREAN_SAFETY_BOUNDARY
from .llm.config import LLMConfig
from .market_data import MarketDataConfig
from .repository import (
    create_watchlist_schedule,
    create_watchlist_schedule_run,
    delete_watchlist_schedule,
    get_watchlist,
    get_watchlist_schedule,
    list_watchlist_schedule_runs,
    list_watchlist_schedules,
    update_watchlist_schedule,
)
from .risk_events import RiskEventConfig
from .schemas import WatchlistScheduleCreate, WatchlistScheduleUpdate
from .services.telegram_service import TelegramService
from .watchlists import (
    WatchlistInputError,
    run_watchlist_review,
    send_watchlist_review_telegram,
)


DEFAULT_TIMEZONE = "Asia/Seoul"
DEFAULT_RUN_TIME = "08:30"
SUPPORTED_CADENCES = {
    "manual_only",
    "daily",
    "weekdays",
    "hourly_stub",
    "market_open_stub",
    "market_close_stub",
}


class WatchlistScheduleError(ValueError):
    pass


def create_schedule_for_watchlist(
    watchlist_id: str,
    payload: WatchlistScheduleCreate,
    *,
    db_path: str | Path | None,
) -> dict:
    if not get_watchlist(watchlist_id, db_path):
        raise WatchlistScheduleError("Watchlist not found")
    name = payload.name.strip()
    if not name:
        raise WatchlistScheduleError("Schedule name is required")
    cadence = payload.cadence
    run_time = normalize_run_time(payload.run_time, cadence)
    timezone = normalize_timezone(payload.timezone)
    next_run_at = compute_next_run_at(cadence, run_time, timezone)
    return create_watchlist_schedule(
        watchlist_id=watchlist_id,
        name=name,
        enabled=payload.enabled,
        cadence=cadence,
        run_time=run_time,
        timezone=timezone,
        auto_send_telegram=payload.auto_send_telegram,
        next_run_at=next_run_at,
        db_path=db_path,
    )


def update_schedule(
    schedule_id: str,
    payload: WatchlistScheduleUpdate,
    *,
    db_path: str | Path | None,
) -> dict:
    existing = get_watchlist_schedule(schedule_id, db_path)
    if not existing:
        raise WatchlistScheduleError("Schedule not found")
    update_data = payload.model_dump(exclude_unset=True)
    cadence = update_data.get("cadence", existing["cadence"])
    timezone = normalize_timezone(update_data.get("timezone", existing["timezone"]))
    run_time = normalize_run_time(update_data.get("run_time", existing.get("run_time")), cadence)
    next_run_at = compute_next_run_at(cadence, run_time, timezone)
    name = update_data.get("name")
    if isinstance(name, str):
        name = name.strip()
        if not name:
            raise WatchlistScheduleError("Schedule name is required")
    updated = update_watchlist_schedule(
        schedule_id,
        name=name if isinstance(name, str) else None,
        enabled=update_data.get("enabled"),
        cadence=cadence,
        run_time=run_time,
        clear_run_time=run_time is None,
        timezone=timezone,
        auto_send_telegram=update_data.get("auto_send_telegram"),
        next_run_at=next_run_at,
        clear_next_run_at=next_run_at is None,
        db_path=db_path,
    )
    return updated


def delete_schedule(schedule_id: str, *, db_path: str | Path | None) -> dict:
    deleted = delete_watchlist_schedule(schedule_id, db_path)
    if not deleted:
        raise WatchlistScheduleError("Schedule not found")
    return {
        "deleted": True,
        "schedule": deleted,
        "order_execution_allowed": False,
    }


def run_schedule_now(
    schedule_id: str,
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    risk_event_config: RiskEventConfig,
    telegram_service: TelegramService,
) -> dict:
    schedule = get_watchlist_schedule(schedule_id, db_path)
    if not schedule:
        raise WatchlistScheduleError("Schedule not found")
    started_at = _now_iso()
    try:
        review = run_watchlist_review(
            schedule["watchlist_id"],
            db_path=db_path,
            report_dir=report_dir,
            llm_config=llm_config,
            market_data_config=market_data_config,
            risk_event_config=risk_event_config,
        )
        telegram_status = _send_telegram_if_requested(
            schedule=schedule,
            review_id=review["id"],
            db_path=db_path,
            telegram_service=telegram_service,
        )
        finished_at = _now_iso()
        next_run_at = compute_next_run_at(
            schedule["cadence"],
            schedule.get("run_time"),
            schedule.get("timezone") or DEFAULT_TIMEZONE,
            now=_parse_iso(finished_at),
        )
        update_watchlist_schedule(
            schedule_id,
            last_run_at=finished_at,
            next_run_at=next_run_at,
            clear_next_run_at=next_run_at is None,
            db_path=db_path,
        )
        status = "completed"
        if schedule.get("auto_send_telegram") and telegram_status.get("status") == "disabled":
            status = "telegram_disabled"
        run = create_watchlist_schedule_run(
            schedule_id=schedule_id,
            watchlist_id=schedule["watchlist_id"],
            watchlist_review_id=review["id"],
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            summary={
                "watchlist_review_id": review["id"],
                "summary": review.get("summary", {}),
                "highest_risk_level": review.get("highest_risk_level"),
                "ticker_count": review.get("ticker_count"),
                "order_execution_allowed": False,
            },
            telegram_status=telegram_status,
            db_path=db_path,
        )
        return {
            "schedule": get_watchlist_schedule(schedule_id, db_path),
            "review": review,
            "run": run,
            "telegram": telegram_status,
            "order_execution_allowed": False,
            "safety_boundary": KOREAN_SAFETY_BOUNDARY,
        }
    except Exception as exc:
        finished_at = _now_iso()
        run = create_watchlist_schedule_run(
            schedule_id=schedule_id,
            watchlist_id=schedule["watchlist_id"],
            watchlist_review_id=None,
            status="failed",
            started_at=started_at,
            finished_at=finished_at,
            summary={"order_execution_allowed": False},
            telegram_status={},
            error_message=str(exc),
            db_path=db_path,
        )
        next_run_at = compute_next_run_at(
            schedule["cadence"],
            schedule.get("run_time"),
            schedule.get("timezone") or DEFAULT_TIMEZONE,
            now=_parse_iso(finished_at),
        )
        update_watchlist_schedule(
            schedule_id,
            last_run_at=finished_at,
            next_run_at=next_run_at,
            clear_next_run_at=next_run_at is None,
            db_path=db_path,
        )
        raise WatchlistScheduleError(f"Schedule run failed: {exc}; run_id={run['id']}") from exc


def run_due_schedules(
    *,
    db_path: str | Path | None,
    report_dir: str | Path | None,
    llm_config: LLMConfig,
    market_data_config: MarketDataConfig,
    risk_event_config: RiskEventConfig,
    telegram_service: TelegramService,
    now: datetime | None = None,
) -> dict:
    schedules = list_watchlist_schedules(db_path)
    current = now or datetime.now(UTC)
    due = [schedule for schedule in schedules if is_schedule_due(schedule, current)]
    results = []
    errors = []
    for schedule in due:
        try:
            result = run_schedule_now(
                schedule["id"],
                db_path=db_path,
                report_dir=report_dir,
                llm_config=llm_config,
                market_data_config=market_data_config,
                risk_event_config=risk_event_config,
                telegram_service=telegram_service,
            )
            results.append(result)
        except WatchlistScheduleError as exc:
            errors.append({"schedule_id": schedule["id"], "error": str(exc)})
    return {
        "due_count": len(due),
        "executed_count": len(results),
        "failed_count": len(errors),
        "skipped_count": len(schedules) - len(due),
        "results": results,
        "errors": errors,
        "order_execution_allowed": False,
        "safety_boundary": KOREAN_SAFETY_BOUNDARY,
    }


def is_schedule_due(schedule: dict, now: datetime | None = None) -> bool:
    if not schedule.get("enabled"):
        return False
    next_run_at = schedule.get("next_run_at")
    if not next_run_at:
        return False
    next_dt = _parse_iso(next_run_at)
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return next_dt <= current.astimezone(UTC)


def compute_next_run_at(
    cadence: str,
    run_time: str | None,
    timezone: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> str | None:
    if cadence not in SUPPORTED_CADENCES:
        raise WatchlistScheduleError(f"Unsupported cadence: {cadence}")
    if cadence == "manual_only":
        return None
    current_utc = now or datetime.now(UTC)
    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=UTC)
    if cadence == "hourly_stub":
        return _format_utc(current_utc.astimezone(UTC) + timedelta(hours=1))
    if cadence in {"market_open_stub", "market_close_stub"}:
        return None

    zone = _zoneinfo(timezone)
    local_now = current_utc.astimezone(zone)
    hour, minute = _parse_run_time(run_time or DEFAULT_RUN_TIME)
    candidate = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cadence == "daily":
        if candidate <= local_now:
            candidate = candidate + timedelta(days=1)
        return _format_utc(candidate.astimezone(UTC))
    if cadence == "weekdays":
        for day_offset in range(0, 8):
            candidate_day = (local_now + timedelta(days=day_offset)).replace(
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if candidate_day.weekday() >= 5:
                continue
            if candidate_day > local_now:
                return _format_utc(candidate_day.astimezone(UTC))
        return None
    return None


def normalize_run_time(run_time: str | None, cadence: str) -> str | None:
    if cadence in {"manual_only", "hourly_stub", "market_open_stub", "market_close_stub"}:
        return None if cadence == "manual_only" else run_time
    value = (run_time or DEFAULT_RUN_TIME).strip()
    _parse_run_time(value)
    return value


def normalize_timezone(timezone: str | None) -> str:
    value = (timezone or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(value)
        return value
    except ZoneInfoNotFoundError:
        return DEFAULT_TIMEZONE


def _send_telegram_if_requested(
    *,
    schedule: dict,
    review_id: str,
    db_path: str | Path | None,
    telegram_service: TelegramService,
) -> dict:
    if not schedule.get("auto_send_telegram"):
        return {
            "requested": False,
            "sent": False,
            "status": "not_requested",
            "order_execution_allowed": False,
        }
    result = send_watchlist_review_telegram(
        review_id,
        db_path=db_path,
        telegram_service=telegram_service,
    )
    return {
        "requested": True,
        "order_execution_allowed": False,
        **result,
    }


def _parse_run_time(value: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError) as exc:
        raise WatchlistScheduleError("run_time must use HH:MM format") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise WatchlistScheduleError("run_time must use HH:MM format")
    return hour, minute


def _zoneinfo(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def _now_iso() -> str:
    return _format_utc(datetime.now(UTC))
