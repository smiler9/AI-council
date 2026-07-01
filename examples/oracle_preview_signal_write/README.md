# Oracle Preview Signal Write Rehearsal

Phase 24R prepares a manual preview signal file write rehearsal after Oracle outbox directories are manually created and verified.

This folder only creates local templates, local command packets, result records, and GO/NO-GO decisions. It does not contact Oracle, upload files, modify systemd, patch the live bot, connect broker APIs, or execute orders.

## Dry-run

```bash
scripts/run_oracle_preview_signal_write_dryrun.sh
```

Generated signal files, packets, results, and decisions stay under `tmp/oracle_preview_signal_write/`.

GO from this phase only allows Mac pull rehearsal. It is not live bot patch approval and is not order approval.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
