#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "examples" / "oracle_staging" / "fixtures" / "minimal_penny_stock_bot.py"
TARGET_FUNCTIONS = ("analyze_signals", "scan_and_enter", "place_order", "check_exits", "force_close_all")
UNSAFE_FUNCTIONS = ("place_order", "check_exits", "force_close_all")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only static analyzer for a US Trader bot file.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Path to penny_stock_bot.py or staging copy.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    try:
        result = analyze_bot(Path(args.source))
    except Exception as exc:
        result = {
            "status": "failed",
            "detail": str(exc),
            "order_execution_allowed": False,
        }
        print_json(result, pretty=args.pretty)
        return 1

    print_json(result, pretty=args.pretty)
    return 0


def analyze_bot(source_path: Path) -> dict[str, Any]:
    path = source_path.expanduser()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    functions = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    line_count = len(source.splitlines())
    function_ranges = {
        name: {
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
        }
        for name, node in functions.items()
        if name in TARGET_FUNCTIONS
    }
    functions_found = {name: name in functions for name in TARGET_FUNCTIONS}
    safe_candidates = build_safe_candidates(source, functions, function_ranges)
    unsafe_points = [
        {
            "function": name,
            "reason": "order/exit execution path; do not insert export hooks here",
            **function_ranges.get(name, {}),
        }
        for name in UNSAFE_FUNCTIONS
        if name in functions
    ]
    return {
        "status": "ok",
        "file_analyzed": str(path),
        "line_count": line_count,
        "functions_found": functions_found,
        "function_ranges": function_ranges,
        "safe_insertion_candidates": safe_candidates,
        "unsafe_insertion_points": unsafe_points,
        "import_executed": False,
        "secret_values_read": False,
        "order_execution_allowed": False,
    }


def build_safe_candidates(source: str, functions: dict[str, ast.AST], ranges: dict[str, dict]) -> list[dict[str, Any]]:
    candidates = []
    lines = source.splitlines()
    scan = functions.get("scan_and_enter")
    if scan:
        start = scan.lineno
        end = getattr(scan, "end_lineno", scan.lineno)
        scan_text = "\n".join(lines[start - 1 : end])
        if 'entry = {"ticker"' in scan_text or "entry = {'ticker'" in scan_text:
            candidates.append(
                {
                    "function": "scan_and_enter",
                    "location_hint": "after candidate entry creation",
                    "reason": "candidate signal appears before order execution",
                    **ranges.get("scan_and_enter", {}),
                }
            )
        elif "candidate" in scan_text and "place_order" in scan_text:
            candidates.append(
                {
                    "function": "scan_and_enter",
                    "location_hint": "before place_order call",
                    "reason": "candidate loop appears before order execution",
                    **ranges.get("scan_and_enter", {}),
                }
            )
    if "analyze_signals" in functions:
        candidates.append(
            {
                "function": "analyze_signals",
                "location_hint": "caller should export returned signal dictionary",
                "reason": "function returns signal metadata but should not call sidecar directly",
                **ranges.get("analyze_signals", {}),
            }
        )
    return candidates


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
