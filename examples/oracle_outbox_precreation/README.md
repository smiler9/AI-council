# Oracle Outbox Pre-creation Rehearsal

Phase 24L prepares a manual-only package for creating Oracle outbox directories in a later approved step. It does not connect to Oracle, upload files, create remote directories, change permissions, touch systemd, or modify the live US Trader bot.

## What This Provides

- Placeholder pre-creation plan for outbox, processed, failed, state, and log paths
- Plan verifier that rejects remote execution, delete/move flags, systemd changes, secrets, and live/order modes
- Manual command examples generated under `tmp/oracle_outbox_precreation/commands/`
- Templates for read-only checks, commented creation examples, verification, rollback, and approval

## Dry-run

```bash
scripts/run_oracle_outbox_precreation_dryrun.sh
```

The dry-run writes only local ignored files under `tmp/oracle_outbox_precreation/`.

## Manual Safety Rules

- Oracle server files are not modified by these tools.
- Generated `mkdir`, `chmod`, `chown`, `rm`, and `mv` examples are commented out.
- No `systemctl start/stop/restart/reload` command is generated.
- Remote delete and remote move remain disabled.
- `order_execution_allowed=false` is enforced.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
