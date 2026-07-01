import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONNECTIVITY_DIR = ROOT / "examples" / "oracle_connectivity"


def test_compare_connectivity_options_recommends_safe_option():
    script = CONNECTIVITY_DIR / "compare_connectivity_options.py"
    result = subprocess.run(
        [sys.executable, str(script), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["recommended_option"] == "oracle_outbox_only_preview"
    assert payload["priority"]["1순위"] == "oracle_outbox_only_preview"
    assert payload["priority"]["2순위"] == "mac_pull_oracle_outbox"
    assert payload["network_changes_performed"] is False
    assert payload["tunnel_started"] is False
    assert payload["ssh_executed"] is False
    assert payload["order_execution_allowed"] is False


def test_generate_connectivity_plan_creates_preview_plan(tmp_path):
    plan = tmp_path / "oracle_connectivity_plan.json"
    script = CONNECTIVITY_DIR / "generate_connectivity_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(plan), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    plan_payload = json.loads(plan.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["option"] == "oracle_outbox_only_preview"
    assert payload["mode"] == "preview"
    assert payload["manual_approval_required"] is True
    assert payload["order_execution_allowed"] is False
    assert plan_payload["mode"] == "preview"
    assert plan_payload["order_execution_allowed"] is False
    assert plan_payload["network_changes_performed"] is False


def test_connectivity_plan_includes_manual_approval_and_safety_flags(tmp_path):
    plan = generate_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))

    assert payload["manual_approval_required"] is True
    assert payload["tunnel_started"] is False
    assert payload["ssh_executed"] is False
    assert payload["ai_council_public_exposure_created"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_connectivity_plan_success(tmp_path):
    plan = generate_plan(tmp_path)
    script = CONNECTIVITY_DIR / "verify_connectivity_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(plan), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["option"] == "oracle_outbox_only_preview"
    assert payload["mode"] == "preview"
    assert payload["secret_hits"] == []
    assert payload["dangerous_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_live_order_mode(tmp_path):
    plan = generate_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["mode"] = "live_order"
    bad_plan = tmp_path / "bad_live_order_plan.json"
    bad_plan.write_text(json.dumps(payload), encoding="utf-8")
    script = CONNECTIVITY_DIR / "verify_connectivity_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(bad_plan)],
        capture_output=True,
        text=True,
    )
    body = json.loads(result.stdout)

    assert result.returncode != 0
    assert body["status"] == "failed"
    assert "plan mode must be preview" in body["errors"]


def test_verify_detects_secret_private_key_or_tunnel_token_marker(tmp_path):
    plan = generate_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["tunnel_token_hint"] = "eyJthisLooksLikeATunnelTokenButIsOnlyATestMarker12345"
    bad_plan = tmp_path / "secret_plan.json"
    bad_plan.write_text(json.dumps(payload), encoding="utf-8")
    script = CONNECTIVITY_DIR / "verify_connectivity_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(bad_plan)],
        capture_output=True,
        text=True,
    )
    body = json.loads(result.stdout)

    assert result.returncode != 0
    assert body["status"] == "failed"
    assert body["secret_hits"]


def test_connectivity_templates_do_not_hardcode_oracle_identity():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (CONNECTIVITY_DIR / "templates").glob("*"))

    for marker in ["ORACLE_REAL_HOST_VALUE", "REAL_PRIVATE_KEY_PATH", "REAL_SSH_KEY_FILENAME"]:
        assert marker not in text
    assert "<oracle-host>" in text
    assert "<path-to-private-key>" in text


def test_connectivity_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_NETWORK_CONNECTIVITY_STRATEGY.md").read_text(
        encoding="utf-8"
    )

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Oracle 서버에서 `127.0.0.1`은 Oracle 자기 자신입니다" in docs
    assert "oracle_outbox_only_preview" in docs
    assert "mac_pull_oracle_outbox" in docs


def test_readme_includes_phase_24i_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24I Oracle Network Connectivity Strategy" in readme
    assert "scripts/run_oracle_connectivity_strategy_dryrun.sh" in readme
    assert "oracle_outbox_only_preview" in readme
    assert "order_execution_allowed=false" in readme


def test_generated_connectivity_plan_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/" in gitignore
    assert "examples/oracle_connectivity/output/" in gitignore
    assert "examples/oracle_connectivity/.state/" in gitignore


def test_oracle_connectivity_order_execution_allowed_always_false():
    files = [
        CONNECTIVITY_DIR / "compare_connectivity_options.py",
        CONNECTIVITY_DIR / "generate_connectivity_plan.py",
        CONNECTIVITY_DIR / "verify_connectivity_plan.py",
        CONNECTIVITY_DIR / "sample_connectivity_plan.json",
        *CONNECTIVITY_DIR.glob("templates/*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_oracle_connectivity_code_does_not_execute_network_or_broker_actions():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            CONNECTIVITY_DIR / "compare_connectivity_options.py",
            CONNECTIVITY_DIR / "generate_connectivity_plan.py",
            ROOT / "scripts" / "run_oracle_connectivity_strategy_dryrun.sh",
        ]
    )
    forbidden_terms = [
        "subprocess.run",
        "urllib",
        "requests.",
        "ngrok http",
        "cloudflared tunnel run",
        "tailscale up",
        "ssh -N -R",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_oracle_connectivity_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "compare_oracle_connectivity_options.sh",
        ROOT / "scripts" / "generate_oracle_connectivity_plan.sh",
        ROOT / "scripts" / "verify_oracle_connectivity_plan.sh",
        ROOT / "scripts" / "run_oracle_connectivity_strategy_dryrun.sh",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def generate_plan(tmp_path: Path) -> Path:
    plan = tmp_path / "oracle_connectivity_plan.json"
    script = CONNECTIVITY_DIR / "generate_connectivity_plan.py"
    subprocess.run(
        [sys.executable, str(script), "--output", str(plan)],
        check=True,
        capture_output=True,
        text=True,
    )
    return plan
