# Outbox Pre-creation Approval Checklist

- [ ] Outbox path approved: `<oracle-trading-dir>/ai_council_outbox`
- [ ] Processed path approved: `<oracle-trading-dir>/ai_council_processed`
- [ ] Failed path approved: `<oracle-trading-dir>/ai_council_failed`
- [ ] State path approved: `<oracle-trading-dir>/ai_council_state`
- [ ] Log path approved: `<oracle-trading-dir>/logs/ai_council_export.log`
- [ ] Oracle disk space reviewed
- [ ] Oracle path owner/group reviewed
- [ ] Oracle operating bot backup confirmed
- [ ] Export hook has not been applied yet
- [ ] `penny_stock_bot.py` remains unmodified
- [ ] systemd services are not changed
- [ ] No active remote delete or move is planned
- [ ] No active permission change is planned without separate approval
- [ ] Mac pull smoke passed
- [ ] Outbox approval package dry-run passed
- [ ] Precreation dry-run passed
- [ ] Rollback plan reviewed
- [ ] Actual order execution is not connected
- [ ] `order_execution_allowed=false` confirmed

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
