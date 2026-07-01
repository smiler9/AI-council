#!/usr/bin/env bash
set -euo pipefail

echo "Manual read-only verification example after a future approved directory creation."

# test -d <oracle-trading-dir>/ai_council_outbox
# test -d <oracle-trading-dir>/ai_council_processed
# test -d <oracle-trading-dir>/ai_council_failed
# test -d <oracle-trading-dir>/ai_council_state
# ls -ld <oracle-trading-dir>/ai_council_outbox <oracle-trading-dir>/ai_council_processed <oracle-trading-dir>/ai_council_failed <oracle-trading-dir>/ai_council_state

echo "No remote files are deleted, moved, or modified by this template."
echo "order_execution_allowed=false"
