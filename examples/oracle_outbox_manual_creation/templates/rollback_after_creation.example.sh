#!/usr/bin/env bash
set -euo pipefail

echo "Oracle outbox rollback notes after manual creation"
echo "No systemd operations. No live bot changes. No broker API. No orders. order_execution_allowed=false."
echo "Rollback defaults to stopping further rollout and preserving outbox files."
echo "Remote deletion/move commands are comments only and require separate approval."

ORACLE_TRADING_DIR='<oracle-trading-dir>'
AI_COUNCIL_OUTBOX_DIR='<oracle-trading-dir>/ai_council_outbox'
AI_COUNCIL_PROCESSED_DIR='<oracle-trading-dir>/ai_council_processed'
AI_COUNCIL_FAILED_DIR='<oracle-trading-dir>/ai_council_failed'
AI_COUNCIL_STATE_DIR='<oracle-trading-dir>/ai_council_state'

# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_OUTBOX_DIR}"
# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_PROCESSED_DIR}"
# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_FAILED_DIR}"
# 별도 승인 전 실행 금지: rm -r "${AI_COUNCIL_STATE_DIR}"
# 별도 승인 전 실행 금지: mv "${AI_COUNCIL_OUTBOX_DIR}" "<approved-archive-dir>"
echo "No active rm/rmdir/mv command is executed by this file."
