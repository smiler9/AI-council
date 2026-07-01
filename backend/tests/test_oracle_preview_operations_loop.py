from __future__ import annotations

import importlib.util
import json
import sys
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
