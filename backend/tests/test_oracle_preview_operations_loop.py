from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "examples" / "oracle_operations" / "run_preview_operations_loop.py"


def load_module():
    spec = importlib.util.spec_from_file_location("oracle_preview_operations_loop", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_config(module, tmp_path, **overrides):
    values = {
        "base_url": "http://127.0.0.1:8000",
        "profile": "us_trader_oracle_v1",
        "local_inbox": tmp_path / "inbox",
        "state_path": tmp_path / "state.json",
        "log_path": tmp_path / "preview.log",
        "portfolio_name": "Oracle Preview Paper Portfolio",
        "secret": None,
        "timeout": 1.0,
        "skip_remote_pull": True,
        "oracle_host": None,
        "oracle_user": None,
        "oracle_key": None,
        "oracle_outbox_dir": None,
        "paper_policy": "risk_gate_conservative",
        "max_notional_per_trade": 100.0,
        "allow_only_decision": False,
        "telegram_alerts_enabled": False,
        "telegram_bot_token": None,
        "telegram_chat_id": None,
        "telegram_timeout": 1.0,
    }
    values.update(overrides)
    return module.LoopConfig(**values)


def test_validate_signal_payload_accepts_preview_signal():
    module = load_module()
    payload = {
        "source": "us_trader_oracle_manual_preview",
        "signal_id": "manual_preview_001",
        "symbol": "TESTA",
        "signal": "manual_preview_signal",
        "action": "buy",
        "price": 0.82,
        "volume": 12500000,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": False,
    }

    module.validate_signal_payload(payload)
    assert module.build_signal_identity(payload, Path("us_trader_preview_signal.json")) == (
        "us_trader_oracle_manual_preview:manual_preview_001"
    )


def test_validate_signal_payload_rejects_order_execution_allowed_true():
    module = load_module()
    payload = {
        "source": "us_trader_oracle_manual_preview",
        "signal_id": "manual_preview_001",
        "symbol": "TESTA",
        "signal": "manual_preview_signal",
        "action": "buy",
        "price": 0.82,
        "volume": 12500000,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": True,
    }

    try:
        module.validate_signal_payload(payload)
    except ValueError as exc:
        assert "order_execution_allowed=false" in str(exc)
    else:
        raise AssertionError("unsafe order execution flag must be rejected")


def test_validate_signal_payload_rejects_order_like_fields():
    module = load_module()
    payload = {
        "source": "us_trader_oracle_manual_preview",
        "signal_id": "manual_preview_002",
        "symbol": "TESTA",
        "signal": "manual_preview_signal",
        "action": "buy",
        "price": 0.82,
        "volume": 12500000,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "quantity": 100,
        "stop_loss": 0.75,
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": False,
    }

    try:
        module.validate_signal_payload(payload)
    except ValueError as exc:
        assert "order-like fields" in str(exc)
        assert "quantity" in str(exc)
        assert "stop_loss" in str(exc)
    else:
        raise AssertionError("order-like signal fields must be rejected in preview mode")


def test_validate_simulation_against_review_rejects_high_risk_entry():
    module = load_module()

    try:
        module.validate_simulation_against_review(
            {"decision": "HOLD", "risk_level": "high"},
            {"actions": ["simulated_entry"]},
        )
    except RuntimeError as exc:
        assert "must not create a simulated entry" in str(exc)
    else:
        raise AssertionError("HOLD/high risk simulated entry must be rejected")


def test_state_duplicate_marker_is_safe(tmp_path):
    module = load_module()
    state_path = tmp_path / "state.json"
    state = module.load_state(state_path)
    module.mark_duplicate(state, "source:signal", Path("signal.json"))
    module.save_state(state_path, state)

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["skipped_duplicates"][0]["signal_identity"] == "source:signal"
    assert saved["order_execution_allowed"] is False
    assert saved["simulation_only"] is True


def test_mark_duplicate_records_once_per_identity(tmp_path):
    module = load_module()
    state = module.load_state(tmp_path / "state.json")

    assert module.mark_duplicate(state, "source:signal", Path("signal.json")) is True
    assert module.mark_duplicate(state, "source:signal", Path("signal.json")) is False
    assert module.mark_duplicate(state, "source:signal", Path("signal.json")) is False

    assert len(state["skipped_duplicates"]) == 1
    assert state["skipped_duplicates"][0]["skip_count"] == 3


def test_mark_failed_records_once_per_file_and_error(tmp_path):
    module = load_module()
    state = module.load_state(tmp_path / "state.json")

    assert module.mark_failed(state, Path("bad.json"), "invalid JSON") is True
    assert module.mark_failed(state, Path("bad.json"), "invalid JSON") is False
    assert module.mark_failed(state, Path("bad.json"), "missing fields") is True

    assert len(state["failed"]) == 2
    assert state["failed"][0]["fail_count"] == 2


def test_load_state_compacts_legacy_duplicate_entries(tmp_path):
    module = load_module()
    state_path = tmp_path / "state.json"
    legacy_entries = [
        {
            "signal_identity": "source:signal",
            "file": "signal.json",
            "skipped_at": f"2026-07-01T00:{index:02d}:00+00:00",
            "order_execution_allowed": False,
            "simulation_only": True,
        }
        for index in range(50)
    ]
    state_path.write_text(
        json.dumps({"version": 1, "skipped_duplicates": legacy_entries}),
        encoding="utf-8",
    )

    state = module.load_state(state_path)

    assert len(state["skipped_duplicates"]) == 1
    entry = state["skipped_duplicates"][0]
    assert entry["signal_identity"] == "source:signal"
    assert entry["skip_count"] == 50
    assert entry["first_skipped_at"] == "2026-07-01T00:00:00+00:00"
    assert entry["last_skipped_at"] == "2026-07-01T00:49:00+00:00"


def test_preview_loop_config_uses_placeholders_only():
    config_path = ROOT / "examples" / "oracle_operations" / "preview_loop_config.example.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)

    assert payload["order_execution_allowed"] is False
    assert payload["simulation_only"] is True
    assert "<oracle-host>" in serialized
    assert "<path-to-private-key>" in serialized
    assert "168.110." not in serialized
    assert "/.ssh/" not in serialized


def test_script_and_readme_document_safety_boundary():
    script = (ROOT / "scripts" / "run_oracle_preview_operations_once.sh").read_text(encoding="utf-8")
    readme = (ROOT / "examples" / "oracle_operations" / "README.md").read_text(encoding="utf-8")

    assert "run_preview_operations_loop.py" in script
    assert "order_execution_allowed=false" in readme
    assert "Oracle outbox files are never deleted or moved" in readme
    assert "Poll mode is available only with `--poll`" in readme
    assert "Telegram Problem Alerts" in readme
    assert "ORACLE_PREVIEW_LOOP_TELEGRAM_ALERTS" in readme


def test_problem_alert_disabled_without_configuration(tmp_path):
    module = load_module()
    config = make_config(module, tmp_path)

    result = module.send_problem_alert(config, "signal_processing_failed", {"file": "bad.json"})

    assert result["status"] == "disabled"
    assert result["sent"] is False
    assert result["order_execution_allowed"] is False
    assert result["simulation_only"] is True


def test_problem_alert_sends_without_leaking_token(monkeypatch, tmp_path):
    module = load_module()
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    config = make_config(
        module,
        tmp_path,
        telegram_alerts_enabled=True,
        telegram_bot_token="12345:SECRET_TOKEN",
        telegram_chat_id="999",
    )

    result = module.send_problem_alert(
        config,
        "signal_processing_failed",
        {
            "file": "bad_signal.json",
            "error": "unsafe key at /Users/example/.ssh/oracle-preview-test.key for 203.0.113.10",
        },
    )

    assert result["status"] == "sent"
    assert result["sent"] is True
    assert "SECRET_TOKEN" not in json.dumps(result)
    assert "SECRET_TOKEN" not in captured["body"]["text"]
    assert "203.0.113." not in captured["body"]["text"]
    assert "/.ssh/" not in captured["body"]["text"]
    assert "AI Council Oracle Preview Loop 알림" in captured["body"]["text"]
    assert "실제 주문 실행: 없음" in captured["body"]["text"]
    assert "order_execution_allowed=false" in captured["body"]["text"]


def test_problem_alert_repeat_suppressed_by_cooldown(monkeypatch, tmp_path):
    module = load_module()
    send_attempts = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        send_attempts.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    config = make_config(
        module,
        tmp_path,
        telegram_alerts_enabled=True,
        telegram_bot_token="12345:SECRET_TOKEN",
        telegram_chat_id="999",
        telegram_alert_cooldown_seconds=3600.0,
    )
    state = module.load_state(tmp_path / "state.json")
    context = {"file": "bad.json", "error": "invalid JSON"}

    first = module.send_problem_alert(config, "signal_processing_failed", context, state=state)
    second = module.send_problem_alert(config, "signal_processing_failed", context, state=state)
    other = module.send_problem_alert(
        config, "signal_processing_failed", {"file": "other.json", "error": "invalid JSON"}, state=state
    )

    assert first["status"] == "sent"
    assert second["status"] == "suppressed_cooldown"
    assert second["sent"] is False
    assert other["status"] == "sent"
    assert len(send_attempts) == 2
    alert_entry = next(iter(state["telegram_alerted"].values()))
    assert alert_entry["sent_count"] >= 1


def test_problem_alert_without_state_still_sends(monkeypatch, tmp_path):
    module = load_module()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    monkeypatch.setattr(module.urllib.request, "urlopen", lambda request, timeout: FakeResponse())
    config = make_config(
        module,
        tmp_path,
        telegram_alerts_enabled=True,
        telegram_bot_token="12345:SECRET_TOKEN",
        telegram_chat_id="999",
    )

    result = module.send_problem_alert(config, "signal_processing_failed", {"file": "bad.json"})

    assert result["status"] == "sent"


def test_problem_alert_http_error_redacts_response(monkeypatch, tmp_path):
    module = load_module()

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "unauthorized",
            hdrs=None,
            fp=FakeErrorBody(b'{"description":"api_key=SECRET_TOKEN from 203.0.113.10"}'),
        )

    class FakeErrorBody:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return self.payload

        def close(self):
            return None

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    config = make_config(
        module,
        tmp_path,
        telegram_alerts_enabled=True,
        telegram_bot_token="12345:SECRET_TOKEN",
        telegram_chat_id="999",
    )

    result = module.send_problem_alert(config, "signal_processing_failed", {"file": "bad.json"})

    assert result["status"] == "error"
    assert "SECRET_TOKEN" not in json.dumps(result)
    assert "203.0.113." not in json.dumps(result)


def test_subprocess_error_message_redacts_key_path():
    module = load_module()
    exc = module.subprocess.CalledProcessError(
        1,
        ["ssh", "-i", "/Users/example/.ssh/oracle-preview-test.key"],
        stderr="failed /Users/example/.ssh/oracle-preview-test.key 203.0.113.10",
    )

    message = module.safe_error_message(exc)

    assert "/.ssh/" not in message
    assert "203.0.113." not in message
    assert "<path-to-private-key>" in message


def test_preview_loop_source_has_no_order_execution_calls():
    source = MODULE_PATH.read_text(encoding="utf-8")
    dangerous_call_patterns = [
        "submit" + "_order(",
        "place" + "_order(",
        "send" + "_order(",
        "create" + "_order(",
        "cancel" + "_order(",
        "close" + "_position(",
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "systemctl reload",
        " rm ",
        " mv ",
        " chmod",
        " chown",
    ]

    for pattern in dangerous_call_patterns:
        assert pattern not in source
