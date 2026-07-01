# Preview Signal Write Checklist

- [ ] Phase 24Q post-creation decision is GO.
- [ ] GO is understood as Mac pull rehearsal preparation only.
- [ ] Preview signal JSON uses TESTA or another test-only symbol.
- [ ] `review_only=true` is present.
- [ ] `simulation_only=true` is present.
- [ ] `order_execution_allowed=false` is present.
- [ ] Manual upload command is reviewed by a human.
- [ ] systemd services are not changed.
- [ ] Oracle live bot files are not modified.
- [ ] No broker API is called.
- [ ] No order is created, sent, approved, cancelled, or executed.
- [ ] Post-write verification uses read-only commands only.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
