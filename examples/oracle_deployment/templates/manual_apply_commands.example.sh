#!/usr/bin/env bash
# Manual apply command notes for review only.
# This script is not intended to be run as-is.
# AI Council does not copy files to Oracle and does not operate systemd.
# Every command below is intentionally documented as echo/comment guidance.

set -euo pipefail

echo "Manual approval is required before any Oracle file copy."
echo "Use placeholders only in docs: ORACLE_HOST=<oracle-host> ORACLE_USER=<oracle-user> ORACLE_TRADING_DIR=<oracle-trading-dir>"
echo "First run local verification:"
echo "  scripts/run_oracle_sidecar_smoke.sh"
echo "  scripts/run_oracle_export_hook_preflight.sh"
echo "  scripts/run_oracle_staging_rehearsal.sh"
echo "  scripts/build_oracle_signal_export_bundle.sh"
echo "  scripts/verify_oracle_signal_export_bundle.sh"
echo "  scripts/run_oracle_readiness_check_dryrun.sh"
echo "Manual copy, service unit review, and any later service operation require a separate approval record."
echo "Do not connect AI Council to place_order, check_exits, or force_close_all."
echo "order_execution_allowed=false"
