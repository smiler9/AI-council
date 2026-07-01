# Oracle Precheck Intake Go/No-Go Criteria

## GO 조건

- `validation_status=passed`
- `result_status=passed` 또는 `warning`
- `remote_write_executed=false`
- `systemd_changed=false`
- `live_bot_modified=false`
- `secrets_exposed=false`
- `order_execution_allowed=false`
- `trading_dir_exists=true`
- `penny_stock_bot_exists=true`
- `server_py_exists=true`
- `python3_available=true`
- `disk_space_ok=true`
- active services가 관찰됐지만 조작되지 않음

GO는 outbox 수동 생성 검토 단계로 넘어갈 수 있다는 뜻입니다. 실제 적용 승인, 운영봇 수정 승인, 브로커 연결 승인, 주문 실행 승인이 아닙니다.

## NO-GO 조건

- remote write 발생
- systemd 변경 발생
- live bot 수정 발생
- secret 노출
- 필수 파일/디렉터리 없음
- disk space 불량
- Python 3 사용 불가
- result_status failed
- order execution true 상태
- secret marker 감지

## Warning 조건

`result_status=warning`은 GO decision을 만들 수 있어도 별도 수동 확인이 필요합니다. 쓰기 작업은 아직 금지됩니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
