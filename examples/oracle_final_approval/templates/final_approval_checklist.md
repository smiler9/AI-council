# Oracle Outbox Final Approval Checklist

- [ ] AI Council backend health 정상 확인
- [ ] AI Council frontend 200 OK 확인
- [ ] diagnostics summary 정상 확인
- [ ] outbox approval dry-run 통과
- [ ] outbox precreation dry-run 통과
- [ ] manual command review 통과
- [ ] Oracle read-only 사전 점검 필요 항목 확인
- [ ] 운영봇 백업 확인 필요
- [ ] systemd 조작 없음 확인
- [ ] 운영봇 수정 없음 확인
- [ ] 실제 주문 없음 확인
- [ ] `order_execution_allowed=false` 확인
- [ ] outbox 경로 승인
- [ ] processed 경로 승인
- [ ] failed 경로 승인
- [ ] state 경로 승인
- [ ] rollback 계획 확인
- [ ] 적용 후 read-only 검증 절차 확인
- [ ] 승인자 수동 기록
- [ ] 승인 일시 수동 기록
- [ ] 비고 수동 기록

기본 approval record는 `approved=false`입니다. 실제 Oracle 적용은 이 checklist와 approval record를 사람이 별도로 검토한 뒤에만 가능합니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
