import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SIDECAR_DIR = ROOT / "examples" / "oracle_sidecar"
SAMPLE_OUTBOX = SIDECAR_DIR / "sample_outbox"
PATCH_DRAFTS = SIDECAR_DIR / "patch_drafts"


def test_oracle_sidecar_sample_outbox_json_validation():
    expected = {
        "us_trader_signal_001.json",
        "us_trader_signal_order_like.json",
        "us_trader_signal_high_risk.json",
    }
    found = {path.name for path in SAMPLE_OUTBOX.glob("*.json")}
    assert found >= expected

    for path in SAMPLE_OUTBOX.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["source"] == "us_trader_oracle"
        assert payload["symbol"].startswith("TEST")
        assert payload["order_execution_allowed"] is False


def test_oracle_sidecar_dry_run():
    script = SIDECAR_DIR / "us_trader_signal_outbox_bridge.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--outbox",
            str(SAMPLE_OUTBOX),
            "--mode",
            "preview",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    body = json.loads(result.stdout)
    assert body["status"] == "passed"
    assert body["mode"] == "preview"
    assert body["dry_run"] is True
    assert body["files_seen"] == 3
    assert body["order_execution_allowed"] is False
    assert body["safety"]["broker_api_used"] is False
    assert body["safety"]["oracle_service_touched"] is False
    warning_text = " ".join(
        warning
        for item in body["results"]
        for warning in item.get("adapter_warnings", [])
    )
    assert "order-like fields ignored for safety" in warning_text


def test_oracle_sidecar_preview_command_construction():
    source = (SIDECAR_DIR / "us_trader_signal_outbox_bridge.py").read_text(encoding="utf-8")

    assert "/api/webhooks/normalize-preview" in source
    assert "/api/webhooks/trade-signal" in source
    assert "US_TRADER_BRIDGE_MODE" in source
    assert "preview" in source
    assert "review" in source
    assert "order_execution_allowed" in source


def test_signal_exporter_hook_example_exports_review_only_payload(tmp_path):
    module_path = SIDECAR_DIR / "signal_exporter_hook_example.py"
    spec = importlib.util.spec_from_file_location("signal_exporter_hook_example", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    payload = module.build_ai_council_signal(
        symbol="testa",
        signal="breakout",
        raw_side="buy",
        price=0.82,
        volume=12500000,
    )
    output = module.export_ai_council_signal(payload, tmp_path)
    written = json.loads(output.read_text(encoding="utf-8"))

    assert output.exists()
    assert written["symbol"] == "TESTA"
    assert written["action"] == "buy"
    assert written["source"] == "us_trader_oracle"
    assert written["order_execution_allowed"] is False
    assert written["review_only"] is True


def test_patch_draft_exporter_module_import_build_validate_and_atomic_write(tmp_path):
    module_path = PATCH_DRAFTS / "ai_council_signal_exporter_module.py"
    spec = importlib.util.spec_from_file_location("ai_council_signal_exporter_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    payload = module.build_ai_council_signal(
        symbol="testa",
        strategy_signal="RSI_DIP",
        raw_side="buy",
        price=0.82,
        volume=12500000,
        timeframe="5m",
        indicators={"rsi": 68},
        risk_context={"source_function": "scan_and_enter"},
        news_headlines=[],
    )
    payload["quantity"] = 1000
    payload["order_type"] = "limit"

    assert module.validate_export_payload(payload) is True
    output = module.export_ai_council_signal(payload, tmp_path)
    written = json.loads(output.read_text(encoding="utf-8"))

    assert output.exists()
    assert not list(tmp_path.glob("*.tmp"))
    assert written["source"] == "us_trader_oracle"
    assert written["symbol"] == "TESTA"
    assert written["action"] == "buy"
    assert written["review_only"] is True
    assert written["order_execution_allowed"] is False
    assert "order-like fields preserved as review context only" in written["adapter_warnings"]


def test_signal_exporter_hook_example_has_no_broker_or_order_calls():
    source = (SIDECAR_DIR / "signal_exporter_hook_example.py").read_text(encoding="utf-8")
    forbidden_call_patterns = [
        "place_order(",
        "check_exits(",
        "force_close_all(",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
        "systemctl",
        "paramiko",
    ]
    for pattern in forbidden_call_patterns:
        assert pattern not in source


def test_patch_draft_exporter_module_has_no_network_broker_or_order_calls():
    source = (PATCH_DRAFTS / "ai_council_signal_exporter_module.py").read_text(encoding="utf-8")
    forbidden_patterns = [
        "requests",
        "urllib",
        "httpx",
        "systemctl",
        "paramiko",
        "ssh ",
        "place_order(",
        "check_exits(",
        "force_close_all(",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in source


def test_oracle_sidecar_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_SIDECAR_PLAN.md").read_text(encoding="utf-8")
    patch_docs = (ROOT / "docs" / "US_TRADER_ORACLE_EXPORT_HOOK_PATCH_DRAFT.md").read_text(
        encoding="utf-8"
    )
    readme = (SIDECAR_DIR / "README.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in patch_docs
    assert "절대 적용하면 안 되는 위치" in patch_docs
    assert "order_execution_allowed" in docs
    assert "Level 0: Dry-run" in docs
    assert "절대 연결하면 안 되는 위치" in docs
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in readme


def test_readme_includes_phase_24c_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24C Oracle Sidecar Signal Bridge Plan" in readme
    assert "scripts/run_oracle_sidecar_smoke.sh" in readme
    assert "Oracle live bot 직접 수정 없음" in readme
    assert "order_execution_allowed=false" in readme


def test_readme_includes_phase_24d_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24D Oracle Export Hook Patch Draft" in readme
    assert "scripts/run_oracle_export_hook_preflight.sh" in readme
    assert "place_order" in readme
    assert "order_execution_allowed=false" in readme


def test_oracle_sidecar_smoke_script_file_exists():
    assert (ROOT / "examples" / "integration" / "run_oracle_sidecar_smoke.py").exists()
    assert (ROOT / "scripts" / "run_oracle_sidecar_smoke.sh").exists()


def test_oracle_export_hook_preflight_script_file_exists():
    assert (SIDECAR_DIR / "oracle_export_hook_preflight.py").exists()
    assert (ROOT / "scripts" / "run_oracle_export_hook_preflight.sh").exists()


def test_oracle_sidecar_order_execution_allowed_always_false():
    files = [
        SIDECAR_DIR / "us_trader_signal_outbox_bridge.py",
        SIDECAR_DIR / "signal_exporter_hook_example.py",
        SIDECAR_DIR / "oracle_export_hook_preflight.py",
        PATCH_DRAFTS / "ai_council_signal_exporter_module.py",
        *SAMPLE_OUTBOX.glob("*.json"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text


def test_oracle_sidecar_code_does_not_add_broker_or_order_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            SIDECAR_DIR / "us_trader_signal_outbox_bridge.py",
            SIDECAR_DIR / "signal_exporter_hook_example.py",
        ]
    )
    forbidden_terms = [
        "BrokerClient",
        "OrderRequest",
        "TradingClient",
        "tradeapi.REST",
        "alpaca_trade_api",
        "ib_insync",
        "kis_order",
    ]
    for term in forbidden_terms:
        assert term not in source
