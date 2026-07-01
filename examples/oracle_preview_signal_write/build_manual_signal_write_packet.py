#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "examples" / "oracle_preview_signal_write"
DEFAULT_SIGNAL = ROOT / "tmp" / "oracle_preview_signal_write" / "us_trader_preview_signal.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_signal_write" / "manual_write_packet"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)
PACKET_FILES = [
    "us_trader_preview_signal.json",
    "manual_signal_write_commands.example.sh",
    "post_signal_write_verify_commands.example.sh",
    "signal_write_result_template.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local manual Oracle preview signal write packet.")
    parser.add_argument("--signal", default=str(DEFAULT_SIGNAL))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        result = build_packet(Path(args.signal), Path(args.output), force=args.force)
        if args.verify:
            verify = run_verify(Path(args.output))
            result["verify"] = verify
            if verify.get("status") != "ok":
                result["status"] = "failed"
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def build_packet(signal_path: Path, output_dir: Path, *, force: bool) -> dict[str, Any]:
    signal = signal_path.expanduser().resolve()
    output = output_dir.expanduser().resolve()
    if not signal.exists():
        raise FileNotFoundError(f"preview signal not found: {signal}")
    validation = run_signal_verify(signal)
    if validation.get("status") != "ok":
        raise RuntimeError(f"preview signal validation failed: {validation.get('errors')}")
    reset_output_dir(output, force=force)
    output.mkdir(parents=True, exist_ok=True)

    packet_signal = output / "us_trader_preview_signal.json"
    shutil.copyfile(signal, packet_signal)
    payload = json.loads(packet_signal.read_text(encoding="utf-8"))
    files = {
        "manual_signal_write_commands.example.sh": render_manual_signal_write_commands(),
        "post_signal_write_verify_commands.example.sh": render_post_signal_write_verify_commands(),
        "signal_write_result_template.json": json.dumps(build_result_template(payload, packet_signal), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n",
    }
    for name, content in files.items():
        (output / name).write_text(content, encoding="utf-8")

    manifest_files = [file_entry(output / name, Path(name)) for name in PACKET_FILES]
    manifest = {
        "status": "ok",
        "packet_name": "oracle_preview_signal_manual_write_packet",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(output),
        "files": manifest_files,
        "file_count": len(manifest_files),
        "manual_approval_required": True,
        "remote_write_executed": False,
        "remote_delete": False,
        "remote_move": False,
        "remote_permission_change_executed": False,
        "systemd_changed": False,
        "oracle_live_bot_modified": False,
        "penny_stock_bot_modified": False,
        "broker_api_connected": False,
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": False,
        "safety_notes": [
            "Packet generation is local only.",
            "scp and rsync examples are commented manual candidates.",
            "No Oracle service, live bot, broker API, or order path is touched.",
        ],
        "safety_boundary": SAFETY_BOUNDARY,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "packet_path": str(output),
        "manifest_path": str(manifest_path),
        "signal_id": payload.get("signal_id"),
        "manual_approval_required": True,
        "remote_write_executed": False,
        "order_execution_allowed": False,
    }


def render_manual_signal_write_commands() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            "echo \"Oracle preview signal manual write packet\"",
            "echo \"This file does not upload anything when executed as-is.\"",
            "echo \"No systemd operations. No live bot changes. No broker API. No orders. order_execution_allowed=false.\"",
            "",
            "ORACLE_USER='<oracle-user>'",
            "ORACLE_HOST='<oracle-host>'",
            "ORACLE_OUTBOX_DIR='<oracle-outbox-dir>'",
            "LOCAL_PREVIEW_SIGNAL_PATH='./us_trader_preview_signal.json'",
            "REMOTE_PREVIEW_SIGNAL_NAME='us_trader_preview_signal.json'",
            "",
            "test -f \"${LOCAL_PREVIEW_SIGNAL_PATH}\"",
            "printf '%s\\n' \"Manual approval is required before any upload command is copied.\"",
            "printf '%s\\n' \"Remote outbox placeholder: ${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}\"",
            "",
            "# 수동 승인 후에만 아래 scp 명령을 검토하세요.",
            "# scp \"${LOCAL_PREVIEW_SIGNAL_PATH}\" \"${ORACLE_USER}@${ORACLE_HOST}:${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}\"",
            "# 수동 승인 후에만 아래 rsync 명령을 검토하세요.",
            "# rsync --checksum --dry-run \"${LOCAL_PREVIEW_SIGNAL_PATH}\" \"${ORACLE_USER}@${ORACLE_HOST}:${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}\"",
            "",
        ]
    )


def render_post_signal_write_verify_commands() -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "",
            "echo \"Oracle preview signal post-write read-only verification\"",
            "echo \"Run these on Oracle after a human manually uploads the preview signal.\"",
            "echo \"No touch/rm/mv/chmod/chown/systemd operations. No live bot changes. No orders.\"",
            "echo \"order_execution_allowed=false remains mandatory.\"",
            "",
            "ORACLE_OUTBOX_DIR='<oracle-outbox-dir>'",
            "REMOTE_PREVIEW_SIGNAL_NAME='us_trader_preview_signal.json'",
            "REMOTE_PREVIEW_SIGNAL_PATH=\"${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}\"",
            "",
            "test -f \"${REMOTE_PREVIEW_SIGNAL_PATH}\"",
            "ls -la \"${ORACLE_OUTBOX_DIR}\"",
            "stat \"${REMOTE_PREVIEW_SIGNAL_PATH}\"",
            "python3 -m json.tool \"${REMOTE_PREVIEW_SIGNAL_PATH}\" >/dev/null",
            "printf '%s\\n' \"Read-only verification complete. Do not modify services or live bot files.\"",
            "",
        ]
    )


def build_result_template(signal: dict[str, Any], signal_path: Path) -> dict[str, Any]:
    return {
        "result_status": "incomplete",
        "manual_operator": "<manual-operator>",
        "written_at": None,
        "oracle_target": {
            "host": "<oracle-host>",
            "user": "<oracle-user>",
            "outbox_dir": "<oracle-outbox-dir>",
        },
        "signal_file": {
            "filename": "us_trader_preview_signal.json",
            "signal_id": signal.get("signal_id", "<signal-id>"),
            "sha256": sha256_file(signal_path),
            "size_bytes": signal_path.stat().st_size,
        },
        "observations": {
            "file_uploaded_manually": False,
            "file_exists_in_outbox": False,
            "file_readable": False,
            "file_json_valid": False,
            "post_write_verify_readonly_only": True,
        },
        "safety": {
            "systemd_changed": False,
            "live_bot_modified": False,
            "penny_stock_bot_modified": False,
            "secrets_exposed": False,
            "broker_api_called": False,
            "order_execution_allowed": False,
        },
        "notes": ["Template only. Do not record secret values."],
        "next_step_requested": "mac_pull_actual_preview_signal_rehearsal",
        "safety_boundary": SAFETY_BOUNDARY,
    }


def run_signal_verify(signal: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "verify_preview_signal_file.py"), "--signal", str(signal)],
        check=False,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_verify(output: Path) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(PREVIEW_DIR / "verify_manual_signal_write_packet.py"), "--packet", str(output)],
        check=False,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def reset_output_dir(output: Path, *, force: bool) -> None:
    if output.exists():
        if not force:
            raise FileExistsError(f"output already exists, pass --force: {output}")
        shutil.rmtree(output)


def file_entry(path: Path, relative_path: Path) -> dict[str, Any]:
    return {"path": str(relative_path), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
