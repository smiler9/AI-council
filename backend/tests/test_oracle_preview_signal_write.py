import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "examples" / "oracle_preview_signal_write"
TEMPLATES = PREVIEW_DIR / "templates"


def test_build_preview_signal_file_creates_tmp_signal(tmp_path):
    output = tmp_path / "us_trader_preview_signal.json"
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "build_preview_signal_file.py"), "--output", str(output), "--pretty"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    signal = json.loads(output.read_text(encoding="utf-8"))

    assert payload["status"] == "ok"
    assert output.exists()
    assert signal["symbol"] == "TESTA"
    assert signal["action"] == "buy"
    assert signal["review_only"] is True
    assert signal["simulation_only"] is True
    assert signal["order_execution_allowed"] is False
    assert "not an order" in " ".join(signal["notes"])


def test_verify_preview_signal_file_success():
    payload = run_signal_verify(PREVIEW_DIR / "sample_preview_signal.json")

    assert payload["status"] == "ok"
    assert payload["validation_status"] == "passed"
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["review_only"] is True
    assert payload["simulation_only"] is True
    assert payload["order_execution_allowed"] is False


def test_verify_signal_rejects_order_execution_allowed_true(tmp_path):
    path = mutate_signal(tmp_path, {"order_execution_allowed": True})
    payload = run_signal_verify(path)

    assert payload["status"] == "failed"
    assert payload["order_true_hits"]


def test_verify_signal_rejects_missing_required_field(tmp_path):
    signal = json.loads((PREVIEW_DIR / "sample_preview_signal.json").read_text(encoding="utf-8"))
    signal.pop("symbol")
    output = tmp_path / "signal.json"
    output.write_text(json.dumps(signal), encoding="utf-8")
    payload = run_signal_verify(output)

    assert payload["status"] == "failed"
    assert any("symbol" in error for error in payload["errors"])


def test_build_manual_signal_write_packet_creates_packet(tmp_path):
    signal_path = tmp_path / "signal.json"
    subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "build_preview_signal_file.py"), "--output", str(signal_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "packet"
    result = subprocess.run(
        [
            sys.executable,
            str(PREVIEW_DIR / "build_manual_signal_write_packet.py"),
            "--signal",
            str(signal_path),
            "--output",
            str(output),
            "--pretty",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert (output / "manifest.json").exists()
    assert (output / "manual_signal_write_commands.example.sh").exists()
    assert payload["remote_write_executed"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_manual_signal_write_packet_success(tmp_path):
    packet = build_packet(tmp_path)
    payload = run_packet_verify(packet)

    assert payload["status"] == "ok"
    assert payload["active_dangerous_commands_found"] is False
    assert payload["commented_manual_commands"]
    assert payload["secret_hits"] == []
    assert payload["order_true_hits"] == []
    assert payload["order_execution_allowed"] is False


def test_verify_packet_rejects_active_scp(tmp_path):
    packet = build_packet(tmp_path)
    command_file = packet / "manual_signal_write_commands.example.sh"
    command_file.write_text(command_file.read_text(encoding="utf-8") + "\nscp file host:path\n", encoding="utf-8")
    payload = run_packet_verify(packet)

    assert payload["status"] == "failed"
    assert any("scp" in item for item in payload["active_dangerous_commands"])


def test_verify_packet_rejects_active_rsync(tmp_path):
    packet = build_packet(tmp_path)
    command_file = packet / "manual_signal_write_commands.example.sh"
    command_file.write_text(command_file.read_text(encoding="utf-8") + "\nrsync file host:path\n", encoding="utf-8")
    payload = run_packet_verify(packet)

    assert payload["status"] == "failed"
    assert any("rsync" in item for item in payload["active_dangerous_commands"])


def test_verify_packet_rejects_active_systemctl(tmp_path):
    packet = build_packet(tmp_path)
    command_file = packet / "manual_signal_write_commands.example.sh"
    command_file.write_text(command_file.read_text(encoding="utf-8") + "\nsystemctl restart service\n", encoding="utf-8")
    payload = run_packet_verify(packet)

    assert payload["status"] == "failed"
    assert any("systemctl" in item for item in payload["active_dangerous_commands"])


def test_record_preview_signal_write_result_creates_sample_result(tmp_path):
    signal_path = tmp_path / "signal.json"
    subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "build_preview_signal_file.py"), "--output", str(signal_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    output = tmp_path / "result.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PREVIEW_DIR / "record_preview_signal_write_result.py"),
            "--signal",
            str(signal_path),
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
    assert recorded["result_status"] == "passed"
    assert recorded["observations"]["file_uploaded_manually"] is True
    assert recorded["safety"]["systemd_changed"] is False
    assert recorded["safety"]["broker_api_called"] is False
    assert recorded["safety"]["order_execution_allowed"] is False


def test_verify_preview_signal_write_result_passes_sample():
    payload = run_result_verify(PREVIEW_DIR / "sample_signal_write_result_passed.json")

    assert payload["status"] == "ok"
    assert payload["validation_status"] == "passed"
    assert payload["systemd_changed"] is False
    assert payload["broker_api_called"] is False
    assert payload["order_execution_allowed"] is False


def test_verify_result_rejects_systemd_changed_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"systemd_changed": True})
    payload = run_result_verify(result_path)

    assert payload["status"] == "failed"
    assert any("systemd_changed" in error for error in payload["errors"])


def test_verify_result_rejects_broker_api_called_true(tmp_path):
    result_path = mutate_result(tmp_path, safety_updates={"broker_api_called": True})
    payload = run_result_verify(result_path)

    assert payload["status"] == "failed"
    assert any("broker_api_called" in error for error in payload["errors"])


def test_decide_pull_rehearsal_go_no_go_creates_go_for_valid_result(tmp_path):
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PREVIEW_DIR / "decide_pull_rehearsal_go_no_go.py"),
            "--result",
            str(PREVIEW_DIR / "sample_signal_write_result_passed.json"),
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
    assert decision["next_phase"] == "Phase 24S Mac pull actual preview signal rehearsal"
    assert decision["decision_scope"] == "Allows only Mac pull rehearsal, not live bot patching or order execution."
    assert "not live bot patch approval" in " ".join(decision["required_manual_acknowledgements"])
    assert decision["order_execution_allowed"] is False


def test_decide_pull_rehearsal_go_no_go_creates_no_go_for_failed_result(tmp_path):
    output = tmp_path / "decision.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PREVIEW_DIR / "decide_pull_rehearsal_go_no_go.py"),
            "--result",
            str(PREVIEW_DIR / "sample_signal_write_result_failed.json"),
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
    assert decision["order_execution_allowed"] is False


def test_preview_signal_write_templates_have_no_actual_oracle_ip_or_key_path():
    text = "\n".join(path.read_text(encoding="utf-8") for path in TEMPLATES.glob("*"))
    text += "\n" + (PREVIEW_DIR / "sample_preview_signal.json").read_text(encoding="utf-8")
    text += "\n" + (PREVIEW_DIR / "sample_signal_write_result_passed.json").read_text(encoding="utf-8")

    assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text) is None
    assert re.search(r"ssh-key-\d{4}-\d{2}-\d{2}", text) is None
    assert re.search(r"/Users/[^\\s'\"]*/\\.ssh/", text) is None
    assert "<oracle-host>" in text
    assert "order_execution_allowed" in text


def test_preview_signal_write_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_PREVIEW_SIGNAL_WRITE_REHEARSAL.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "Phase 24R" in docs
    assert "GO가 의미하는 것과 의미하지 않는 것" in docs
    assert "운영봇 patch 승인" in docs


def test_readme_includes_phase_24r_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24R Oracle Preview Signal Write Rehearsal" in readme
    assert "scripts/run_oracle_preview_signal_write_dryrun.sh" in readme
    assert "GO는 Mac Pull 리허설 허용" in readme


def test_frontend_includes_phase_24r_guidance():
    source = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    assert "Oracle Preview Signal 파일 쓰기 리허설" in source
    assert "scripts/run_oracle_preview_signal_write_dryrun.sh" in source
    assert "GO는 Mac Pull 리허설 허용" in source
    assert "운영봇 patch 승인이 아닙니다" in source


def test_generated_preview_signal_write_paths_are_gitignored():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "tmp/oracle_preview_signal_write/" in gitignore
    assert "examples/oracle_preview_signal_write/output/" in gitignore
    assert "examples/oracle_preview_signal_write/.state/" in gitignore


def test_order_execution_allowed_always_false_in_preview_signal_write_files():
    files = [
        PREVIEW_DIR / "build_preview_signal_file.py",
        PREVIEW_DIR / "verify_preview_signal_file.py",
        PREVIEW_DIR / "build_manual_signal_write_packet.py",
        PREVIEW_DIR / "verify_manual_signal_write_packet.py",
        PREVIEW_DIR / "record_preview_signal_write_result.py",
        PREVIEW_DIR / "verify_preview_signal_write_result.py",
        PREVIEW_DIR / "decide_pull_rehearsal_go_no_go.py",
        PREVIEW_DIR / "sample_preview_signal.json",
        PREVIEW_DIR / "sample_signal_write_result_passed.json",
        PREVIEW_DIR / "sample_signal_write_result_failed.json",
        *TEMPLATES.glob("*"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text
        assert "ORDER_EXECUTION_ALLOWED=true" not in text


def test_preview_signal_write_code_does_not_add_broker_order_or_remote_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PREVIEW_DIR / "build_preview_signal_file.py",
            PREVIEW_DIR / "verify_preview_signal_file.py",
            PREVIEW_DIR / "build_manual_signal_write_packet.py",
            PREVIEW_DIR / "verify_manual_signal_write_packet.py",
            PREVIEW_DIR / "record_preview_signal_write_result.py",
            PREVIEW_DIR / "verify_preview_signal_write_result.py",
            PREVIEW_DIR / "decide_pull_rehearsal_go_no_go.py",
            ROOT / "scripts" / "build_oracle_preview_signal_file.sh",
            ROOT / "scripts" / "verify_oracle_preview_signal_file.sh",
            ROOT / "scripts" / "build_oracle_preview_signal_write_packet.sh",
            ROOT / "scripts" / "verify_oracle_preview_signal_write_packet.sh",
            ROOT / "scripts" / "record_oracle_preview_signal_write_sample_result.sh",
            ROOT / "scripts" / "verify_oracle_preview_signal_write_result.sh",
            ROOT / "scripts" / "decide_oracle_pull_rehearsal_go_no_go.sh",
            ROOT / "scripts" / "run_oracle_preview_signal_write_dryrun.sh",
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
    ]
    for term in forbidden_terms:
        assert term not in source


def test_preview_signal_write_scripts_exist_and_are_executable():
    scripts = [
        ROOT / "scripts" / "build_oracle_preview_signal_file.sh",
        ROOT / "scripts" / "verify_oracle_preview_signal_file.sh",
        ROOT / "scripts" / "build_oracle_preview_signal_write_packet.sh",
        ROOT / "scripts" / "verify_oracle_preview_signal_write_packet.sh",
        ROOT / "scripts" / "record_oracle_preview_signal_write_sample_result.sh",
        ROOT / "scripts" / "verify_oracle_preview_signal_write_result.sh",
        ROOT / "scripts" / "decide_oracle_pull_rehearsal_go_no_go.sh",
        ROOT / "scripts" / "run_oracle_preview_signal_write_dryrun.sh",
        PREVIEW_DIR / "build_preview_signal_file.py",
        PREVIEW_DIR / "verify_preview_signal_file.py",
        PREVIEW_DIR / "build_manual_signal_write_packet.py",
        PREVIEW_DIR / "verify_manual_signal_write_packet.py",
        PREVIEW_DIR / "record_preview_signal_write_result.py",
        PREVIEW_DIR / "verify_preview_signal_write_result.py",
        PREVIEW_DIR / "decide_pull_rehearsal_go_no_go.py",
    ]
    for script in scripts:
        assert script.exists()
        assert script.stat().st_mode & 0o111


def run_signal_verify(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "verify_preview_signal_file.py"), "--signal", str(path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_packet_verify(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "verify_manual_signal_write_packet.py"), "--packet", str(path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_result_verify(path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "verify_preview_signal_write_result.py"), "--result", str(path)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def mutate_signal(tmp_path: Path, updates: dict) -> Path:
    payload = json.loads((PREVIEW_DIR / "sample_preview_signal.json").read_text(encoding="utf-8"))
    payload.update(updates)
    output = tmp_path / "signal.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output


def mutate_result(tmp_path: Path, *, observation_updates: dict | None = None, safety_updates: dict | None = None) -> Path:
    payload = json.loads((PREVIEW_DIR / "sample_signal_write_result_passed.json").read_text(encoding="utf-8"))
    if observation_updates:
        payload["observations"].update(observation_updates)
    if safety_updates:
        payload["safety"].update(safety_updates)
    output = tmp_path / "result.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return output


def build_packet(tmp_path: Path) -> Path:
    signal_path = tmp_path / "signal.json"
    subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "build_preview_signal_file.py"), "--output", str(signal_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    packet = tmp_path / "packet"
    subprocess.run(
        [
            sys.executable,
            str(PREVIEW_DIR / "build_manual_signal_write_packet.py"),
            "--signal",
            str(signal_path),
            "--output",
            str(packet),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return packet
