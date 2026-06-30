#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python3 examples/integration/run_webhook_smoke_test.py
