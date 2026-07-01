# Oracle Precheck Intake Go/No-Go

Phase 24O turns manually collected Oracle read-only precheck observations into a validated intake JSON and a GO/NO_GO decision for the next review stage.

GO means only that the next manual review stage for outbox pre-creation can be considered. It does not approve deployment, modify Oracle, change systemd, alter the live bot, connect broker APIs, or execute orders.

## Dry-run

```bash
scripts/run_oracle_precheck_intake_dryrun.sh
```

Generated intake and decision files stay under `tmp/oracle_precheck_intake/`.

## Phase 24P Manual Creation Packet

After a GO decision, build the manual creation packet:

```bash
scripts/run_oracle_outbox_manual_creation_dryrun.sh
```

The packet only prepares commented command candidates and read-only verification templates. It does not write to Oracle.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
