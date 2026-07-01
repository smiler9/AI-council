# Oracle Outbox Creation Result Criteria

## Passed

- `result_status=passed`
- outbox, processed, failed, state directories exist
- directories are readable
- expected user can write to the directories
- disk space is acceptable
- post-creation verification used read-only commands only
- `systemd_changed=false`
- `live_bot_modified=false`
- `penny_stock_bot_modified=false`
- `secrets_exposed=false`
- `broker_api_called=false`
- `order_execution_allowed=false`

## Warning

- Ownership is not confirmed but read/write checks passed
- `result_status=warning`
- Notes require manual review before the next rehearsal

## Failed

- Required directory is missing
- Directory permission is insufficient
- Disk space is not acceptable
- systemd changed
- live bot or `penny_stock_bot.py` changed
- secret was exposed
- broker API was called
- `order_execution_allowed` true 상태

## GO/NO-GO

GO only allows moving to preview signal file write rehearsal. It is not live bot patch approval, not broker connection approval, and not order execution approval.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
