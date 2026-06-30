import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_DIR = ROOT / "examples" / "oracle_deployment"
PREVIEW_DIR = ROOT / "examples" / "oracle_preview_deploy"


def test_prepare_preview_deploy_plan_creates_preview_mode_plan(tmp_path):
    bundle = build_bundle(tmp_path)
    plan = tmp_path / "oracle_preview_deploy_plan.json"
    script = PREVIEW_DIR / "prepare_preview_deploy_plan.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--bundle",
            str(bundle),
            "--output",
            str(plan),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    plan_payload = json.loads(plan.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["mode"] == "preview"
    assert payload["manual_approval_required"] is True
    assert payload["order_execution_allowed"] is False
    assert plan_payload["mode"] == "preview"
    assert plan_payload["run_once_command_preview"].count("--mode preview") == 1


def test_preview_plan_contains_safety_flags(tmp_path):
    plan = prepare_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))

    assert payload["order_execution_allowed"] is False
    assert payload["manual_approval_required"] is True
    assert payload["auto_start"] is False
    assert payload["systemd_enabled"] is False
    assert payload["oracle_server_contacted"] is False
    assert payload["oracle_files_written"] is False
    assert payload["oracle_systemd_touched"] is False


def test_verify_preview_deploy_plan_success(tmp_path):
    plan = prepare_plan(tmp_path)
    script = PREVIEW_DIR / "verify_preview_deploy_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(plan), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["mode"] == "preview"
    assert payload["secret_hits"] == []
    assert payload["dangerous_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_review_live_order_modes(tmp_path):
    plan = prepare_plan(tmp_path)
    script = PREVIEW_DIR / "verify_preview_deploy_plan.py"
    for mode in ["review", "live", "order"]:
        payload = json.loads(plan.read_text(encoding="utf-8"))
        payload["mode"] = mode
        bad_plan = tmp_path / f"{mode}_plan.json"
        bad_plan.write_text(json.dumps(payload), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script), "--plan", str(bad_plan)],
            capture_output=True,
            text=True,
        )
        body = json.loads(result.stdout)

        assert result.returncode != 0
        assert body["status"] == "failed"
        assert "plan mode must be preview" in body["errors"]


def test_verify_detects_secret_private_key_marker(tmp_path):
    plan = prepare_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["oracle_target"]["host"] = "168.110.101.18"
    bad_plan = tmp_path / "secret_plan.json"
    bad_plan.write_text(json.dumps(payload), encoding="utf-8")
    script = PREVIEW_DIR / "verify_preview_deploy_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(bad_plan)],
        capture_output=True,
        text=True,
    )
    body = json.loads(result.stdout)

    assert result.returncode != 0
    assert body["status"] == "failed"
    assert body["secret_hits"]


def test_generate_preview_commands_creates_command_preview_files(tmp_path):
    plan = prepare_plan(tmp_path)
    output = tmp_path / "oracle_preview_commands"
    script = PREVIEW_DIR / "generate_preview_commands.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--plan",
            str(plan),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["mode"] == "preview"
    assert payload["command_file_count"] == 7
    assert (output / "00_readiness_check.sh").exists()
    assert (output / "04_run_sidecar_once_preview.preview.sh").exists()
    assert payload["order_execution_allowed"] is False


def test_generated_commands_do_not_directly_start_stop_restart_systemd(tmp_path):
    plan = prepare_plan(tmp_path)
    output = generate_commands(tmp_path, plan)
    text = "\n".join(path.read_text(encoding="utf-8") for path in output.glob("*.sh"))

    for forbidden in ["systemctl start", "systemctl stop", "systemctl restart", "systemctl enable", "systemctl disable"]:
        assert forbidden not in text
    assert "--mode preview" in text
    assert "--mode review" not in text


def test_generated_commands_do_not_touch_oracle_live_bot_services(tmp_path):
    plan = prepare_plan(tmp_path)
    output = generate_commands(tmp_path, plan)
    text = "\n".join(path.read_text(encoding="utf-8") for path in output.glob("*.sh"))

    for service in ["sniper-bot.service", "usstock-bot.service", "usstock-web.service"]:
        assert service not in text
    assert "penny_stock_bot.py" in text
    assert "Do not modify penny_stock_bot.py" in text


def test_preview_templates_do_not_hardcode_oracle_identity():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (PREVIEW_DIR / "templates").glob("*"))
    for marker in ["168.110.101.18", "ssh-key-2026", "/Users/lahyunhwa/.ssh"]:
        assert marker not in text
    assert "<oracle-host>" in (ROOT / "docs" / "US_TRADER_ORACLE_PREVIEW_DEPLOY_PLAN.md").read_text(encoding="utf-8")


def test_preview_deploy_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_PREVIEW_DEPLOY_PLAN.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Preview mode" in docs
    assert "systemd 운영봇 restart 없음" in docs


def test_readme_includes_phase_24g_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24G Oracle Preview-only Sidecar Deployment Preparation" in readme
    assert "scripts/run_oracle_preview_deploy_dryrun.sh" in readme
    assert "order_execution_allowed=false" in readme


def test_preview_deploy_order_execution_allowed_always_false():
    files = [
        PREVIEW_DIR / "prepare_preview_deploy_plan.py",
        PREVIEW_DIR / "verify_preview_deploy_plan.py",
        PREVIEW_DIR / "generate_preview_commands.py",
        PREVIEW_DIR / "sample_preview_plan.json",
        *PREVIEW_DIR.glob("templates/*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text or "ORDER_EXECUTION_ALLOWED" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_preview_deploy_code_does_not_add_broker_or_order_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PREVIEW_DIR / "prepare_preview_deploy_plan.py",
            PREVIEW_DIR / "generate_preview_commands.py",
            ROOT / "scripts" / "run_oracle_preview_deploy_dryrun.sh",
        ]
    )
    forbidden_terms = [
        "alpaca_trade_api",
        "ib_insync",
        "TradingClient",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_preview_deploy_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "prepare_oracle_preview_deploy_plan.sh",
        ROOT / "scripts" / "verify_oracle_preview_deploy_plan.sh",
        ROOT / "scripts" / "generate_oracle_preview_commands.sh",
        ROOT / "scripts" / "run_oracle_preview_deploy_dryrun.sh",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def build_bundle(tmp_path: Path) -> Path:
    output = tmp_path / "oracle_signal_export_bundle"
    script = DEPLOYMENT_DIR / "build_signal_export_bundle.py"
    subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def prepare_plan(tmp_path: Path) -> Path:
    bundle = build_bundle(tmp_path)
    plan = tmp_path / "oracle_preview_deploy_plan.json"
    script = PREVIEW_DIR / "prepare_preview_deploy_plan.py"
    subprocess.run(
        [sys.executable, str(script), "--bundle", str(bundle), "--output", str(plan)],
        check=True,
        capture_output=True,
        text=True,
    )
    return plan


def generate_commands(tmp_path: Path, plan: Path) -> Path:
    output = tmp_path / "oracle_preview_commands"
    script = PREVIEW_DIR / "generate_preview_commands.py"
    subprocess.run(
        [sys.executable, str(script), "--plan", str(plan), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output
