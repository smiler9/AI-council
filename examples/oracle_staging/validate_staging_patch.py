#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


UNSAFE_FUNCTIONS = ("place_order", "check_exits", "force_close_all")
FORBIDDEN_TERMS = (
    "BrokerClient",
    "OrderRequest",
    "TradingClient",
    "tradeapi.REST",
    "alpaca_trade_api",
    "ib_insync",
    "kis_order",
)
SECRET_MARKERS = ("BEGIN PRIVATE KEY", "ssh-key-2026", "API_SECRET", "ACCESS_TOKEN")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a staging patched preview file without executing it.")
    parser.add_argument("--source", required=True, help="Path to patched preview file.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    result = validate_patch(Path(args.source))
    print_json(result, pretty=args.pretty)
    return 0 if result["status"] == "ok" else 1


def validate_patch(source_path: Path) -> dict[str, Any]:
    path = source_path.expanduser()
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    function_ranges = function_line_ranges(tree)
    hook_lines = lines_with(source, ("export_ai_council_signal(", "build_ai_council_signal("))
    unsafe_hits = []
    for function_name in UNSAFE_FUNCTIONS:
        line_range = function_ranges.get(function_name)
        if not line_range:
            continue
        start, end = line_range
        for line_no in hook_lines:
            if start <= line_no <= end:
                unsafe_hits.append({"function": function_name, "line": line_no})
    has_exporter_import = "ai_council_signal_exporter_module" in source
    has_export_call = "export_ai_council_signal(" in source
    has_order_false = "order_execution_allowed=false" in source or '"order_execution_allowed": false' in source
    has_review_marker = "review_only=true" in source or '"review_only": true' in source
    forbidden_hits = [term for term in FORBIDDEN_TERMS if term in source]
    secret_hits = [term for term in SECRET_MARKERS if term in source]
    status = "ok"
    errors = []
    if not has_exporter_import:
        errors.append("missing exporter module import")
    if not has_export_call:
        errors.append("missing export_ai_council_signal call")
    if unsafe_hits:
        errors.append("export hook appears inside unsafe function")
    if not has_order_false:
        errors.append("missing order_execution_allowed=false marker")
    if not has_review_marker:
        errors.append("missing review_only marker")
    if forbidden_hits:
        errors.append("forbidden broker/order client term found")
    if secret_hits:
        errors.append("secret/private key marker found")
    if errors:
        status = "failed"
    return {
        "status": status,
        "file_validated": str(path),
        "has_exporter_import": has_exporter_import,
        "has_export_call": has_export_call,
        "unsafe_hook_hits": unsafe_hits,
        "forbidden_hits": forbidden_hits,
        "secret_hits": secret_hits,
        "errors": errors,
        "order_execution_allowed": False,
        "review_only": True,
    }


def function_line_ranges(tree: ast.AST) -> dict[str, tuple[int, int]]:
    ranges = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ranges[node.name] = (node.lineno, getattr(node, "end_lineno", node.lineno))
    return ranges


def lines_with(source: str, needles: tuple[str, ...]) -> list[int]:
    matches = []
    for line_no, line in enumerate(source.splitlines(), start=1):
        if any(needle in line for needle in needles):
            matches.append(line_no)
    return matches


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
