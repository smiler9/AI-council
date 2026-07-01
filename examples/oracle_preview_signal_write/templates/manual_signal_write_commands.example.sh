#!/usr/bin/env bash
set -euo pipefail

echo "Oracle preview signal manual write packet"
echo "This file does not upload anything when executed as-is."
echo "No systemd operations. No live bot changes. No broker API. No orders. order_execution_allowed=false."

ORACLE_USER='<oracle-user>'
ORACLE_HOST='<oracle-host>'
ORACLE_OUTBOX_DIR='<oracle-outbox-dir>'
LOCAL_PREVIEW_SIGNAL_PATH='./us_trader_preview_signal.json'
REMOTE_PREVIEW_SIGNAL_NAME='us_trader_preview_signal.json'

test -f "${LOCAL_PREVIEW_SIGNAL_PATH}"
printf '%s\n' "Manual approval is required before any upload command is copied."
printf '%s\n' "Remote outbox placeholder: ${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}"

# 수동 승인 후에만 아래 scp 명령을 검토하세요.
# scp "${LOCAL_PREVIEW_SIGNAL_PATH}" "${ORACLE_USER}@${ORACLE_HOST}:${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}"
# 수동 승인 후에만 아래 rsync 명령을 검토하세요.
# rsync --checksum --dry-run "${LOCAL_PREVIEW_SIGNAL_PATH}" "${ORACLE_USER}@${ORACLE_HOST}:${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}"
