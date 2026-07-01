import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APPROVAL_DIR = ROOT / "examples" / "oracle_outbox_approval"
TEMPLATES = APPROVAL_DIR / "templates"


def test_build_outbox_approval_package_creates_package_in_tmp(tmp_path):
    output = tmp_path / "oracle_outbox_approval"
    script = APPROVAL_DIR / "build_outbox_approval_package.py"
    result = subprocess.run(
        [sys.executable, str(script), "--output", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert output.exists()
    assert (output / "outbox_paths.example.json").exists()
    assert (output / "outbox_file_contract.md").exists()
    assert (output / "outbox_retention_policy.md").exists()
    assert (output / "outbox_rollback_plan.md").exists()
    assert payload["remote_delete"] is False
    assert payload["remote_move"] is False
    assert payload["order_execution_allowed"] is False
    assert manifest["manual_approval_required"] is True
    assert manifest["order_execution_allowed"] is False


def test_outbox_approval_manifest_contains_sha256_entries(tmp_path):
    output = build_package(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["file_count"] == len(manifest["files"])
    for entry in manifest["files"]:
        assert entry["path"]
        assert len(entry["sha256"]) == 64
        assert (output / entry["path"]).exists()


def test_verify_outbox_approval_package_success(tmp_path):
    output = build_package(tmp_path)
    script = APPROVAL_DIR / "verify_outbox_approval_package.py"
    result = subprocess.run(
        [sys.executable, str(script), "--package", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["hash_failures"] == []
    assert payload["secret_hits"] == []
    assert payload["active_dangerous_hits"] == []
    assert payload["remote_delete"] is False
    assert payload["remote_move"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_outbox_approval_package_detects_secret_marker(tmp_path):
    output = build_package(tmp_path)
    marker = output / "secret_marker.txt"
    marker.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
    result = run_verify(output)
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_verify_outbox_approval_package_rejects_active_mkdir_chmod_systemctl(tmp_path):
    output = build_package(tmp_path)
    script_path = output / "outbox_apply_commands.example.sh"
    script_path.write_text(
        "# bad active commands below\n"
        "mkdir -p <oracle-trading-dir>/ai_council_outbox/\n"
        "chmod 750 <oracle-trading-dir>/ai_council_outbox/\n"
        "systemctl restart <service-name>\n",
        encoding="utf-8",
    )
    result = run_verify(output)
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["active_dangerous_hits"]


def test_outbox_file_contract_includes_required_fields():
    text = (TEMPLATES / "outbox_file_contract.md").read_text(encoding="utf-8")

    for field in [
        "source",
        "signal_id",
        "symbol",
        "ticker",
        "signal",
        "strategy_signal",
        "action",
        "raw_side",
        "price",
        "volume",
        "timestamp",
        "order_execution_allowed=false",
    ]:
        assert field in text
    assert "source + signal_id" in text
    assert ".tmp" in text


def test_retention_policy_forbids_remote_delete_and_move():
    text = (TEMPLATES / "outbox_retention_policy.md").read_text(encoding="utf-8")

    assert "Remote Oracle file deletion and movement are prohibited" in text
    assert "remote_delete=false" in text
    assert "remote_move=false" in text
    assert "local state" in text


def test_rollback_plan_includes_safety_boundary():
    text = (TEMPLATES / "outbox_rollback_plan.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in text
    assert "Mac Pull Rollback" in text
    assert "No broker API" in text or "No broker API is connected" in text


def test_manual_checklist_includes_unsafe_function_checks():
    text = (TEMPLATES / "outbox_manual_checklist.md").read_text(encoding="utf-8")

    assert "`place_order` 내부 미삽입 확인" in text
    assert "`check_exits` 내부 미삽입 확인" in text
    assert "`force_close_all` 내부 미삽입 확인" in text
    assert "Mac pull smoke 통과" in text


def test_outbox_approval_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_OUTBOX_PATH_APPROVAL.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "<oracle-trading-dir>/ai_council_outbox/" in docs
    assert "remote_delete=false" in docs
    assert "remote_move=false" in docs


def test_readme_includes_phase_24k_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24K Oracle Outbox Path Approval Package" in readme
    assert "scripts/run_oracle_outbox_approval_dryrun.sh" in readme
    assert "remote_delete=false" in readme


def test_generated_outbox_approval_package_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_outbox_approval/" in gitignore
    assert "outbox_approval_packages/" in gitignore
    assert "examples/oracle_outbox_approval/output/" in gitignore
    assert "examples/oracle_outbox_approval/packages/" in gitignore
    assert "examples/oracle_outbox_approval/.state/" in gitignore


def test_outbox_approval_order_execution_allowed_always_false():
    files = [
        APPROVAL_DIR / "build_outbox_approval_package.py",
        APPROVAL_DIR / "verify_outbox_approval_package.py",
        APPROVAL_DIR / "sample_outbox_approval.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_outbox_approval_code_does_not_add_broker_order_or_active_remote_actions():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            APPROVAL_DIR / "build_outbox_approval_package.py",
            APPROVAL_DIR / "verify_outbox_approval_package.py",
            ROOT / "scripts" / "build_oracle_outbox_approval_package.sh",
            ROOT / "scripts" / "verify_oracle_outbox_approval_package.sh",
            ROOT / "scripts" / "run_oracle_outbox_approval_dryrun.sh",
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
        "scp ",
        "rsync ",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_outbox_approval_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_outbox_approval_package.sh",
        ROOT / "scripts" / "verify_oracle_outbox_approval_package.sh",
        ROOT / "scripts" / "run_oracle_outbox_approval_dryrun.sh",
        APPROVAL_DIR / "build_outbox_approval_package.py",
        APPROVAL_DIR / "verify_outbox_approval_package.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_apply_commands_example_has_no_active_mkdir_chmod_systemctl():
    text = (TEMPLATES / "outbox_apply_commands.example.sh").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("echo "):
            continue
        assert "mkdir " not in stripped
        assert "chmod " not in stripped
        assert "systemctl " not in stripped


def build_package(tmp_path: Path) -> Path:
    output = tmp_path / "oracle_outbox_approval"
    script = APPROVAL_DIR / "build_outbox_approval_package.py"
    subprocess.run(
        [sys.executable, str(script), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return output


def run_verify(output: Path) -> subprocess.CompletedProcess[str]:
    script = APPROVAL_DIR / "verify_outbox_approval_package.py"
    return subprocess.run(
        [sys.executable, str(script), "--package", str(output)],
        capture_output=True,
        text=True,
    )
