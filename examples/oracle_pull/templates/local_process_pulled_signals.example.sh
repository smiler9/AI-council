#!/usr/bin/env bash
set -euo pipefail

cd ~/AI-council

./.venv/bin/python examples/oracle_pull/process_pulled_signals.py \
  --inbox tmp/oracle_pull/inbox \
  --state tmp/oracle_pull/state.json \
  --mode preview \
  --pretty

echo "This only calls AI Council normalize-preview. It does not execute trades."
echo "order_execution_allowed=false"
