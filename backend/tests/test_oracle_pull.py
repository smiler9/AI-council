import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PULL_DIR = ROOT / "examples" / "oracle_pull"
SAMPLE_SIGNALS = PULL_DIR / "sample_pulled_signals"


def test_verify_pull_plan_accepts_sample_plan():
    script = PULL_DIR / "verify_pull_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(PULL_DIR / "sample_pull_plan.json"), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["mode"] == "preview"
    assert payload["strategy"] == "mac_pull_oracle_outbox"
    assert payload["remote_delete"] is False
    assert payload["remote_move"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_pull_plan_rejects_remote_delete(tmp_path):
    plan = load_sample_plan(tmp_path)
    plan["remote_delete"] = True
    bad_plan = tmp_path / "remote_delete_plan.json"
    bad_plan.write_text(json.dumps(plan), encoding="utf-8")
    result = run_verify(bad_plan)
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert "remote_delete must be false" in payload["errors"]


def test_verify_pull_plan_rejects_remote_move(tmp_path):
    plan = load_sample_plan(tmp_path)
    plan["remote_move"] = True
    bad_plan = tmp_path / "remote_move_plan.json"
    bad_plan.write_text(json.dumps(plan), encoding="utf-8")
    result = run_verify(bad_plan)
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert "remote_move must be false" in payload["errors"]


def test_verify_pull_plan_detects_secret_private_key_marker(tmp_path):
    plan = load_sample_plan(tmp_path)
    plan["oracle"]["ssh_key"] = "-----BEGIN OPENSSH PRIVATE KEY-----"
    bad_plan = tmp_path / "secret_plan.json"
    bad_plan.write_text(json.dumps(plan), encoding="utf-8")
    result = run_verify(bad_plan)
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_oracle_outbox_pull_preview_dry_run():
    script = PULL_DIR / "oracle_outbox_pull_preview.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["mode"] == "dry_run"
    assert payload["network_changes_performed"] is False
    assert payload["tunnel_started"] is False
    assert payload["remote_delete_performed"] is False
    assert payload["remote_move_performed"] is False
    assert payload["order_execution_allowed"] is False


def test_process_pulled_signals_sample_preview_dry_run():
    script = PULL_DIR / "process_pulled_signals.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--inbox",
            str(SAMPLE_SIGNALS),
            "--mode",
            "preview",
            "--dry-run",
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["mode"] == "preview"
    assert payload["dry_run"] is True
    assert payload["files_seen"] == 3
    assert payload["remote_delete_performed"] is False
    assert payload["remote_move_performed"] is False
    assert payload["order_execution_allowed"] is False


def test_process_pulled_signals_suppresses_duplicate_signal_id(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = json.loads((SAMPLE_SIGNALS / "pulled_us_trader_signal_001.json").read_text(encoding="utf-8"))
    first = inbox / "first.json"
    second = inbox / "second.json"
    first.write_text(json.dumps(source), encoding="utf-8")
    second.write_text(json.dumps(source | {"symbol": "TESTA"}), encoding="utf-8")

    script = PULL_DIR / "process_pulled_signals.py"
    result = subprocess.run(
        [sys.executable, str(script), "--inbox", str(inbox), "--dry-run", "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "passed"
    assert payload["files_seen"] == 2
    assert payload["processed_count"] == 1
    assert payload["duplicate_count"] == 1
    assert payload["order_execution_allowed"] is False


def test_process_pulled_signals_reports_order_like_warning():
    script = PULL_DIR / "process_pulled_signals.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--inbox",
            str(SAMPLE_SIGNALS),
            "--mode",
            "preview",
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    warning_text = " ".join(
        warning
        for item in payload["results"]
        for warning in item.get("adapter_warnings", [])
    )

    assert "order-like fields ignored for safety" in warning_text
    assert "buy/sell side was treated as review context only" in warning_text


def test_oracle_pull_sample_payloads_are_valid_json():
    expected = {
        "pulled_us_trader_signal_001.json",
        "pulled_us_trader_signal_order_like.json",
        "pulled_us_trader_signal_high_risk.json",
    }
    found = {path.name for path in SAMPLE_SIGNALS.glob("*.json")}
    assert found == expected

    for path in SAMPLE_SIGNALS.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["source"] == "us_trader_oracle"
        assert payload["symbol"].startswith("TEST")
        assert payload["order_execution_allowed"] is False


def test_oracle_pull_templates_do_not_hardcode_oracle_identity():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (PULL_DIR / "templates").glob("*"))

    for marker in ["ORACLE_REAL_HOST_VALUE", "REAL_PRIVATE_KEY_PATH", "REAL_SSH_KEY_FILENAME"]:
        assert marker not in text
    assert "<oracle-host>" in text
    assert "<path-to-private-key>" in text


def test_oracle_pull_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_MAC_PULL_PLAN.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "원격 파일 삭제/이동 금지" in docs
    assert "mac_pull_oracle_outbox" in docs


def test_readme_includes_phase_24j_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24J Mac Pull Oracle Outbox Preview Pipeline" in readme
    assert "scripts/run_oracle_pull_smoke.sh" in readme
    assert "원격 삭제/이동 금지" in readme


def test_oracle_pull_order_execution_allowed_always_false():
    files = [
        PULL_DIR / "oracle_outbox_pull_preview.py",
        PULL_DIR / "process_pulled_signals.py",
        PULL_DIR / "verify_pull_plan.py",
        PULL_DIR / "sample_pull_plan.json",
        *SAMPLE_SIGNALS.glob("*.json"),
        *PULL_DIR.glob("templates/*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_oracle_pull_code_does_not_add_broker_order_or_remote_write_actions():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PULL_DIR / "oracle_outbox_pull_preview.py",
            PULL_DIR / "process_pulled_signals.py",
            PULL_DIR / "verify_pull_plan.py",
            ROOT / "scripts" / "run_oracle_pull_smoke.sh",
        ]
    )
    forbidden_terms = [
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
        "market_order(",
        "limit_order(",
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "ngrok http",
        "cloudflared tunnel run",
        "tailscale up",
        "ssh -N -R",
        "--remove-source-files",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_oracle_pull_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "examples" / "integration" / "run_oracle_pull_smoke.py",
        ROOT / "scripts" / "run_oracle_pull_smoke.sh",
        PULL_DIR / "oracle_outbox_pull_preview.py",
        PULL_DIR / "process_pulled_signals.py",
        PULL_DIR / "verify_pull_plan.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_generated_pull_outputs_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_pull/" in gitignore
    assert "oracle_pulled_signals/" in gitignore
    assert "examples/oracle_pull/cache/" in gitignore
    assert "examples/oracle_pull/output/" in gitignore
    assert "examples/oracle_pull/.state/" in gitignore


def test_oracle_pull_smoke_script_file_exists():
    assert (ROOT / "examples" / "integration" / "run_oracle_pull_smoke.py").exists()
    assert (ROOT / "scripts" / "run_oracle_pull_smoke.sh").exists()


def test_sample_processing_does_not_modify_sample_files(tmp_path):
    copied = tmp_path / "sample_copy"
    shutil.copytree(SAMPLE_SIGNALS, copied)
    before = {path.name: path.read_text(encoding="utf-8") for path in copied.glob("*.json")}
    script = PULL_DIR / "process_pulled_signals.py"
    subprocess.run(
        [sys.executable, str(script), "--inbox", str(copied), "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
    )
    after = {path.name: path.read_text(encoding="utf-8") for path in copied.glob("*.json")}
    assert before == after


def load_sample_plan(tmp_path: Path) -> dict:
    return json.loads((PULL_DIR / "sample_pull_plan.json").read_text(encoding="utf-8"))


def run_verify(plan: Path) -> subprocess.CompletedProcess[str]:
    script = PULL_DIR / "verify_pull_plan.py"
    return subprocess.run(
        [sys.executable, str(script), "--plan", str(plan)],
        capture_output=True,
        text=True,
    )
