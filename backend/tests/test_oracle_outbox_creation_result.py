import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT_DIR = ROOT / "examples" / "oracle_outbox_creation_result"
TEMPLATES = RESULT_DIR / "templates"


def test_build_creation_result_template_creates_tmp_template(tmp_path):
    output = tmp_path / "creation_result_template.json"
    result = subprocess.run(
        [
            sys.executable,
            str(RESULT_DIR / "build_creation_result_template.py"),
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
    assert template["observations"]["outbox_dir_exists"] is False
    assert template["observations"]["post_creation_verify_readonly_only"] is True
    assert template["safety"]["systemd_changed"] is False
    assert template["safety"]["live_bot_modified"] is False
    assert template["safety"]["order_execution_allowed"] is False
    assert payload["order_execution_allowed"] is False


def test_record_creation_result_creates_sample_result(tmp_path):
    output = tmp_path / "creation_result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(RESULT_DIR / "record_creation_result.py"),
            "--input",
            str(RESULT_DIR / "sample_creation_result_passed.json"),
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
    assert output.exists()
    assert recorded["result_status"] == "passed"
    assert recorded["observations"]["outbox_dir_exists"] is True
    assert recorded["safety"]["systemd_changed"] is False
    assert recorded["safety"]["live_bot_modified"] is False
    assert recorded["safety"]["penny_stock_bot_modified"] is False
    assert recorded["safety"]["broker_api_called"] is False
    assert recorded["safety"]["order_execution_allowed"] is False


def test_verify_creation_result_passes_sample():
    payload = run_verify(RESULT_DIR / "sample_creation_result_passed.json")

    assert payload["status"] == "ok"
    assert payload["validation_status"] == "passed"
    assert payload["errors"] == []
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["systemd_changed"] is False
    assert payload["live_bot_modified"] is False
    assert payload["penny_stock_bot_modified"] is False
    assert payload["broker_api_called"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_missing_outbox_dir_exists(tmp_path):
    result_path = mutate_result(tmp_path, observation_updates={"outbox_dir_exists": False})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert any("outbox_dir_exists" in error for error in payload["errors"])


def test_verify_rejects_systemd_changed_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"systemd_changed": True})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert any("systemd_changed" in error for error in payload["errors"])


def test_verify_rejects_live_bot_modified_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"live_bot_modified": True})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert any("live_bot_modified" in error for error in payload["errors"])


def test_verify_rejects_penny_stock_bot_modified_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"penny_stock_bot_modified": True})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert any("penny_stock_bot_modified" in error for error in payload["errors"])


def test_verify_rejects_broker_api_called_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"broker_api_called": True})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert any("broker_api_called" in error for error in payload["errors"])


def test_verify_rejects_order_execution_allowed_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"order_execution_allowed": True})
    payload = run_verify(result_path)

    assert payload["status"] == "failed"
    assert payload["order_true_hits"]


def test_decide_post_creation_go_no_go_creates_go_for_valid_result(tmp_path):
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(RESULT_DIR / "decide_post_creation_go_no_go.py"),
            "--result",
            str(RESULT_DIR / "sample_creation_result_passed.json"),
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
    assert decision["next_phase"] == "Phase 24R Oracle preview signal file write rehearsal"
    assert decision["decision_scope"] == "Allows only preview signal file write rehearsal, not live bot patching or order execution."
    assert decision["order_execution_allowed"] is False
    assert "not live bot patch approval" in " ".join(decision["required_manual_acknowledgements"])


def test_decide_post_creation_go_no_go_creates_no_go_for_failed_result(tmp_path):
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(RESULT_DIR / "decide_post_creation_go_no_go.py"),
            "--result",
            str(RESULT_DIR / "sample_creation_result_failed.json"),
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
    assert decision["order_execution_allowed"] is False


def test_go_record_defaults_to_approved_false():
    payload = json.loads((TEMPLATES / "post_creation_go_record.example.json").read_text(encoding="utf-8"))

    assert payload["decision"] == "GO"
    assert payload["approved"] is False
    assert payload["manual_approval_required"] is True
    assert payload["order_execution_allowed"] is False
    assert payload["decision_scope"] == "Allows only preview signal file write rehearsal, not live bot patching or order execution."


def test_creation_result_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))
    text += "\n" + (RESULT_DIR / "sample_creation_result_passed.json").read_text(encoding="utf-8")

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-host>" in text
    assert "<oracle-trading-dir>" in text
    assert "order_execution_allowed" in text


def test_creation_result_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_OUTBOX_CREATION_RESULT_VERIFICATION.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24Q" in docs
    assert "GO가 의미하는 것과 의미하지 않는 것" in docs
    assert "운영봇 patch 승인" in docs


def test_readme_includes_phase_24q_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24Q Oracle Outbox Creation Result Verification" in readme
    assert "scripts/run_oracle_outbox_creation_result_dryrun.sh" in readme
    assert "GO는 운영봇 patch 승인이 아닙니다" in readme


def test_frontend_includes_phase_24q_guidance():
    source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "Oracle Outbox 생성 결과 검증" in source
    assert "scripts/run_oracle_outbox_creation_result_dryrun.sh" in source
    assert "GO는 운영봇 patch 승인이 아니라" in source
    assert "실제 주문" in source


def test_generated_creation_result_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_outbox_creation_result/" in gitignore
    assert "examples/oracle_outbox_creation_result/output/" in gitignore
    assert "examples/oracle_outbox_creation_result/.state/" in gitignore


def test_order_execution_allowed_always_false_in_creation_result_files():
    files = [
        RESULT_DIR / "build_creation_result_template.py",
        RESULT_DIR / "record_creation_result.py",
        RESULT_DIR / "verify_creation_result.py",
        RESULT_DIR / "decide_post_creation_go_no_go.py",
        RESULT_DIR / "sample_creation_result_passed.json",
        RESULT_DIR / "sample_creation_result_failed.json",
        RESULT_DIR / "sample_post_creation_go_decision.json",
        RESULT_DIR / "sample_post_creation_no_go_decision.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_creation_result_code_does_not_add_broker_order_or_remote_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            RESULT_DIR / "build_creation_result_template.py",
            RESULT_DIR / "record_creation_result.py",
            RESULT_DIR / "verify_creation_result.py",
            RESULT_DIR / "decide_post_creation_go_no_go.py",
            ROOT / "scripts" / "build_oracle_outbox_creation_result_template.sh",
            ROOT / "scripts" / "record_oracle_outbox_creation_sample_result.sh",
            ROOT / "scripts" / "verify_oracle_outbox_creation_result.sh",
            ROOT / "scripts" / "decide_oracle_post_creation_go_no_go.sh",
            ROOT / "scripts" / "run_oracle_outbox_creation_result_dryrun.sh",
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


def test_creation_result_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_outbox_creation_result_template.sh",
        ROOT / "scripts" / "record_oracle_outbox_creation_sample_result.sh",
        ROOT / "scripts" / "verify_oracle_outbox_creation_result.sh",
        ROOT / "scripts" / "decide_oracle_post_creation_go_no_go.sh",
        ROOT / "scripts" / "run_oracle_outbox_creation_result_dryrun.sh",
        RESULT_DIR / "build_creation_result_template.py",
        RESULT_DIR / "record_creation_result.py",
        RESULT_DIR / "verify_creation_result.py",
        RESULT_DIR / "decide_post_creation_go_no_go.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def run_verify(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(RESULT_DIR / "verify_creation_result.py"), "--result", str(path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def mutate_result(tmp_path: Path, *, observation_updates: dict | None = None, safety_updates: dict | None = None) -> Path:
    payload = json.loads((RESULT_DIR / "sample_creation_result_passed.json").read_text(encoding="utf-8"))
    if observation_updates:
        payload["observations"].update(observation_updates)
    if safety_updates:
        payload["safety"].update(safety_updates)
    output = tmp_path / "creation_result.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output
