from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "US_TRADER_ORACLE_READONLY_READINESS_REPORT.md"
PREVIEW_PLAN = ROOT / "docs" / "US_TRADER_ORACLE_PREVIEW_DEPLOY_PLAN.md"


def test_readiness_report_exists():
    assert REPORT.exists()


def test_readiness_report_includes_safety_boundary():
    text = REPORT.read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in text
    assert "`order_execution_allowed`는 항상 `false`입니다" in text
    assert "파일을 쓰지 않고" in text
    assert "systemd start/stop/restart/reload" in text


def test_readiness_report_does_not_include_private_key_path_or_oracle_ip():
    text = REPORT.read_text(encoding="utf-8")
    forbidden = [
        "168.110.101.18",
        "ssh-key-2026",
        "/Users/lahyunhwa/.ssh",
        "/home/ubuntu/trading_v2",
    ]
    for marker in forbidden:
        assert marker not in text
    assert "ORACLE_HOST=<oracle-host>" in text
    assert "ORACLE_SSH_KEY=<path-to-private-key>" in text
    assert "ORACLE_TRADING_DIR=<oracle-trading-dir>" in text


def test_readiness_report_does_not_include_secret_markers():
    text = REPORT.read_text(encoding="utf-8")
    forbidden = [
        "BEGIN PRIVATE KEY",
        "OPENSSH PRIVATE KEY",
        "API_SECRET=",
        "ACCESS_TOKEN=",
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
    ]
    for marker in forbidden:
        assert marker not in text
    assert "REDACTED" in text


def test_preview_deploy_plan_links_readonly_report():
    text = PREVIEW_PLAN.read_text(encoding="utf-8")

    assert "Phase 24H read-only readiness" in text
    assert "docs/US_TRADER_ORACLE_READONLY_READINESS_REPORT.md" in text
    assert "127.0.0.1" in text
    assert "start/stop/restart" in text


def test_readme_includes_phase_24h_summary():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24H Oracle Read-only Preview Deployment Readiness Check" in text
    assert "docs/US_TRADER_ORACLE_READONLY_READINESS_REPORT.md" in text
    assert "Oracle 서버 파일 쓰기" in text


def test_frontend_mentions_oracle_readonly_readiness_report():
    text = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "Oracle Read-only 점검" in text
    assert "docs/US_TRADER_ORACLE_READONLY_READINESS_REPORT.md" in text
    assert "systemd 서비스 재시작" in text


def test_phase_24h_order_execution_allowed_false():
    files = [REPORT, PREVIEW_PLAN, ROOT / "README.md"]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text


def test_phase_24h_does_not_add_broker_or_order_execution_code():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            REPORT,
            PREVIEW_PLAN,
            ROOT / "frontend" / "src" / "App.jsx",
        ]
    )
    forbidden_terms = [
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
    ]
    for term in forbidden_terms:
        assert term not in text
