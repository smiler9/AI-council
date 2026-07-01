import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANUAL_DIR = ROOT / "examples" / "oracle_outbox_manual_creation"
PRECREATION_DIR = ROOT / "examples" / "oracle_outbox_precreation"
GO_DECISION = ROOT / "examples" / "oracle_precheck_intake" / "sample_go_decision.json"
NO_GO_DECISION = ROOT / "examples" / "oracle_precheck_intake" / "sample_no_go_decision.json"
TEMPLATES = MANUAL_DIR / "templates"


def test_build_manual_creation_packet_creates_packet_from_go_decision(tmp_path):
    plan = build_precreation_plan(tmp_path)
    output = tmp_path / "manual_packet"
    result = subprocess.run(
        [
            sys.executable,
            str(MANUAL_DIR / "build_manual_creation_packet.py"),
            "--precreation-plan",
            str(plan),
            "--go-no-go-decision",
            str(GO_DECISION),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert (output / "manual_creation_commands.example.sh").exists()
    assert (output / "post_creation_verify_commands.example.sh").exists()
    assert (output / "creation_result_record.example.json").exists()
    assert (output / "rollback_after_creation.example.sh").exists()
    assert payload["command_review_status"] == "passed"
    assert payload["creation_executed"] is False
    assert payload["remote_write_executed"] is False
    assert payload["systemd_changed"] is False
    assert payload["order_execution_allowed"] is False
    assert manifest["go_is_not_deployment_approval"] is True
    assert manifest["order_execution_allowed"] is False


def test_build_manual_creation_packet_fails_for_no_go_decision(tmp_path):
    plan = build_precreation_plan(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(MANUAL_DIR / "build_manual_creation_packet.py"),
            "--precreation-plan",
            str(plan),
            "--go-no-go-decision",
            str(NO_GO_DECISION),
            "--output",
            str(tmp_path / "manual_packet"),
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert "decision must be GO" in payload["error"]


def test_build_manual_creation_packet_fails_for_order_execution_allowed_true(tmp_path):
    plan = build_precreation_plan(tmp_path)
    decision = mutate_decision(tmp_path, {"order_execution_allowed": True})
    result = subprocess.run(
        [
            sys.executable,
            str(MANUAL_DIR / "build_manual_creation_packet.py"),
            "--precreation-plan",
            str(plan),
            "--go-no-go-decision",
            str(decision),
            "--output",
            str(tmp_path / "manual_packet"),
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert "order_execution_allowed must be false" in payload["error"]


def test_review_creation_commands_rejects_active_mkdir(tmp_path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "manual_creation_commands.example.sh").write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\nmkdir -p \"$AI_COUNCIL_OUTBOX_DIR\"\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(MANUAL_DIR / "review_creation_commands.py"), "--packet", str(packet)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["active_dangerous_commands_found"] is True


def test_review_creation_commands_classifies_commented_mkdir_as_manual_command(tmp_path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "manual_creation_commands.example.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo \"safe\"\n"
        "ORACLE_TRADING_DIR='<oracle-trading-dir>'\n"
        "test -d \"${ORACLE_TRADING_DIR}\"\n"
        "# mkdir -p \"${ORACLE_TRADING_DIR}/ai_council_outbox\"\n",
        encoding="utf-8",
    )
    payload = run_review(packet)

    assert payload["status"] == "passed"
    assert payload["active_dangerous_commands_found"] is False
    assert payload["commented_manual_write_commands"]
    assert payload["order_execution_allowed"] is False


def test_review_creation_commands_rejects_active_systemctl(tmp_path):
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "bad.example.sh").write_text("systemctl restart sniper-bot.service\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(MANUAL_DIR / "review_creation_commands.py"), "--packet", str(packet)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["active_dangerous_commands_found"] is True


def test_verify_manual_creation_packet_success(tmp_path):
    packet = build_packet(tmp_path)
    payload = run_verify(packet)

    assert payload["status"] == "ok"
    assert payload["hash_failures"] == []
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["broker_order_hits"] == []
    assert payload["command_review_status"] == "passed"
    assert payload["creation_executed"] is False
    assert payload["remote_write_executed"] is False
    assert payload["systemd_changed"] is False
    assert payload["oracle_live_bot_modified"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_creation_executed_true_default(tmp_path):
    packet = build_packet(tmp_path)
    record_path = packet / "creation_result_record.example.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["creation_executed"] = True
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    payload = run_verify(packet)

    assert payload["status"] == "failed"
    assert "creation_result_record creation_executed must default to false" in payload["errors"]


def test_verify_rejects_remote_write_executed_true(tmp_path):
    packet = build_packet(tmp_path)
    record_path = packet / "creation_result_record.example.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["remote_write_executed"] = True
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    payload = run_verify(packet)

    assert payload["status"] == "failed"
    assert "creation_result_record remote_write_executed must be false" in payload["errors"]


def test_verify_detects_secret_private_key_marker(tmp_path):
    packet = build_packet(tmp_path)
    (packet / "secret_marker.txt").write_text("-----BEGIN " + "OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
    payload = run_verify(packet)

    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_creation_result_record_defaults_incomplete():
    payload = json.loads((MANUAL_DIR / "templates" / "creation_result_record.example.json").read_text(encoding="utf-8"))
    sample = json.loads((MANUAL_DIR / "sample_creation_result_record.json").read_text(encoding="utf-8"))

    for record in [payload, sample]:
        assert record["creation_executed"] is False
        assert record["remote_write_executed"] is False
        assert record["systemd_changed"] is False
        assert record["live_bot_modified"] is False
        assert record["order_execution_allowed"] is False
        assert record["result_status"] == "incomplete"


def test_manual_creation_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_OUTBOX_MANUAL_CREATION_PACKET.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24P" in docs
    assert "GO가 의미하지 않는 것" in docs
    assert "systemd" in docs


def test_readme_includes_phase_24p_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24P Oracle Outbox Manual Creation Packet" in readme
    assert "scripts/run_oracle_outbox_manual_creation_dryrun.sh" in readme
    assert "creation_executed=false" in readme


def test_frontend_includes_phase_24p_guidance():
    source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "Oracle Outbox 수동 생성 패킷" in source
    assert "scripts/run_oracle_outbox_manual_creation_dryrun.sh" in source
    assert "GO는 실제 적용 승인이 아니라" in source
    assert "실제 주문" in source


def test_generated_manual_creation_packet_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_outbox_manual_creation/" in gitignore
    assert "examples/oracle_outbox_manual_creation/output/" in gitignore
    assert "examples/oracle_outbox_manual_creation/.state/" in gitignore


def test_order_execution_allowed_always_false_in_manual_creation_files():
    files = [
        MANUAL_DIR / "build_manual_creation_packet.py",
        MANUAL_DIR / "review_creation_commands.py",
        MANUAL_DIR / "verify_manual_creation_packet.py",
        MANUAL_DIR / "sample_manual_creation_packet.json",
        MANUAL_DIR / "sample_creation_result_record.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_manual_creation_code_does_not_add_broker_order_or_remote_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            MANUAL_DIR / "build_manual_creation_packet.py",
            MANUAL_DIR / "review_creation_commands.py",
            MANUAL_DIR / "verify_manual_creation_packet.py",
            ROOT / "scripts" / "build_oracle_outbox_manual_creation_packet.sh",
            ROOT / "scripts" / "review_oracle_outbox_creation_commands.sh",
            ROOT / "scripts" / "verify_oracle_outbox_manual_creation_packet.sh",
            ROOT / "scripts" / "run_oracle_outbox_manual_creation_dryrun.sh",
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


def test_manual_creation_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_outbox_manual_creation_packet.sh",
        ROOT / "scripts" / "review_oracle_outbox_creation_commands.sh",
        ROOT / "scripts" / "verify_oracle_outbox_manual_creation_packet.sh",
        ROOT / "scripts" / "run_oracle_outbox_manual_creation_dryrun.sh",
        MANUAL_DIR / "build_manual_creation_packet.py",
        MANUAL_DIR / "review_creation_commands.py",
        MANUAL_DIR / "verify_manual_creation_packet.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_manual_creation_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-trading-dir>" in text


def build_precreation_plan(tmp_path: Path) -> Path:
    output = tmp_path / "precreation_plan.json"
    subprocess.run(
        [sys.executable, str(PRECREATION_DIR / "build_outbox_precreation_plan.py"), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def mutate_decision(tmp_path: Path, updates: dict) -> Path:
    payload = json.loads(GO_DECISION.read_text(encoding="utf-8"))
    payload.update(updates)
    output = tmp_path / "decision.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output


def build_packet(tmp_path: Path) -> Path:
    plan = build_precreation_plan(tmp_path)
    output = tmp_path / "manual_packet"
    subprocess.run(
        [
            sys.executable,
            str(MANUAL_DIR / "build_manual_creation_packet.py"),
            "--precreation-plan",
            str(plan),
            "--go-no-go-decision",
            str(GO_DECISION),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def run_review(packet: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(MANUAL_DIR / "review_creation_commands.py"), "--packet", str(packet)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_verify(packet: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(MANUAL_DIR / "verify_manual_creation_packet.py"), "--packet", str(packet)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)
