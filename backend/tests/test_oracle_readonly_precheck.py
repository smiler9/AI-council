import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRECHECK_DIR = ROOT / "examples" / "oracle_readonly_precheck"
TEMPLATES = PRECHECK_DIR / "templates"


def test_build_readonly_precheck_plan_creates_plan(tmp_path):
    output = tmp_path / "precheck_plan.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PRECHECK_DIR / "build_readonly_precheck_plan.py"),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    plan = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert output.exists()
    assert plan["mode"] == "readonly_precheck"
    assert plan["manual_execution_required"] is True
    assert plan["remote_write_allowed"] is False
    assert plan["remote_write_executed"] is False
    assert plan["systemd_changes_allowed"] is False
    assert plan["order_execution_allowed"] is False
    assert payload["command_count"] >= 8


def test_verify_readonly_precheck_plan_success(tmp_path):
    plan = build_plan(tmp_path)
    payload = run_plan_verify(plan)

    assert payload["status"] == "ok"
    assert payload["secret_hits"] == []
    assert payload["active_forbidden_hits"] == []
    assert payload["remote_write_allowed"] is False
    assert payload["systemd_changes_allowed"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_plan_rejects_remote_write_allowed_true(tmp_path):
    plan = mutate_plan(tmp_path, {"remote_write_allowed": True})
    payload = run_plan_verify(plan)

    assert payload["status"] == "failed"
    assert "remote_write_allowed must be false" in payload["errors"]


def test_verify_plan_rejects_systemd_changes_allowed_true(tmp_path):
    plan = mutate_plan(tmp_path, {"systemd_changes_allowed": True})
    payload = run_plan_verify(plan)

    assert payload["status"] == "failed"
    assert "systemd_changes_allowed must be false" in payload["errors"]


def test_verify_plan_detects_forbidden_command(tmp_path):
    plan = build_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload["commands"].append({"category": "file_write", "command": "mkdir -p <oracle-trading-dir>/bad"})
    plan.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    verify_payload = run_plan_verify(plan)

    assert verify_payload["status"] == "failed"
    assert verify_payload["active_forbidden_hits"]


def test_record_readonly_precheck_result_creates_sample(tmp_path):
    output = tmp_path / "precheck_result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PRECHECK_DIR / "record_readonly_precheck_result.py"),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    recorded = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["result_status"] == "passed"
    assert recorded["remote_write_executed"] is False
    assert recorded["systemd_changed"] is False
    assert recorded["order_execution_allowed"] is False
    assert recorded["observations"]["penny_stock_bot_exists"] is True


def test_verify_readonly_precheck_result_success(tmp_path):
    result_path = record_result(tmp_path)
    payload = run_result_verify(result_path)

    assert payload["status"] == "ok"
    assert payload["next_step_allowed"] is True
    assert payload["missing_observations"] == []
    assert payload["secret_hits"] == []
    assert payload["remote_write_executed"] is False
    assert payload["systemd_changed"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_result_rejects_remote_write_executed_true(tmp_path):
    result_path = mutate_result(tmp_path, {"remote_write_executed": True})
    payload = run_result_verify(result_path)

    assert payload["status"] == "failed"
    assert "remote_write_executed must be false" in payload["errors"]


def test_verify_result_rejects_systemd_changed_true(tmp_path):
    result_path = mutate_result(tmp_path, {"systemd_changed": True})
    payload = run_result_verify(result_path)

    assert payload["status"] == "failed"
    assert "systemd_changed must be false" in payload["errors"]


def test_verify_result_warns_for_approved_field(tmp_path):
    result_path = mutate_result(tmp_path, {"approved": True})
    payload = run_result_verify(result_path)

    assert payload["status"] == "ok"
    assert payload["warnings"]
    assert payload["next_step_allowed"] is True


def test_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-trading-dir>" in text
    assert "order_execution_allowed" in text


def test_readonly_precheck_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_READONLY_PRECHECK_EXECUTION.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24N" in docs
    assert "read-only" in docs
    assert "systemd" in docs


def test_readme_includes_phase_24n_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24N Oracle Read-only Precheck Recorder" in readme
    assert "scripts/run_oracle_readonly_precheck_dryrun.sh" in readme
    assert "remote_write_allowed=false" in readme


def test_generated_readonly_precheck_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_readonly_precheck/" in gitignore
    assert "examples/oracle_readonly_precheck/output/" in gitignore
    assert "examples/oracle_readonly_precheck/.state/" in gitignore


def test_order_execution_allowed_always_false_in_readonly_precheck_files():
    files = [
        PRECHECK_DIR / "build_readonly_precheck_plan.py",
        PRECHECK_DIR / "verify_readonly_precheck_plan.py",
        PRECHECK_DIR / "record_readonly_precheck_result.py",
        PRECHECK_DIR / "verify_readonly_precheck_result.py",
        PRECHECK_DIR / "sample_readonly_precheck_plan.json",
        PRECHECK_DIR / "sample_readonly_precheck_result.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_readonly_precheck_code_does_not_add_broker_order_or_remote_write_operations():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PRECHECK_DIR / "build_readonly_precheck_plan.py",
            PRECHECK_DIR / "verify_readonly_precheck_plan.py",
            PRECHECK_DIR / "record_readonly_precheck_result.py",
            PRECHECK_DIR / "verify_readonly_precheck_result.py",
            ROOT / "scripts" / "build_oracle_readonly_precheck_plan.sh",
            ROOT / "scripts" / "verify_oracle_readonly_precheck_plan.sh",
            ROOT / "scripts" / "record_oracle_readonly_precheck_sample_result.sh",
            ROOT / "scripts" / "verify_oracle_readonly_precheck_result.sh",
            ROOT / "scripts" / "run_oracle_readonly_precheck_dryrun.sh",
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
        "ssh ",
        "scp ",
        "rsync ",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_readonly_precheck_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_readonly_precheck_plan.sh",
        ROOT / "scripts" / "verify_oracle_readonly_precheck_plan.sh",
        ROOT / "scripts" / "record_oracle_readonly_precheck_sample_result.sh",
        ROOT / "scripts" / "verify_oracle_readonly_precheck_result.sh",
        ROOT / "scripts" / "run_oracle_readonly_precheck_dryrun.sh",
        PRECHECK_DIR / "build_readonly_precheck_plan.py",
        PRECHECK_DIR / "verify_readonly_precheck_plan.py",
        PRECHECK_DIR / "record_readonly_precheck_result.py",
        PRECHECK_DIR / "verify_readonly_precheck_result.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def build_plan(tmp_path: Path) -> Path:
    output = tmp_path / "precheck_plan.json"
    subprocess.run(
        [sys.executable, str(PRECHECK_DIR / "build_readonly_precheck_plan.py"), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def mutate_plan(tmp_path: Path, updates: dict) -> Path:
    plan = build_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    payload.update(updates)
    plan.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return plan


def run_plan_verify(plan: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PRECHECK_DIR / "verify_readonly_precheck_plan.py"), "--plan", str(plan)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def record_result(tmp_path: Path) -> Path:
    output = tmp_path / "precheck_result.json"
    subprocess.run(
        [sys.executable, str(PRECHECK_DIR / "record_readonly_precheck_result.py"), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def mutate_result(tmp_path: Path, updates: dict) -> Path:
    result_path = record_result(tmp_path)
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload.update(updates)
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return result_path


def run_result_verify(result_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PRECHECK_DIR / "verify_readonly_precheck_result.py"), "--result", str(result_path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
