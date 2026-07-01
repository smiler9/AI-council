#!/usr/bin/env bash
set -euo pipefail

echo "Oracle outbox post-creation read-only verification"
echo "No sample signal file is created. No systemd operations. order_execution_allowed=false."

ORACLE_TRADING_DIR='<oracle-trading-dir>'
AI_COUNCIL_OUTBOX_DIR='<oracle-trading-dir>/ai_council_outbox'
AI_COUNCIL_PROCESSED_DIR='<oracle-trading-dir>/ai_council_processed'
AI_COUNCIL_FAILED_DIR='<oracle-trading-dir>/ai_council_failed'
AI_COUNCIL_STATE_DIR='<oracle-trading-dir>/ai_council_state'

test -d "${AI_COUNCIL_OUTBOX_DIR}"
test -d "${AI_COUNCIL_PROCESSED_DIR}"
test -d "${AI_COUNCIL_FAILED_DIR}"
test -d "${AI_COUNCIL_STATE_DIR}"
ls -la "${AI_COUNCIL_OUTBOX_DIR}"
ls -la "${AI_COUNCIL_PROCESSED_DIR}"
ls -la "${AI_COUNCIL_FAILED_DIR}"
ls -la "${AI_COUNCIL_STATE_DIR}"
stat "${AI_COUNCIL_OUTBOX_DIR}"
df -h "${ORACLE_TRADING_DIR}"
