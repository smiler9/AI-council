#!/usr/bin/env bash
set -euo pipefail

echo "Oracle outbox manual creation command candidates."
echo "All write commands are intentionally commented out."
echo "Manual approval is required before copying any command to Oracle."

# 수동 승인 후 주석 해제 후보입니다. 이 파일 자체는 원격 디렉터리를 만들지 않습니다.
# mkdir -p <oracle-trading-dir>/ai_council_outbox
# mkdir -p <oracle-trading-dir>/ai_council_processed
# mkdir -p <oracle-trading-dir>/ai_council_failed
# mkdir -p <oracle-trading-dir>/ai_council_state

# 권한 변경은 기본 보류입니다. 별도 승인 없이 실행하지 않습니다.
# chmod 750 <oracle-trading-dir>/ai_council_outbox

echo "No systemd operation. No live bot modification. No real order."
echo "order_execution_allowed=false"
