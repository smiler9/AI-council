import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INTAKE_DIR = ROOT / "examples" / "oracle_precheck_intake"
TEMPLATES = INTAKE_DIR / "templates"


def test_build_precheck_intake_template_creates_template(tmp_path):
    output = tmp_path / "precheck_intake_template.json"
    result = subprocess.run(
        [
            sys.executable,
            str(INTAKE_DIR / "build_precheck_intake_template.py"),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    template = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert output.exists()
    assert template["result_status"] == "incomplete"
    assert template["oracle_target"]["host"] == "<oracle-host>"
    assert template["safety"]["remote_write_executed"] is False
    assert template["safety"]["systemd_changed"] is False
    assert template["safety"]["live_bot_modified"] is False
    assert template["safety"]["secrets_exposed"] is False
    assert template["safety"]["order_execution_allowed"] is False
    assert payload["order_execution_allowed"] is False


def test_validate_precheck_intake_passes_sample():
    payload = run_validate(INTAKE_DIR / "sample_precheck_intake.json")

    assert payload["status"] == "ok"
    assert payload["validation_status"] == "passed"
    assert payload["errors"] == []
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["remote_write_executed"] is False
    assert payload["systemd_changed"] is False
    assert payload["live_bot_modified"] is False
    assert payload["secrets_exposed"] is False
    assert payload["order_execution_allowed"] is False


def test_validate_rejects_remote_write_executed_true(tmp_path):
    intake = mutate_sample(tmp_path, safety_updates={"remote_write_executed": True})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert any("remote_write_executed" in error for error in payload["errors"])


def test_validate_rejects_systemd_changed_true(tmp_path):
    intake = mutate_sample(tmp_path, safety_updates={"systemd_changed": True})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert any("systemd_changed" in error for error in payload["errors"])


def test_validate_rejects_live_bot_modified_true(tmp_path):
    intake = mutate_sample(tmp_path, safety_updates={"live_bot_modified": True})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert any("live_bot_modified" in error for error in payload["errors"])


def test_validate_rejects_secrets_exposed_true(tmp_path):
    intake = mutate_sample(tmp_path, safety_updates={"secrets_exposed": True})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert any("secrets_exposed" in error for error in payload["errors"])


def test_validate_rejects_order_execution_allowed_true(tmp_path):
    intake = mutate_sample(tmp_path, safety_updates={"order_execution_allowed": True})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert payload["order_true_hits"]


def test_validate_rejects_missing_required_observation(tmp_path):
    intake = mutate_sample(tmp_path, observation_updates={"python3_available": False})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert any("python3_available" in error for error in payload["errors"])


def test_validate_detects_secret_or_private_key_marker(tmp_path):
    intake = mutate_sample(tmp_path, updates={"notes": ["-----BEGIN " + "OPENSSH PRIVATE KEY-----"]})
    payload = run_validate(intake)

    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_decide_precreation_go_no_go_creates_go_for_valid_intake(tmp_path):
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(INTAKE_DIR / "decide_precreation_go_no_go.py"),
            "--intake",
            str(INTAKE_DIR / "sample_precheck_intake.json"),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    decision = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["decision"] == "GO"
    assert payload["next_phase_allowed"] is True
    assert decision["decision"] == "GO"
    assert decision["decision_scope"] == "Allows only the next manual review stage, not deployment or order execution."
    assert decision["order_execution_allowed"] is False
    assert "broker API" in " ".join(decision["required_manual_acknowledgements"])


def test_decide_precreation_go_no_go_creates_no_go_for_failed_intake(tmp_path):
    intake = mutate_sample(tmp_path, updates={"result_status": "failed"})
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(INTAKE_DIR / "decide_precreation_go_no_go.py"),
            "--intake",
            str(intake),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    decision = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert payload["decision"] == "NO_GO"
    assert payload["next_phase_allowed"] is False
    assert decision["decision"] == "NO_GO"
    assert decision["next_phase_allowed"] is False
    assert decision["order_execution_allowed"] is False


def test_go_record_defaults_to_approved_false():
    payload = json.loads((TEMPLATES / "precreation_go_record.example.json").read_text(encoding="utf-8"))

    assert payload["decision"] == "GO"
    assert payload["approved"] is False
    assert payload["manual_approval_required"] is True
    assert payload["order_execution_allowed"] is False
    assert payload["decision_scope"] == "Allows only the next manual review stage, not deployment or order execution."


def test_precheck_intake_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))
    text += "\n" + (INTAKE_DIR / "sample_precheck_intake.json").read_text(encoding="utf-8")

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-host>" in text
    assert "<oracle-trading-dir>" in text
    assert "order_execution_allowed" in text


def test_precheck_intake_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_PRECHECK_INTAKE_GO_NO_GO.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24O" in docs
    assert "GO는 실제 적용 승인이 아니라" in docs
    assert "No-Go" in docs or "NO-GO" in docs


def test_readme_includes_phase_24o_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24O Oracle Precheck Intake Go/No-Go" in readme
    assert "scripts/run_oracle_precheck_intake_dryrun.sh" in readme
    assert "GO는 실제 적용 승인이 아니라" in readme


def test_frontend_includes_phase_24o_guidance():
    source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "Oracle Precheck 결과 반영" in source
    assert "scripts/run_oracle_precheck_intake_dryrun.sh" in source
    assert "GO는 실제 적용 승인이 아니라" in source
    assert "실제 주문" in source


def test_generated_precheck_intake_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_precheck_intake/" in gitignore
    assert "examples/oracle_precheck_intake/output/" in gitignore
    assert "examples/oracle_precheck_intake/.state/" in gitignore


def test_order_execution_allowed_always_false_in_precheck_intake_files():
    files = [
        INTAKE_DIR / "build_precheck_intake_template.py",
        INTAKE_DIR / "validate_precheck_intake.py",
        INTAKE_DIR / "decide_precreation_go_no_go.py",
        INTAKE_DIR / "sample_precheck_intake.json",
        INTAKE_DIR / "sample_go_decision.json",
        INTAKE_DIR / "sample_no_go_decision.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_precheck_intake_code_does_not_add_broker_order_or_remote_operations():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            INTAKE_DIR / "build_precheck_intake_template.py",
            INTAKE_DIR / "validate_precheck_intake.py",
            INTAKE_DIR / "decide_precreation_go_no_go.py",
            ROOT / "scripts" / "build_oracle_precheck_intake_template.sh",
            ROOT / "scripts" / "validate_oracle_precheck_intake.sh",
            ROOT / "scripts" / "decide_oracle_precreation_go_no_go.sh",
            ROOT / "scripts" / "run_oracle_precheck_intake_dryrun.sh",
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


def test_precheck_intake_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_precheck_intake_template.sh",
        ROOT / "scripts" / "validate_oracle_precheck_intake.sh",
        ROOT / "scripts" / "decide_oracle_precreation_go_no_go.sh",
        ROOT / "scripts" / "run_oracle_precheck_intake_dryrun.sh",
        INTAKE_DIR / "build_precheck_intake_template.py",
        INTAKE_DIR / "validate_precheck_intake.py",
        INTAKE_DIR / "decide_precreation_go_no_go.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def run_validate(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(INTAKE_DIR / "validate_precheck_intake.py"), "--intake", str(path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def mutate_sample(
    tmp_path: Path,
    *,
    updates: dict | None = None,
    observation_updates: dict | None = None,
    safety_updates: dict | None = None,
) -> Path:
    payload = json.loads((INTAKE_DIR / "sample_precheck_intake.json").read_text(encoding="utf-8"))
    if updates:
        payload.update(updates)
    if observation_updates:
        payload["observations"].update(observation_updates)
    if safety_updates:
        payload["safety"].update(safety_updates)
    output = tmp_path / "precheck_intake.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output
