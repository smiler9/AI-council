#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


DEFAULT_BASE_URL = os.getenv("AI_COUNCIL_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("AI_COUNCIL_TIMEOUT_SECONDS", "30"))
DIAGNOSTIC_PATHS = [
    "/health",
    "/api/diagnostics/summary",
    "/api/diagnostics/security",
    "/api/diagnostics/providers",
    "/api/diagnostics/runtime",
    "/api/diagnostics/e2e-status",
]


@dataclass
class DiagnosticFailure(Exception):
    path: str
    detail: str
    http_status: int | None = None
    response_snippet: str | None = None


def main() -> int:
    args = parse_args()
    try:
        result = run_diagnostics(args.base_url, args.timeout)
    except DiagnosticFailure as exc:
        result = {
            "status": "failed",
            "failed_path": exc.path,
            "detail": exc.detail,
            "http_status": exc.http_status,
            "response_snippet": exc.response_snippet,
            "order_execution_allowed": False,
        }
        print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI Council read-only diagnostics.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="AI Council backend base URL")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="HTTP timeout seconds")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return parser.parse_args()


def run_diagnostics(base_url: str, timeout_seconds: float) -> dict:
    base_url = base_url.rstrip("/")
    checks = {}
    for path in DIAGNOSTIC_PATHS:
        payload = request_json(f"{base_url}{path}", path, timeout_seconds)
        checks[path] = payload
        ensure_order_execution_false(payload, path)
    summary = checks["/api/diagnostics/summary"]
    security = checks["/api/diagnostics/security"]
    providers = checks["/api/diagnostics/providers"]
    runtime = checks["/api/diagnostics/runtime"]
    e2e_status = checks["/api/diagnostics/e2e-status"]
    return {
        "status": "passed",
        "base_url": base_url,
        "checks_total": len(DIAGNOSTIC_PATHS),
        "checks_passed": len(DIAGNOSTIC_PATHS),
        "overall_status": summary.get("status"),
        "security_status": security.get("status"),
        "provider_status": providers.get("status"),
        "runtime_status": runtime.get("status"),
        "e2e_script_available": e2e_status.get("full_e2e_script_available"),
        "safety": {
            "order_execution_allowed_all_false": True,
            "broker_api_connected": security.get("broker_api_connected") is True,
            "secret_values_exposed": security.get("secret_values_exposed") is True,
            "simulation_only_confirmed": summary.get("safety", {}).get("simulation_only_confirmed") is True,
        },
        "diagnostics": checks,
    }


def request_json(url: str, path: str, timeout_seconds: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise DiagnosticFailure(path, "HTTP request failed", exc.code, body[:800]) from exc
    except urllib.error.URLError as exc:
        raise DiagnosticFailure(path, f"Connection failed: {exc.reason}") from exc


def ensure_order_execution_false(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if value.get("order_execution_allowed") is not None and value["order_execution_allowed"] is not False:
            raise DiagnosticFailure(path, "order_execution_allowed must remain false")
        for item in value.values():
            ensure_order_execution_false(item, path)
    elif isinstance(value, list):
        for item in value:
            ensure_order_execution_false(item, path)


if __name__ == "__main__":
    sys.exit(main())
