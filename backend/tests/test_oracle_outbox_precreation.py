import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRECREATION_DIR = ROOT / "examples" / "oracle_outbox_precreation"
TEMPLATES = PRECREATION_DIR / "templates"


def test_build_outbox_precreation_plan_creates_tmp_plan(tmp_path):
    output = tmp_path / "precreation_plan.json"
    script = PRECREATION_DIR / "build_outbox_precreation_plan.py"
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    plan = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert output.exists()
    assert plan["mode"] == "precreation_manual"
    assert plan["manual_approval_required"] is True
    assert plan["remote_write_planned"] is True
    assert plan["remote_write_executed"] is False
    assert plan["remote_delete"] is False
    assert plan["remote_move"] is False
    assert plan["systemd_changes_planned"] is False
    assert plan["order_execution_allowed"] is False
    assert plan["paths"]["outbox_dir"] == "<oracle-trading-dir>/ai_council_outbox"


def test_verify_outbox_precreation_plan_success(tmp_path):
    plan = build_plan(tmp_path)
    result = run_verify(plan)
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "ok"
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["dangerous_hits"] == []
    assert payload["remote_write_executed"] is False
    assert payload["remote_delete"] is False
    assert payload["remote_move"] is False
    assert payload["systemd_changes_planned"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_rejects_remote_write_executed_true(tmp_path):
    plan = mutate_plan(tmp_path, {"remote_write_executed": True})
    payload = json.loads(run_verify(plan).stdout)

    assert payload["status"] == "failed"
    assert "remote_write_executed must be false" in payload["errors"]


def test_verify_rejects_remote_delete_true(tmp_path):
    plan = mutate_plan(tmp_path, {"remote_delete": True})
    payload = json.loads(run_verify(plan).stdout)

    assert payload["status"] == "failed"
    assert "remote_delete must be false" in payload["errors"]


def test_verify_rejects_remote_move_true(tmp_path):
    plan = mutate_plan(tmp_path, {"remote_move": True})
    payload = json.loads(run_verify(plan).stdout)

    assert payload["status"] == "failed"
    assert "remote_move must be false" in payload["errors"]


def test_verify_rejects_systemd_changes_planned_true(tmp_path):
    plan = mutate_plan(tmp_path, {"systemd_changes_planned": True})
    payload = json.loads(run_verify(plan).stdout)

    assert payload["status"] == "failed"
    assert "systemd_changes_planned must be false" in payload["errors"]


def test_verify_rejects_secret_private_key_marker(tmp_path):
    marker = "-----BEGIN " + "OPENSSH PRIVATE KEY-----"
    plan = mutate_plan(tmp_path, {"safety_boundary": marker})
    payload = json.loads(run_verify(plan).stdout)

    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_generate_manual_precreation_commands_creates_files(tmp_path):
    plan = build_plan(tmp_path)
    output = tmp_path / "commands"
    script = PRECREATION_DIR / "generate_manual_precreation_commands.py"
    result = subprocess.run(
        [sys.executable, str(script), "--plan", str(plan), "--output", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["command_file_count"] == 5
    for name in [
        "00_check_existing_paths.manual.sh",
        "01_create_outbox_dirs.manual.sh",
        "02_verify_outbox_dirs.manual.sh",
        "03_permissions_review.manual.sh",
        "99_rollback_outbox_dirs.manual.sh",
    ]:
        assert (output / name).exists()
    assert payload["remote_write_executed"] is False
    assert payload["remote_delete"] is False
    assert payload["remote_move"] is False
    assert payload["systemd_changes_planned"] is False
    assert payload["order_execution_allowed"] is False


def test_generated_commands_have_no_active_remote_write_or_systemd(tmp_path):
    plan = build_plan(tmp_path)
    output = tmp_path / "commands"
    generate_commands(plan, output)
    forbidden = [
        "mkdir ",
        "touch ",
        "chmod ",
        "chown ",
        "rm ",
        "mv ",
        "systemctl ",
        "service ",
    ]

    for path in output.glob("*.sh"):
        for line in active_lines(path.read_text(encoding="utf-8")):
            for term in forbidden:
                assert term not in line


def test_precreation_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-trading-dir>" in text
    assert "order_execution_allowed=false" in text or '"order_execution_allowed": false' in text


def test_precreation_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_OUTBOX_PRECREATION_REHEARSAL.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24L" in docs
    assert "원격 파일 삭제나 이동은 Phase 24L 범위에서 금지" in docs
    assert "systemd" in docs


def test_readme_includes_phase_24l_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24L Oracle Outbox Pre-creation Rehearsal" in readme
    assert "scripts/run_oracle_outbox_precreation_dryrun.sh" in readme
    assert "remote_write_executed=false" in readme


def test_generated_precreation_plan_and_commands_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_outbox_precreation/" in gitignore
    assert "examples/oracle_outbox_precreation/output/" in gitignore
    assert "examples/oracle_outbox_precreation/.state/" in gitignore


def test_order_execution_allowed_always_false_in_precreation_files():
    files = [
        PRECREATION_DIR / "build_outbox_precreation_plan.py",
        PRECREATION_DIR / "verify_outbox_precreation_plan.py",
        PRECREATION_DIR / "generate_manual_precreation_commands.py",
        PRECREATION_DIR / "sample_precreation_plan.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_precreation_code_does_not_add_broker_order_or_remote_operations():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PRECREATION_DIR / "build_outbox_precreation_plan.py",
            PRECREATION_DIR / "verify_outbox_precreation_plan.py",
            PRECREATION_DIR / "generate_manual_precreation_commands.py",
            ROOT / "scripts" / "build_oracle_outbox_precreation_plan.sh",
            ROOT / "scripts" / "verify_oracle_outbox_precreation_plan.sh",
            ROOT / "scripts" / "generate_oracle_outbox_precreation_commands.sh",
            ROOT / "scripts" / "run_oracle_outbox_precreation_dryrun.sh",
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


def test_precreation_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_outbox_precreation_plan.sh",
        ROOT / "scripts" / "verify_oracle_outbox_precreation_plan.sh",
        ROOT / "scripts" / "generate_oracle_outbox_precreation_commands.sh",
        ROOT / "scripts" / "run_oracle_outbox_precreation_dryrun.sh",
        PRECREATION_DIR / "build_outbox_precreation_plan.py",
        PRECREATION_DIR / "verify_outbox_precreation_plan.py",
        PRECREATION_DIR / "generate_manual_precreation_commands.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def build_plan(tmp_path: Path) -> Path:
    output = tmp_path / "precreation_plan.json"
    script = PRECREATION_DIR / "build_outbox_precreation_plan.py"
    subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def mutate_plan(tmp_path: Path, updates: dict) -> Path:
    plan = build_plan(tmp_path)
    payload = json.loads(plan.read_text(encoding="utf-8"))
    for key, value in updates.items():
        if key == "paths":
            payload["paths"].update(value)
        else:
            payload[key] = value
    plan.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return plan


def run_verify(plan: Path) -> subprocess.CompletedProcess[str]:
    script = PRECREATION_DIR / "verify_outbox_precreation_plan.py"
    return subprocess.run(
        [sys.executable, str(script), "--plan", str(plan)],
        capture_output=True,
        text=True,
    )


def generate_commands(plan: Path, output: Path) -> None:
    script = PRECREATION_DIR / "generate_manual_precreation_commands.py"
    subprocess.run(
        [sys.executable, str(script), "--plan", str(plan), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )


def active_lines(text: str):
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith("echo "):
            continue
        if stripped == "set -euo pipefail":
            continue
        if re.match(r"^[A-Z_]+=", stripped):
            continue
        yield stripped
