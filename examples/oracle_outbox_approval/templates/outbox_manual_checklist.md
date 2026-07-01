# Oracle Outbox Manual Approval Checklist

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Required Checks

- [ ] Oracle 운영봇 백업 확인
- [ ] outbox 경로 승인
- [ ] processed/failed/state 경로 승인
- [ ] export log 경로 승인
- [ ] 권한 확인
- [ ] 디스크 여유 확인
- [ ] Python 환경 확인
- [ ] export hook 위치 승인
- [ ] `place_order` 내부 미삽입 확인
- [ ] `check_exits` 내부 미삽입 확인
- [ ] `force_close_all` 내부 미삽입 확인
- [ ] sidecar preview smoke 통과
- [ ] Mac pull smoke 통과
- [ ] normalize-preview 통과
- [ ] review mode 전환 보류
- [ ] paper simulation 전환 보류
- [ ] 실제 주문 연결 없음 확인
- [ ] 브로커 API 연결 없음 확인
- [ ] remote delete/move 없음 확인
- [ ] rollback 계획 확인

## Approval Record

승인자는 별도 approval record에 서명하고, 적용 대상 파일과 경로를 다시 확인해야 합니다.

`order_execution_allowed=false`를 유지합니다.
