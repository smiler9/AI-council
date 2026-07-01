import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
STAGING_DIR = ROOT / "examples" / "oracle_staging"
FIXTURE_BOT = STAGING_DIR / "fixtures" / "minimal_penny_stock_bot.py"


def test_analyze_us_trader_bot_finds_fixture_functions():
    script = STAGING_DIR / "analyze_us_trader_bot.py"
    result = subprocess.run(
        [sys.executable, str(script), "--source", str(FIXTURE_BOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["functions_found"]["analyze_signals"] is True
    assert payload["functions_found"]["scan_and_enter"] is True
    assert payload["functions_found"]["place_order"] is True
    assert payload["functions_found"]["check_exits"] is True
    assert payload["functions_found"]["force_close_all"] is True
    assert payload["order_execution_allowed"] is False
    assert any(item["function"] == "scan_and_enter" for item in payload["safe_insertion_candidates"])


def test_analyzer_classifies_unsafe_insertion_points():
    script = STAGING_DIR / "analyze_us_trader_bot.py"
    result = subprocess.run(
        [sys.executable, str(script), "--source", str(FIXTURE_BOT)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    unsafe = {item["function"] for item in payload["unsafe_insertion_points"]}

    assert unsafe == {"place_order", "check_exits", "force_close_all"}


def test_prepare_staging_rehearsal_copies_without_modifying_source(tmp_path):
    script = STAGING_DIR / "prepare_staging_rehearsal.py"
    before = sha256_file(FIXTURE_BOT)
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-bot",
            str(FIXTURE_BOT),
            "--output",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    after = sha256_file(FIXTURE_BOT)
    payload = json.loads(result.stdout)

    assert before == after
    assert payload["status"] == "prepared"
    assert Path(payload["staging_bot"]).exists()
    assert Path(payload["exporter_module"]).exists()
    assert Path(payload["outbox_dir"]).exists()
    assert payload["source_modified"] is False
    assert payload["order_execution_allowed"] is False


def test_generate_export_hook_patch_preview_creates_diff(tmp_path):
    prepare = run_prepare(tmp_path)
    script = STAGING_DIR / "generate_export_hook_patch_preview.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            prepare["staging_bot"],
            "--diff-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert "export_ai_council_signal" in payload["diff"]
    assert "order_execution_allowed=false" in payload["diff"]
    assert payload["patched_preview_written"] is False


def test_generate_export_hook_patch_preview_fails_without_safe_point(tmp_path):
    source = tmp_path / "no_safe_point.py"
    source.write_text(
        "def analyze_signals(ticker):\n    return {'signals': []}\n",
        encoding="utf-8",
    )
    script = STAGING_DIR / "generate_export_hook_patch_preview.py"
    result = subprocess.run(
        [sys.executable, str(script), "--source", str(source), "--diff-only"],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["order_execution_allowed"] is False


def test_patched_preview_file_is_created_only_in_staging_output(tmp_path):
    prepare = run_prepare(tmp_path)
    output = tmp_path / "penny_stock_bot.patched.preview.py"
    script = STAGING_DIR / "generate_export_hook_patch_preview.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            prepare["staging_bot"],
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert output.exists()
    assert str(output).startswith(str(tmp_path))
    assert payload["patched_preview_written"] is True
    assert payload["patched_preview_path"] == str(output)


def test_validate_staging_patch_accepts_safe_preview(tmp_path):
    prepare = run_prepare(tmp_path)
    output = tmp_path / "penny_stock_bot.patched.preview.py"
    run_generate(prepare["staging_bot"], output)
    script = STAGING_DIR / "validate_staging_patch.py"
    result = subprocess.run(
        [sys.executable, str(script), "--source", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["has_exporter_import"] is True
    assert payload["has_export_call"] is True
    assert payload["unsafe_hook_hits"] == []
    assert payload["order_execution_allowed"] is False


def test_validate_staging_patch_rejects_unsafe_insertion(tmp_path):
    unsafe = tmp_path / "unsafe_patch.py"
    unsafe.write_text(
        "from ai_council_signal_exporter_module import build_ai_council_signal, export_ai_council_signal\n"
        "def place_order():\n"
        "    payload = build_ai_council_signal(symbol='TESTA', strategy_signal='x')\n"
        "    export_ai_council_signal(payload, 'outbox')\n"
        "    # order_execution_allowed=false review_only=true\n",
        encoding="utf-8",
    )
    script = STAGING_DIR / "validate_staging_patch.py"
    result = subprocess.run(
        [sys.executable, str(script), "--source", str(unsafe)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["unsafe_hook_hits"][0]["function"] == "place_order"


def test_oracle_staging_fixture_has_no_secret_markers():
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in STAGING_DIR.rglob("*")
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in {".py", ".md", ".json"}
            and path.name != "validate_staging_patch.py"
        )
    )
    forbidden = [
        "BEGIN PRIVATE KEY",
        "OPENSSH PRIVATE KEY",
        "ACCESS_TOKEN=",
        "API_SECRET=",
        "ORACLE_REAL_HOST_VALUE",
    ]
    for marker in forbidden:
        assert marker not in text


def test_oracle_staging_docs_include_safety_boundary():
    docs = (ROOT / "docs" / "US_TRADER_ORACLE_STAGING_REHEARSAL.md").read_text(encoding="utf-8")

    assert "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다" in docs
    assert "scripts/run_oracle_staging_rehearsal.sh" in docs
    assert "운영본 직접 수정 금지" in docs


def test_readme_includes_phase_24e_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Phase 24E Oracle Staging Patch Rehearsal" in readme
    assert "scripts/run_oracle_staging_rehearsal.sh" in readme
    assert "order_execution_allowed=false" in readme


def test_oracle_staging_order_execution_allowed_always_false():
    files = [
        STAGING_DIR / "analyze_us_trader_bot.py",
        STAGING_DIR / "prepare_staging_rehearsal.py",
        STAGING_DIR / "generate_export_hook_patch_preview.py",
        STAGING_DIR / "validate_staging_patch.py",
        STAGING_DIR / "fixtures" / "sample_signal_candidate.json",
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "order_execution_allowed" in text
        assert '"order_execution_allowed": true' not in text
        assert "order_execution_allowed=True" not in text


def test_oracle_staging_code_does_not_add_broker_or_order_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in STAGING_DIR.rglob("*.py")
        if path.name != "validate_staging_patch.py"
    )
    forbidden_terms = [
        "requests.post",
        "requests.get",
        "httpx.",
        "tradeapi.REST(",
        "submit_order(",
        "create_order(",
        "cancel_order(",
        "close_position(",
        "systemctl ",
        "paramiko.",
    ]
    for term in forbidden_terms:
        assert term not in source


def test_run_oracle_staging_rehearsal_script_exists():
    assert (ROOT / "scripts" / "run_oracle_staging_rehearsal.sh").exists()


def run_prepare(output_dir: Path) -> dict:
    script = STAGING_DIR / "prepare_staging_rehearsal.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-bot",
            str(FIXTURE_BOT),
            "--output",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_generate(source: str, output: Path) -> dict:
    script = STAGING_DIR / "generate_export_hook_patch_preview.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source",
            source,
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
