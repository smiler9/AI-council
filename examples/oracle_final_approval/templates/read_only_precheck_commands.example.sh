#!/usr/bin/env bash
set -euo pipefail

echo "Oracle read-only precheck command examples."
echo "Replace placeholders manually after approval. No write command is active."

# test -d <oracle-trading-dir>
# test -f <oracle-trading-dir>/penny_stock_bot.py
# test -f <oracle-trading-dir>/server.py
# test -d <oracle-trading-dir>/.secrets
# ls -ld <oracle-trading-dir>
# stat <oracle-trading-dir>
# df -h <oracle-trading-dir>
# free -h
# python3 --version
# systemctl status --no-pager <service-name>

echo "Do not cat secret files. Do not run start/stop/restart/reload."
echo "order_execution_allowed=false"
