#!/usr/bin/env bash
set -euo pipefail

echo "Rsync dry-run example for Oracle outbox JSON files."
echo "Do not use source-removal options. Do not delete or move remote files."

# rsync --dry-run -av \
#   -e "ssh -i <path-to-private-key>" \
#   <oracle-user>@<oracle-host>:<oracle-outbox-dir>/*.json \
#   tmp/oracle_pull/inbox/

echo "Actual command is intentionally commented out."
echo "order_execution_allowed=false"
