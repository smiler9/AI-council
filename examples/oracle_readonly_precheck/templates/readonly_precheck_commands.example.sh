#!/usr/bin/env bash
set -euo pipefail

echo "Oracle read-only precheck commands."
echo "Run manually only after replacing placeholders. Do not print secrets."

hostname
whoami
pwd
uname -a
date
df -h
free -h
python3 --version
which python3
ls -la <oracle-trading-dir>
test -f <oracle-trading-dir>/penny_stock_bot.py
test -f <oracle-trading-dir>/server.py
test -d <oracle-trading-dir>/.secrets
ps aux | grep -i trader
ps aux | grep -i penny
ps aux | grep -i python
screen -ls
tmux ls
crontab -l
systemctl status --no-pager <service-name>

echo "Do not run mkdir, touch, cp, mv, rm, chmod, chown, service changes, trading scripts, or secret file cat commands."
echo "order_execution_allowed=false"
