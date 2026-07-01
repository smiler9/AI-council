#!/usr/bin/env bash
# Mac pull example for manual review only.
# The Mac pulls Oracle outbox JSON files read-only after outbox export is approved.
# Do not delete remote files. Start with dry-run/listing only.
# No broker API is called. No real order is created or transmitted.
# order_execution_allowed=false

set -euo pipefail

echo "Dry-run concept only. No SSH/SCP/rsync command is executed by this template."
echo "ORACLE_HOST=<oracle-host>"
echo "ORACLE_USER=<oracle-user>"
echo "ORACLE_OUTBOX=<oracle-outbox-dir>"

# Example concept only:
# rsync --dry-run -av --ignore-existing -e "ssh -i <path-to-private-key>" \
#   <oracle-user>@<oracle-host>:<oracle-outbox-dir>/ ./tmp/oracle_pulled_signals/
