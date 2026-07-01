# Oracle Outbox Approval Package

Phase 24K finalizes placeholder outbox paths and bundles the file contract, retention policy, rollback plan, and manual checklist for review.

This folder does not write to Oracle, upload files, create remote directories, change permissions, touch systemd, connect to broker APIs, or execute orders.

## Build

```bash
python examples/oracle_outbox_approval/build_outbox_approval_package.py \
  --output tmp/oracle_outbox_approval \
  --pretty
```

## Verify

```bash
python examples/oracle_outbox_approval/verify_outbox_approval_package.py \
  --package tmp/oracle_outbox_approval \
  --pretty
```

## Dry-run

```bash
scripts/run_oracle_outbox_approval_dryrun.sh
```

## Phase 24L Pre-creation Rehearsal

After approval package verification, Phase 24L creates a manual-only pre-creation plan and command package:

```bash
scripts/run_oracle_outbox_precreation_dryrun.sh
```

The pre-creation package still does not connect to Oracle, create directories, change permissions, touch systemd, or modify the live bot.

## Safety Boundary

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

`order_execution_allowed=false`, `remote_delete=false`, and `remote_move=false` are required.
