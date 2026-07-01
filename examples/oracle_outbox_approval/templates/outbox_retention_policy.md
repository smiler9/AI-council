# Oracle Outbox Retention Policy

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Phase 24K Rule

Remote Oracle file deletion and movement are prohibited in Phase 24K.

- `remote_delete=false`
- `remote_move=false`
- no remote permission changes
- no remote directory changes by automation

## Initial Policy

The Mac pull pipeline reads or copies JSON files from the approved outbox directory. It does not mark remote files processed and does not move remote files into failed directories.

## Future Processed / Failed Policy

Processed and failed directory movement can be considered only in a later phase after separate manual approval.

Until then:

- keep remote files untouched
- store local pulled copies under ignored local paths
- track duplicates with local state

## Local Mac Cache

Suggested ignored local paths:

- `tmp/oracle_pull/inbox`
- `tmp/oracle_pull/state.json`
- `tmp/oracle_pull/failed`

The local state file records processed `source + signal_id` identities.

## Logs

The Oracle export hook may write a small export log after approval:

```text
<oracle-trading-dir>/logs/ai_council_export.log
```

Do not write secret values, API keys, account values, private key paths, or raw config content into the log.

## Capacity Management

Before enabling any export hook, manually confirm:

- disk free space
- expected signal rate
- maximum JSON file size
- log rotation plan
- manual cleanup owner

## Manual Cleanup

Remote cleanup is not automated in Phase 24K. Any future cleanup must be manual, documented, and approved.

`order_execution_allowed=false` must remain enforced for every approval package, pull workflow, and AI Council response.
