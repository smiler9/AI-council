# Oracle Outbox Manual Creation Packet

Phase 24P builds a local command packet for a human to review before manually creating Oracle outbox directories.

GO from Phase 24O only allows this next manual review stage. It is not deployment approval, does not modify Oracle, does not change systemd, does not alter the live bot, and does not permit broker API connections or orders.

## Dry-run

```bash
scripts/run_oracle_outbox_manual_creation_dryrun.sh
```

Generated packets stay under `tmp/oracle_outbox_manual_creation/`.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
