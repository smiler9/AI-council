import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_DIR = ROOT / "examples" / "oracle_deployment"


def test_build_signal_export_bundle_creates_bundle_in_tmp(tmp_path):
    output = tmp_path / "oracle_signal_export_bundle"
    script = DEPLOYMENT_DIR / "build_signal_export_bundle.py"
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
    assert (output / "ai_council_signal_exporter_module.py").exists()
    assert (output / "us_trader_signal_outbox_bridge.py").exists()
    assert (output / "mapping_profiles" / "us_trader_oracle_v1.json").exists()
    assert payload["order_execution_allowed"] is False
    assert manifest["manual_approval_required"] is True
    assert manifest["order_execution_allowed"] is False


def test_bundle_manifest_contains_sha256_entries(tmp_path):
    output = build_bundle(tmp_path)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["files"]
    for entry in manifest["files"]:
        assert entry["path"]
        assert len(entry["sha256"]) == 64
        assert (output / entry["path"]).exists()


def test_verify_signal_export_bundle_success(tmp_path):
    output = build_bundle(tmp_path)
    script = DEPLOYMENT_DIR / "verify_signal_export_bundle.py"
    result = subprocess.run(
        [sys.executable, str(script), "--bundle", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["hash_failures"] == []
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["dangerous_hits"] == []
    assert payload["order_execution_allowed"] is False


def test_verify_signal_export_bundle_detects_sha256_tamper(tmp_path):
    output = build_bundle(tmp_path)
    (output / "README.md").write_text("tampered\n", encoding="utf-8")
    script = DEPLOYMENT_DIR / "verify_signal_export_bundle.py"
    result = subprocess.run(
        [sys.executable, str(script), "--bundle", str(output)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["hash_failures"]


def test_verify_signal_export_bundle_detects_secret_marker(tmp_path):
    output = build_bundle(tmp_path)
    secret_file = output / "secret_leak.txt"
    secret_file.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\n", encoding="utf-8")
    script = DEPLOYMENT_DIR / "verify_signal_export_bundle.py"
    result = subprocess.run(
        [sys.executable, str(script), "--bundle", str(output)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["secret_hits"]


def test_verify_signal_export_bundle_detects_order_execution_true(tmp_path):
    output = build_bundle(tmp_path)
    marker = output / "bad_flag.txt"
    marker.write_text('{"order_execution_allowed": true}\n', encoding="utf-8")
    script = DEPLOYMENT_DIR / "verify_signal_export_bundle.py"
    result = subprocess.run(
        [sys.executable, str(script), "--bundle", str(output)],
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert result.returncode != 0
    assert payload["status"] == "failed"
    assert payload["order_true_hits"]


def test_oracle_readiness_check_dry_run():
    script = DEPLOYMENT_DIR / "oracle_readiness_check.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    commands = "\n".join(payload["command_preview"]["commands"])

    assert payload["status"] == "ok"
    assert payload["mode"] == "dry_run"
    assert payload["ssh_executed"] is False
    assert payload["oracle_server_contacted"] is False
    assert payload["order_execution_allowed"] is False
    assert "systemctl status --no-pager" in commands


def test_readiness_check_has_no_start_stop_restart_commands():
    script = DEPLOYMENT_DIR / "oracle_readiness_check.py"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    commands = "\n".join(payload["command_preview"]["commands"])
    for forbidden in ["systemctl start", "systemctl stop", "systemctl restart", "service start", "service stop"]:
        assert forbidden not in commands


def test_templates_do_not_hardcode_oracle_identity():
    text = "\n".join(path.read_text(encoding="utf-8") for path in (DEPLOYMENT_DIR / "templates").glob("*"))
    forbidden = ["ORACLE_REAL_HOST_VALUE", "REAL_PRIVATE_KEY_PATH", "REAL_SSH_KEY_FILENAME"]
    for marker in forbidden:
        assert marker not in text
    assert "<oracle-host>" in (ROOT / "docs" / "US_TRADER_ORACLE_DEPLOYMENT_RUNBOOK.md").read_text(encoding="utf-8")


def test_manual_approval_docs_include_safety_boundary():
    manual = (ROOT / "docs" / "US_TRADER_ORACLE_MANUAL_APPROVAL_GATE.md").read_text(encoding="utf-8")
    runbook = (ROOT / "docs" / "US_TRADER_ORACLE_DEPLOYMENT_RUNBOOK.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in manual
    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in runbook
    assert "Rollback" in runbook
    assert "수동 승인" in manual


def test_generated_bundle_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/" in gitignore
    assert "deployment_bundles/" in gitignore
    assert "examples/oracle_deployment/output/" in gitignore
    assert "examples/oracle_deployment/bundles/" in gitignore


def test_deployment_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_signal_export_bundle.sh",
        ROOT / "scripts" / "verify_oracle_signal_export_bundle.sh",
        ROOT / "scripts" / "run_oracle_readiness_check_dryrun.sh",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def test_deployment_tools_do_not_write_oracle_or_control_systemd():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            ROOT / "scripts" / "build_oracle_signal_export_bundle.sh",
            ROOT / "scripts" / "verify_oracle_signal_export_bundle.sh",
            ROOT / "scripts" / "run_oracle_readiness_check_dryrun.sh",
        ]
    )
    forbidden_terms = [
        "systemctl start",
        "systemctl stop",
        "systemctl restart",
        "scp ",
        "rsync ",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_readme_includes_phase_24f_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24F Oracle Deployment Bundle Approval Gate" in readme
    assert "scripts/build_oracle_signal_export_bundle.sh" in readme
    assert "scripts/verify_oracle_signal_export_bundle.sh" in readme
    assert "scripts/run_oracle_readiness_check_dryrun.sh" in readme
    assert "order_execution_allowed=false" in readme


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
