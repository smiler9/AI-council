#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any

from analyze_us_trader_bot import analyze_bot


IMPORT_BLOCK = [
    "",
    "# AI Council export hook preview: review-only outbox export. No broker API calls.",
    "from ai_council_signal_exporter_module import build_ai_council_signal, export_ai_council_signal",
    "",
]

HOOK_BLOCK = [
    "            # AI Council export hook preview: export candidate before any order path.",
    "            # order_execution_allowed=false; review_only=true; AI Council result is not used for orders.",
    "            try:",
    "                ai_council_payload = build_ai_council_signal(",
    "                    symbol=entry[\"ticker\"],",
    "                    strategy_signal=\"+\".join(entry.get(\"signals\", [])) or \"scanner_candidate\",",
    "                    raw_side=\"buy\",",
    "                    price=entry.get(\"current_price\"),",
    "                    volume=None,",
    "                    timeframe=\"5m\",",
    "                    indicators={",
    "                        \"rsi\": entry.get(\"rsi\"),",
    "                        \"volume_ratio\": entry.get(\"volume_ratio\"),",
    "                        \"gap_pct\": entry.get(\"gap_pct\"),",
    "                        \"recent_momentum_pct\": entry.get(\"recent_momentum_pct\"),",
    "                        \"signal_score\": entry.get(\"signal_score\"),",
    "                        \"vwap\": entry.get(\"vwap\"),",
    "                    },",
    "                    risk_context={",
    "                        \"source_function\": \"scan_and_enter\",",
    "                        \"breakout_ok\": entry.get(\"breakout_ok\"),",
    "                    },",
    "                    news_headlines=[],",
    "                    notes=\"Review-only staging export before live order boundary.\",",
    "                )",
    "                export_ai_council_signal(ai_council_payload, AI_COUNCIL_OUTBOX_DIR)",
    "            except Exception as export_exc:",
    "                print(f\"[AI Council export skipped] {entry.get('ticker')}: {export_exc}\")",
]
UNSAFE_FUNCTIONS = ("place_order", "check_exits", "force_close_all")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a local patch preview for an AI Council export hook.")
    parser.add_argument("--source", required=True, help="Path to staging penny_stock_bot.py copy.")
    parser.add_argument("--output", help="Optional patched preview output path.")
    parser.add_argument("--diff-only", action="store_true", help="Only generate unified diff in JSON output.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = generate_preview(Path(args.source), Path(args.output) if args.output else None)
    except Exception as exc:
        result = {
            "status": "failed",
            "detail": str(exc),
            "patched_preview_written": False,
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1

    if args.diff_only:
        result["patched_preview_written"] = False
    print_json(result, pretty=args.pretty)
    return 0


def generate_preview(source_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    source = source_path.expanduser()
    original_lines = source.read_text(encoding="utf-8").splitlines()
    analysis = analyze_bot(source)
    safe = [
        item
        for item in analysis.get("safe_insertion_candidates", [])
        if item.get("function") == "scan_and_enter"
    ]
    if not safe:
        raise RuntimeError("no safe scan_and_enter insertion point found")
    import_at = find_import_insertion_index(original_lines)
    hook_at = find_hook_insertion_index(original_lines)
    if hook_at is None:
        raise RuntimeError("candidate entry creation line not found")
    patched = list(original_lines)
    patched[import_at:import_at] = IMPORT_BLOCK
    adjusted_hook_at = hook_at + len(IMPORT_BLOCK)
    patched[adjusted_hook_at:adjusted_hook_at] = HOOK_BLOCK
    diff = "\n".join(
        difflib.unified_diff(
            original_lines,
            patched,
            fromfile=str(source),
            tofile=str(output_path or source.with_suffix(".patched.preview.py")),
            lineterm="",
        )
    )
    if not diff:
        raise RuntimeError("patch preview diff is empty")
    written = False
    if output_path is not None:
        output = output_path.expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(patched) + "\n", encoding="utf-8")
        written = True
    return {
        "status": "ok",
        "source": str(source),
        "safe_insertion_function": "scan_and_enter",
        "unsafe_functions_avoided": list(UNSAFE_FUNCTIONS),
        "hook_insert_line": hook_at + 1,
        "diff": diff,
        "patched_preview_path": str(output_path) if output_path else None,
        "patched_preview_written": written,
        "order_execution_allowed": False,
        "review_only": True,
    }


def find_import_insertion_index(lines: list[str]) -> int:
    last_import = -1
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import = index
        elif last_import >= 0 and stripped and not stripped.startswith("#"):
            break
    return last_import + 1 if last_import >= 0 else 0


def find_hook_insertion_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("entry = ") and '"ticker"' in stripped:
            return index + 1
    return None


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
