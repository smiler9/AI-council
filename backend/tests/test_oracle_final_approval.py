import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FINAL_DIR = ROOT / "examples" / "oracle_final_approval"
PRECREATION_DIR = ROOT / "examples" / "oracle_outbox_precreation"
TEMPLATES = FINAL_DIR / "templates"


def test_build_final_approval_packet_creates_packet_in_tmp(tmp_path):
    precreation_plan, commands_dir = make_precreation_inputs(tmp_path)
    output = tmp_path / "final_packet"
    script = FINAL_DIR / "build_final_approval_packet.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--precreation-plan",
            str(precreation_plan),
            "--manual-commands-dir",
            str(commands_dir),
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
    assert output.exists()
    assert (output / "final_approval_checklist.md").exists()
    assert (output / "approval_record.example.json").exists()
    assert (output / "manual_command_review.json").exists()
    assert payload["approved"] is False
    assert payload["remote_write_executed"] is False
    assert payload["order_execution_allowed"] is False
    assert manifest["manual_approval_required"] is True
    assert manifest["approved"] is False
    assert manifest["order_execution_allowed"] is False


def test_review_manual_commands_passes_read_only_commands(tmp_path):
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "read_only.manual.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo \"read only\"\n"
        "test -d <oracle-trading-dir>\n"
        "ls -ld <oracle-trading-dir>\n"
        "stat <oracle-trading-dir>\n"
        "df -h <oracle-trading-dir>\n"
        "python3 --version\n",
        encoding="utf-8",
    )
    payload = run_review(commands)

    assert payload["status"] == "passed"
    assert payload["active_dangerous_commands_found"] is False
    assert payload["read_only_commands"]
    assert payload["order_execution_allowed"] is False


def test_review_manual_commands_rejects_active_mkdir_chmod_rm_systemctl(tmp_path):
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "bad.manual.sh").write_text(
        "mkdir -p <oracle-trading-dir>/ai_council_outbox\n"
        "chmod 750 <oracle-trading-dir>/ai_council_outbox\n"
        "rm -r <oracle-trading-dir>/ai_council_outbox\n"
        "systemctl restart <service-name>\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(FINAL_DIR / "review_manual_commands.py"), "--commands-dir", str(commands)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["active_dangerous_commands_found"] is True
    assert len(payload["active_dangerous_commands"]) == 4


def test_verify_final_approval_packet_success(tmp_path):
    packet = build_packet(tmp_path)
    payload = run_verify(packet)

    assert payload["status"] == "ok"
    assert payload["hash_failures"] == []
    assert payload["secret_hits"] == []
    assert payload["approved_true_hits"] == []
    assert payload["active_dangerous_hits"] == []
    assert payload["manual_approval_required"] is True
    assert payload["approved"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_approved_true_default(tmp_path):
    packet = build_packet(tmp_path)
    approval_record = packet / "approval_record.example.json"
    payload = json.loads(approval_record.read_text(encoding="utf-8"))
    payload["approved"] = True
    approval_record.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(FINAL_DIR / "verify_final_approval_packet.py"), "--packet", str(packet)],
        capture_output=True,
        text=True,
    )
    verify_payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert verify_payload["status"] == "failed"
    assert verify_payload["approved_true_hits"]
    assert "approval_record approved must default to false" in verify_payload["errors"]


def test_verify_rejects_secret_private_key_marker(tmp_path):
    packet = build_packet(tmp_path)
    marker = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
    (packet / "secret_marker.txt").write_text(marker, encoding="utf-8")
    payload = run_verify(packet)

    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_verify_rejects_actual_oracle_ip_or_key_path_marker(tmp_path):
    packet = build_packet(tmp_path)
    (packet / "host_marker.txt").write_text(
        "ORACLE_HOST=203.0.113.10\nORACLE_SSH_KEY=/Users/example/.ssh/example.key\n",
        encoding="utf-8",
    )
    payload = run_verify(packet)

    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_final_approval_templates_have_no_active_systemctl_start_stop_restart():
    for path in TEMPLATES.glob("*.sh"):
        text = path.read_text(encoding="utf-8")
        for line in active_lines(text):
            assert "systemctl start" not in line
            assert "systemctl stop" not in line
            assert "systemctl restart" not in line
            assert "systemctl reload" not in line


def test_approval_record_example_defaults_to_approved_false():
    payload = json.loads((TEMPLATES / "approval_record.example.json").read_text(encoding="utf-8"))
    sample = json.loads((FINAL_DIR / "sample_final_approval_record.json").read_text(encoding="utf-8"))

    assert payload["approved"] is False
    assert payload["order_execution_allowed"] is False
    assert sample["approved"] is False
    assert sample["order_execution_allowed"] is False


def test_final_approval_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_FINAL_APPROVAL_GATE.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24M" in docs
    assert "approved=false" in docs
    assert "systemd" in docs


def test_readme_includes_phase_24m_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24M Oracle Final Approval Gate" in readme
    assert "scripts/run_oracle_final_approval_dryrun.sh" in readme
    assert "approved=false" in readme


def test_generated_final_approval_packet_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_final_approval/" in gitignore
    assert "examples/oracle_final_approval/output/" in gitignore
    assert "examples/oracle_final_approval/.state/" in gitignore


def test_final_approval_order_execution_allowed_always_false():
    files = [
        FINAL_DIR / "build_final_approval_packet.py",
        FINAL_DIR / "review_manual_commands.py",
        FINAL_DIR / "verify_final_approval_packet.py",
        FINAL_DIR / "sample_final_approval_record.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_final_approval_code_does_not_add_broker_order_or_remote_operations():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            FINAL_DIR / "build_final_approval_packet.py",
            FINAL_DIR / "review_manual_commands.py",
            FINAL_DIR / "verify_final_approval_packet.py",
            ROOT / "scripts" / "build_oracle_final_approval_packet.sh",
            ROOT / "scripts" / "review_oracle_manual_commands.sh",
            ROOT / "scripts" / "verify_oracle_final_approval_packet.sh",
            ROOT / "scripts" / "run_oracle_final_approval_dryrun.sh",
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


def test_final_approval_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_final_approval_packet.sh",
        ROOT / "scripts" / "review_oracle_manual_commands.sh",
        ROOT / "scripts" / "verify_oracle_final_approval_packet.sh",
        ROOT / "scripts" / "run_oracle_final_approval_dryrun.sh",
        FINAL_DIR / "build_final_approval_packet.py",
        FINAL_DIR / "review_manual_commands.py",
        FINAL_DIR / "verify_final_approval_packet.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def make_precreation_inputs(tmp_path: Path) -> tuple[Path, Path]:
    plan = tmp_path / "precreation_plan.json"
    commands = tmp_path / "commands"
    subprocess.run(
        [
            sys.executable,
            str(PRECREATION_DIR / "build_outbox_precreation_plan.py"),
            "--output",
            str(plan),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(PRECREATION_DIR / "generate_manual_precreation_commands.py"),
            "--plan",
            str(plan),
            "--output",
            str(commands),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return plan, commands


def build_packet(tmp_path: Path) -> Path:
    plan, commands = make_precreation_inputs(tmp_path)
    output = tmp_path / "final_packet"
    subprocess.run(
        [
            sys.executable,
            str(FINAL_DIR / "build_final_approval_packet.py"),
            "--precreation-plan",
            str(plan),
            "--manual-commands-dir",
            str(commands),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def run_review(commands: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(FINAL_DIR / "review_manual_commands.py"), "--commands-dir", str(commands)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_verify(packet: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(FINAL_DIR / "verify_final_approval_packet.py"), "--packet", str(packet)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def active_lines(text: str):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("echo "):
            continue
        if stripped == "set -euo pipefail":
            continue
        if re.match(r"^[A-Z_]+=", stripped):
            continue
        yield stripped
