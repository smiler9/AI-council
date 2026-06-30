from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.repository import update_watchlist_schedule
from app.watchlist_schedules import compute_next_run_at


def _create_watchlist(client, name: str = "Schedule Watchlist", tickers: list[str] | None = None) -> dict:
    response = client.post(
        "/api/watchlists",
        json={
            "name": name,
            "tickers": tickers or ["TESTA", "TESTB"],
            "review_mode": "penny_stock_risk",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_schedule(
    client,
    watchlist_id: str,
    *,
    cadence: str = "daily",
    enabled: bool = True,
    auto_send_telegram: bool = False,
) -> dict:
    response = client.post(
        f"/api/watchlists/{watchlist_id}/schedules",
        json={
            "name": "매일 장전 리스크 점검",
            "enabled": enabled,
            "cadence": cadence,
            "run_time": "08:30",
            "timezone": "Asia/Seoul",
            "auto_send_telegram": auto_send_telegram,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_watchlist_schedule_create_and_list(client):
    watchlist = _create_watchlist(client)

    schedule = _create_schedule(client, watchlist["id"])
    listed = client.get("/api/watchlist-schedules")
    scoped = client.get(f"/api/watchlists/{watchlist['id']}/schedules")
    detail = client.get(f"/api/watchlist-schedules/{schedule['id']}")

    assert schedule["watchlist_id"] == watchlist["id"]
    assert schedule["cadence"] == "daily"
    assert schedule["run_time"] == "08:30"
    assert schedule["next_run_at"] is not None
    assert schedule["order_execution_allowed"] is False
    assert listed.status_code == 200
    assert any(item["id"] == schedule["id"] for item in listed.json())
    assert scoped.status_code == 200
    assert scoped.json()[0]["id"] == schedule["id"]
    assert detail.status_code == 200
    assert detail.json()["order_execution_allowed"] is False


def test_watchlist_schedule_invalid_watchlist_rejected(client):
    response = client.post(
        "/api/watchlists/missing/schedules",
        json={"name": "Bad", "cadence": "daily", "run_time": "08:30"},
    )

    assert response.status_code == 404


def test_daily_next_run_at_calculation():
    now = datetime(2026, 6, 30, 0, 0, tzinfo=UTC)
    next_run = datetime.fromisoformat(
        compute_next_run_at("daily", "08:30", "Asia/Seoul", now=now)
    )

    assert next_run > now
    local = next_run.astimezone(ZoneInfo("Asia/Seoul"))
    assert local.hour == 8
    assert local.minute == 30


def test_weekdays_next_run_at_skips_weekend():
    friday_after_run_time = datetime(2026, 7, 3, 2, 0, tzinfo=UTC)
    next_run = datetime.fromisoformat(
        compute_next_run_at("weekdays", "08:30", "Asia/Seoul", now=friday_after_run_time)
    )

    local = next_run.astimezone(ZoneInfo("Asia/Seoul"))
    assert local.weekday() == 0
    assert local.hour == 8
    assert local.minute == 30


def test_manual_only_next_run_at_is_null(client):
    watchlist = _create_watchlist(client)
    schedule = _create_schedule(client, watchlist["id"], cadence="manual_only")

    assert compute_next_run_at("manual_only", None, "Asia/Seoul") is None
    assert schedule["next_run_at"] is None
    assert schedule["run_time"] is None


def test_run_now_creates_watchlist_review_and_schedule_run_log(client):
    watchlist = _create_watchlist(client, tickers=["TESTA"])
    schedule = _create_schedule(client, watchlist["id"], cadence="manual_only")

    response = client.post(f"/api/watchlist-schedules/{schedule['id']}/run-now")
    runs = client.get("/api/watchlist-schedule-runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review"]["watchlist_id"] == watchlist["id"]
    assert payload["review"]["ticker_count"] == 1
    assert payload["run"]["status"] == "completed"
    assert payload["run"]["watchlist_review_id"] == payload["review"]["id"]
    assert payload["schedule"]["last_run_at"] is not None
    assert payload["schedule"]["next_run_at"] is None
    assert payload["order_execution_allowed"] is False
    assert runs.status_code == 200
    assert any(item["id"] == payload["run"]["id"] for item in runs.json())


def test_run_due_executes_only_due_schedule(client):
    watchlist = _create_watchlist(client, tickers=["TESTB"])
    schedule = _create_schedule(client, watchlist["id"], cadence="daily")
    past = (datetime.now(UTC) - timedelta(minutes=5)).replace(microsecond=0).isoformat()
    update_watchlist_schedule(schedule["id"], next_run_at=past, db_path=client.app.state.db_path)

    response = client.post("/api/watchlist-schedules/run-due")

    assert response.status_code == 200
    payload = response.json()
    assert payload["due_count"] == 1
    assert payload["executed_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["results"][0]["run"]["watchlist_review_id"]
    assert payload["order_execution_allowed"] is False


def test_disabled_schedule_is_not_run_due(client):
    watchlist = _create_watchlist(client, tickers=["TESTC"])
    schedule = _create_schedule(client, watchlist["id"], cadence="daily", enabled=False)
    past = (datetime.now(UTC) - timedelta(minutes=5)).replace(microsecond=0).isoformat()
    update_watchlist_schedule(schedule["id"], next_run_at=past, db_path=client.app.state.db_path)

    response = client.post("/api/watchlist-schedules/run-due")

    assert response.status_code == 200
    payload = response.json()
    assert payload["due_count"] == 0
    assert payload["executed_count"] == 0
    assert payload["skipped_count"] == 1
    assert payload["order_execution_allowed"] is False


def test_schedule_run_log_filter_and_get(client):
    watchlist = _create_watchlist(client, tickers=["TESTA"])
    schedule = _create_schedule(client, watchlist["id"])
    run_now = client.post(f"/api/watchlist-schedules/{schedule['id']}/run-now")
    run_id = run_now.json()["run"]["id"]

    filtered = client.get(f"/api/watchlist-schedule-runs?schedule_id={schedule['id']}")
    detail = client.get(f"/api/watchlist-schedule-runs/{run_id}")

    assert filtered.status_code == 200
    assert filtered.json()[0]["id"] == run_id
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id
    assert detail.json()["summary"]["order_execution_allowed"] is False
    assert detail.json()["order_execution_allowed"] is False


def test_schedule_telegram_disabled_safe_handling(client):
    watchlist = _create_watchlist(client, tickers=["TESTA"])
    schedule = _create_schedule(client, watchlist["id"], auto_send_telegram=True)

    response = client.post(f"/api/watchlist-schedules/{schedule['id']}/run-now")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["status"] == "telegram_disabled"
    assert payload["telegram"]["requested"] is True
    assert payload["telegram"]["sent"] is False
    assert payload["telegram"]["status"] == "disabled"
    assert payload["run"]["telegram_status"]["order_execution_allowed"] is False
    assert payload["order_execution_allowed"] is False


def test_schedule_order_execution_allowed_always_false(client):
    watchlist = _create_watchlist(client, tickers=["TESTD"])
    schedule = _create_schedule(client, watchlist["id"])

    response = client.post(f"/api/watchlist-schedules/{schedule['id']}/run-now")
    payload = response.json()

    assert response.status_code == 200
    assert payload["order_execution_allowed"] is False
    assert payload["schedule"]["order_execution_allowed"] is False
    assert payload["run"]["order_execution_allowed"] is False
    assert payload["review"]["order_execution_allowed"] is False
    assert all(result["order_execution_allowed"] is False for result in payload["review"]["results"])


def test_watchlist_schedule_code_does_not_add_broker_or_order_execution():
    root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    forbidden_terms = [
        "submit_order",
        "place_order",
        "BrokerClient",
        "OrderRequest",
        "TradingClient",
        "tradeapi.REST",
        "cancel_order",
        "execute_order",
    ]
    for term in forbidden_terms:
        assert term not in source
