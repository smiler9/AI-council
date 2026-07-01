#!/usr/bin/env bash
set -euo pipefail

echo "Oracle outbox manual creation command candidates"
echo "Manual review packet only. GO is not deployment approval."
echo "No systemd operations. No live bot changes. No broker API. No orders. order_execution_allowed=false."

ORACLE_TRADING_DIR='<oracle-trading-dir>'
AI_COUNCIL_OUTBOX_DIR='<oracle-trading-dir>/ai_council_outbox'
AI_COUNCIL_PROCESSED_DIR='<oracle-trading-dir>/ai_council_processed'
AI_COUNCIL_FAILED_DIR='<oracle-trading-dir>/ai_council_failed'
AI_COUNCIL_STATE_DIR='<oracle-trading-dir>/ai_council_state'

echo "Read this file on Oracle, then manually copy only approved commented commands."
test -d "${ORACLE_TRADING_DIR}"
ls -la "${ORACLE_TRADING_DIR}"
# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_OUTBOX_DIR}"
# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_PROCESSED_DIR}"
# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_FAILED_DIR}"
# 수동 승인 후 주석 해제: mkdir -p "${AI_COUNCIL_STATE_DIR}"
# 수동 승인 후 주석 해제 필요 시만: chmod 750 "${AI_COUNCIL_OUTBOX_DIR}"
# chown is not recommended and remains prohibited unless separately approved.
echo "This file does not create directories when executed as-is."
