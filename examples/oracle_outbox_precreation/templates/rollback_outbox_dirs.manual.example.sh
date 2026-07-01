#!/usr/bin/env bash
set -euo pipefail

echo "Manual rollback planning example."
echo "Default rollback is to stop Mac pull and preserve outbox files for audit."

# Remote deletion is prohibited by default.
# Do not run deletion or movement commands unless a separate post-audit approval exists.
# rm -r <oracle-trading-dir>/ai_council_outbox
# mv <oracle-trading-dir>/ai_council_outbox <approved-archive-dir>

echo "This template does not delete or move remote files."
echo "No systemd service is touched. No live bot file is modified."
echo "order_execution_allowed=false"
