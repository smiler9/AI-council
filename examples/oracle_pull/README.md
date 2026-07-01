# Oracle Mac Pull Preview Pipeline

Phase 24J prepares a Mac-side pull workflow for Oracle US Trader outbox JSON files.

The preferred early flow is:

1. Oracle keeps signal JSON in an approved outbox directory.
2. Mac lists or copies those JSON files with a read-only SSH workflow.
3. AI Council processes local copies through `normalize-preview`.
4. Review mode and paper simulation remain explicit later steps.

This folder does not modify Oracle files, upload code, start tunnels, or touch systemd services.

## Tools

- `oracle_outbox_pull_preview.py`: previews read-only listing/copy commands.
- `process_pulled_signals.py`: processes local pulled JSON with AI Council preview/review endpoints.
- `verify_pull_plan.py`: verifies pull plans are preview/read-only and do not include remote delete or move behavior.

## Dry-run

```bash
python examples/oracle_pull/oracle_outbox_pull_preview.py --dry-run --pretty
```

## Verify Plan

```bash
python examples/oracle_pull/verify_pull_plan.py \
  --plan examples/oracle_pull/sample_pull_plan.json \
  --pretty
```

## Process Sample Signals

```bash
python examples/oracle_pull/process_pulled_signals.py \
  --inbox examples/oracle_pull/sample_pulled_signals \
  --mode preview \
  --pretty
```

## Optional Read-only Listing

Only use this after manually filling placeholders. It does not write remote files.

```bash
python examples/oracle_pull/oracle_outbox_pull_preview.py \
  --host <oracle-host> \
  --user <oracle-user> \
  --key <path-to-private-key> \
  --outbox-dir <oracle-outbox-dir> \
  --enable-ssh-readonly-list \
  --pretty
```

## Safety Boundary

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

Remote file deletion, remote movement, systemd operations, broker API calls, and order execution are out of scope. `order_execution_allowed=false` is always required.

## Phase 24K Outbox Approval

Outbox path finalization and approval package documents are available at:

- `docs/US_TRADER_ORACLE_OUTBOX_PATH_APPROVAL.md`
- `examples/oracle_outbox_approval/`

Run:

```bash
scripts/run_oracle_outbox_approval_dryrun.sh
```

## Phase 24L Outbox Pre-creation

Before any real Oracle directory creation, generate and verify the manual-only precreation package:

```bash
scripts/run_oracle_outbox_precreation_dryrun.sh
```

This remains a local dry-run. It does not create remote directories, move/delete remote files, change permissions, or touch systemd.
