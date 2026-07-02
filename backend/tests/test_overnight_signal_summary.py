from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "examples" / "oracle_operations" / "send_overnight_signal_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location("overnight_signal_summary", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


NOW = datetime(2026, 7, 2, 22, 30, tzinfo=timezone.utc)


def test_summary_message_with_signals():
    module = load_module()
    reviews = [
        {
            "ticker": "ABCD",
            "decision": "HOLD",
            "risk_level": "high",
            "simulation_actions": ["simulated_skip"],
        },
        {
            "ticker": "EFGH",
            "decision": "ALLOW",
            "risk_level": "medium",
            "simulation_actions": ["simulated_entry"],
        },
    ]
    failed = [{"file": "bad.json", "error": "invalid JSON"}]
    paper = {"cash": 9900.0, "total_value": 10000.0, "open_positions": 1, "total_trades": 4}

    message = module.build_summary_message(reviews, failed, paper, 24.0, NOW)

    assert "AI Council 야간 signal 처리 요약" in message
    assert "처리된 signal: 2건 | 실패: 1건" in message
    assert "판단: ALLOW 1 / HOLD 1" in message
    assert "가상 진입 1 / 가상 skip 1" in message
    assert "- ABCD: HOLD (risk high)" in message
    assert "- EFGH: ALLOW (risk medium)" in message
    assert "bad.json" in message
    assert "총가치 $10,000.00" in message
    assert "order_execution_allowed=false" in message


def test_summary_message_without_signals():
    module = load_module()
    message = module.build_summary_message([], [], None, 24.0, NOW)

    assert "밤새 신규 signal이 없었습니다" in message
    assert "simulation_only=true" in message


def test_entries_in_window_filters_by_timestamp():
    module = load_module()
    since = NOW - timedelta(hours=24)
    entries = [
        {"processed_at": (NOW - timedelta(hours=2)).isoformat()},
        {"processed_at": (NOW - timedelta(hours=30)).isoformat()},
        {"processed_at": "not-a-date"},
    ]

    kept = module.entries_in_window(entries, "processed_at", since)

    assert len(kept) == 1


def test_load_env_file_strips_export_and_quotes(tmp_path, monkeypatch):
    module = load_module()
    env_file = tmp_path / "test.env"
    env_file.write_text(
        'export QUOTED_TOKEN="123:abc"\n'
        "PLAIN_VALUE=hello\n"
        "SINGLE_QUOTED='world'\n",
        encoding="utf-8",
    )
    for key in ("QUOTED_TOKEN", "PLAIN_VALUE", "SINGLE_QUOTED"):
        monkeypatch.delenv(key, raising=False)

    module.load_env_file(env_file)

    import os
    assert os.environ["QUOTED_TOKEN"] == "123:abc"
    assert os.environ["PLAIN_VALUE"] == "hello"
    assert os.environ["SINGLE_QUOTED"] == "world"
    for key in ("QUOTED_TOKEN", "PLAIN_VALUE", "SINGLE_QUOTED"):
        monkeypatch.delenv(key, raising=False)


def test_summary_message_never_enables_orders():
    module = load_module()
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "order_execution_allowed=false" in module.build_summary_message([], [], None, 12.0, NOW)
    for pattern in ["place" + "_order(", "submit" + "_order(", "systemctl "]:
        assert pattern not in source
