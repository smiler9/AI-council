#!/usr/bin/env bash
set -euo pipefail

echo "Outbox apply commands example. This file is documentation, not an automatic deployment script."
echo "Manual approval is required before any Oracle change."
echo "No broker API connection. No real order execution. order_execution_allowed=false."

echo "Approved placeholder paths:"
echo "OUTBOX=<oracle-trading-dir>/ai_council_outbox/"
echo "PROCESSED=<oracle-trading-dir>/ai_council_processed/"
echo "FAILED=<oracle-trading-dir>/ai_council_failed/"
echo "STATE=<oracle-trading-dir>/ai_council_state/"
echo "LOG=<oracle-trading-dir>/logs/ai_council_export.log"

echo "The following commands are intentionally comments only:"
# Manual approval required before creating any directory:
# mkdir -p <oracle-trading-dir>/ai_council_outbox/
# mkdir -p <oracle-trading-dir>/ai_council_processed/
# mkdir -p <oracle-trading-dir>/ai_council_failed/
# mkdir -p <oracle-trading-dir>/ai_council_state/

# Manual approval required before changing any permission:
# chmod 750 <oracle-trading-dir>/ai_council_outbox/

# Production service operations are not part of Phase 24K:
# systemctl status --no-pager <service-name>

echo "Do not start, stop, restart, reload, or modify Oracle production services in Phase 24K."
