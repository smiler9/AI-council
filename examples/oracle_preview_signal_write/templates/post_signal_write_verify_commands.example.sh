#!/usr/bin/env bash
set -euo pipefail

echo "Oracle preview signal post-write read-only verification"
echo "Run these on Oracle after a human manually uploads the preview signal."
echo "No touch/rm/mv/chmod/chown/systemd operations. No live bot changes. No orders."
echo "order_execution_allowed=false remains mandatory."

ORACLE_OUTBOX_DIR='<oracle-outbox-dir>'
REMOTE_PREVIEW_SIGNAL_NAME='us_trader_preview_signal.json'
REMOTE_PREVIEW_SIGNAL_PATH="${ORACLE_OUTBOX_DIR}/${REMOTE_PREVIEW_SIGNAL_NAME}"

test -f "${REMOTE_PREVIEW_SIGNAL_PATH}"
ls -la "${ORACLE_OUTBOX_DIR}"
stat "${REMOTE_PREVIEW_SIGNAL_PATH}"
python3 -m json.tool "${REMOTE_PREVIEW_SIGNAL_PATH}" >/dev/null
printf '%s\n' "Read-only verification complete. Do not modify services or live bot files."
