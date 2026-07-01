# Oracle Outbox Manual Creation Checklist

- [ ] Phase 24O GO decision reviewed; GO is not deployment approval.
- [ ] Oracle read-only precheck result reviewed.
- [ ] Outbox path approved: `<oracle-trading-dir>/ai_council_outbox`
- [ ] Processed path approved: `<oracle-trading-dir>/ai_council_processed`
- [ ] Failed path approved: `<oracle-trading-dir>/ai_council_failed`
- [ ] State path approved: `<oracle-trading-dir>/ai_council_state`
- [ ] Disk and Python environment checked.
- [ ] Directory creation commands remain commented until a human manually approves them.
- [ ] No `systemctl` start/stop/restart/reload command will be used.
- [ ] `penny_stock_bot.py` will not be modified in this step.
- [ ] No sample signal file will be created during verification.
- [ ] Rollback plan reviewed; remote deletion/move is not automatic.
- [ ] 실제 주문 없음, 브로커 API 연결 없음, `order_execution_allowed=false`.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
