#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "examples" / "oracle_preview_signal_write"
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_signal_write" / "pull_rehearsal_go_no_go_decision.json"
NEXT_PHASE = "Phase 24S Mac pull actual preview signal rehearsal"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Decide GO/NO_GO for Mac pull rehearsal after preview signal write.")
    parser.add_argument("--result", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        decision = decide(Path(args.result))
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(decision, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "status": "ok",
            "decision_path": str(output),
            "decision": decision["decision"],
            "next_phase_allowed": decision["next_phase_allowed"],
            "order_execution_allowed": False,
        }
    except Exception as exc:
        result = {"status": "failed", "error": str(exc), "order_execution_allowed": False}
        print_json(result, pretty=args.pretty)
        return 1
    print_json(result, pretty=args.pretty)
    return 0


def decide(result_path: Path) -> dict[str, Any]:
    payload = json.loads(result_path.expanduser().read_text(encoding="utf-8"))
    validation = run_validation(result_path)
    observations = payload.get("observations", {})
    safety = payload.get("safety", {})
    reasons: list[str] = []
    warnings: list[str] = []

    if validation.get("validation_status") != "passed":
        reasons.append(f"validation_status={validation.get('validation_status')}")
    if payload.get("result_status") not in {"passed", "warning"}:
        reasons.append(f"result_status={payload.get('result_status')}")
    if payload.get("result_status") == "warning":
        warnings.append("result_status=warning requires extra manual acknowledgement before Mac pull rehearsal")
    for key in [
        "file_uploaded_manually",
        "file_exists_in_outbox",
        "file_readable",
        "file_json_valid",
        "post_write_verify_readonly_only",
    ]:
        if observations.get(key) is not True:
            reasons.append(f"{key} must be true")
    for key in [
        "systemd_changed",
        "live_bot_modified",
        "penny_stock_bot_modified",
        "secrets_exposed",
        "broker_api_called",
        "order_execution_allowed",
    ]:
        if safety.get(key) is not False:
            reasons.append(f"{key} must be false")
    if validation.get("secret_hits"):
        reasons.append("secret marker detected")
    if validation.get("order_true_hits"):
        reasons.append("order_execution_allowed true marker detected")

    decision = "NO_GO" if reasons else "GO"
    return {
        "decision": decision,
        "next_phase_allowed": decision == "GO",
        "next_phase": NEXT_PHASE,
        "decision_scope": "Allows only Mac pull rehearsal, not live bot patching or order execution.",
        "reasons": reasons,
        "warnings": warnings,
        "validation": validation,
        "required_manual_acknowledgements": [
            "GO is not live bot patch approval.",
            "GO does not permit broker API connection or order execution.",
            "GO does not permit systemd changes or live bot modification.",
            "The next phase is Mac pull actual preview signal rehearsal only.",
        ],
        "systemd_changed": False,
        "live_bot_modified": False,
        "penny_stock_bot_modified": False,
        "broker_api_called": False,
        "order_execution_allowed": False,
        "safety_boundary": SAFETY_BOUNDARY,
    }


def run_validation(result_path: Path) -> dict[str, Any]:
    script = PREVIEW_DIR / "verify_preview_signal_write_result.py"
    result = subprocess.run(
        [sys.executable, str(script), "--result", str(result_path.expanduser().resolve())],
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"validation did not return JSON: {result.stdout[:200]}") from exc


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
