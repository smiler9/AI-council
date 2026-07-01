# Read-only Precheck Approval Notes

## 해석 기준

- `passed`: 모든 필수 관찰값이 true이고 remote write/systemd/order 상태가 false입니다.
- `warning`: 일부 비핵심 관찰값이 불명확합니다. 다음 단계로 진행하지 말고 보완 확인합니다.
- `failed`: 필수 관찰값 실패, secret 노출 의심, systemd 변경, remote write 등이 확인되었습니다.
- `incomplete`: 아직 결과 기록이 완료되지 않았습니다.

## 실패 시 중단 조건

- `remote_write_executed`가 true인 경우
- `systemd_changed`가 true인 경우
- `order_execution_allowed`가 true인 경우
- secret, API key, token, private key, 실제 Oracle 접속 정보가 포함된 경우
- `penny_stock_bot.py` 또는 운영 서비스 변경이 필요한 경우

## 다음 단계 전 확인

- read-only result verify 통과
- result_status가 `passed`
- final approval packet verify 통과
- 실제 쓰기 작업은 아직 금지

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
