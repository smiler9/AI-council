#!/usr/bin/env bash
set -euo pipefail

echo "Manual Oracle outbox directory creation example."
echo "All remote write commands are intentionally commented out."
echo "Run only after separate human approval on Oracle."

# 수동 승인 후에만 사람이 복사해서 실행할 수 있는 예시입니다.
# mkdir -p <oracle-trading-dir>/ai_council_outbox
# mkdir -p <oracle-trading-dir>/ai_council_processed
# mkdir -p <oracle-trading-dir>/ai_council_failed
# mkdir -p <oracle-trading-dir>/ai_council_state

echo "This file does not create directories by itself."
echo "No systemd service is touched. No live bot file is modified. No real order is executed."
echo "order_execution_allowed=false"
