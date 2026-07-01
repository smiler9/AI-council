#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "tmp" / "oracle_preview_signal_write" / "us_trader_preview_signal.json"
SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local Oracle preview signal JSON file.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    output.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    result = {
        "status": "ok",
        "signal_path": str(output),
        "signal_id": payload["signal_id"],
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": False,
    }
    print_json(result, pretty=args.pretty)
    return 0


def build_payload() -> dict:
    now = datetime.now(timezone.utc)
    signal_id = f"manual_preview_{now.strftime('%Y%m%dT%H%M%SZ')}"
    return {
        "source": "us_trader_oracle_manual_preview",
        "signal_id": signal_id,
        "symbol": "TESTA",
        "signal": "manual_preview_signal",
        "action": "buy",
        "price": 0.82,
        "volume": 12500000,
        "timestamp": now.isoformat(),
        "indicators": {
            "relative_volume": 5.2,
            "rsi": 68,
        },
        "risk_context": {
            "spread_pct": 2.5,
            "premarket": False,
            "manual_preview": True,
        },
        "review_only": True,
        "simulation_only": True,
        "order_execution_allowed": False,
        "notes": [
            "Manual preview only. Raw action is review context, not an order.",
            "This TESTA payload is not a real ticker recommendation.",
            SAFETY_BOUNDARY,
        ],
    }


def print_json(payload: dict, *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
