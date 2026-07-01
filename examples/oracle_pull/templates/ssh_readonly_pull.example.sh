#!/usr/bin/env bash
set -euo pipefail

echo "Read-only Oracle outbox listing example. Review before running manually."
echo "No remote files are deleted, moved, or changed."

# ssh -i <path-to-private-key> <oracle-user>@<oracle-host> \
#   "ls -la <oracle-outbox-dir> && find <oracle-outbox-dir> -maxdepth 1 -type f -name '*.json' -print"

echo "Actual command is intentionally commented out."
echo "order_execution_allowed=false"
