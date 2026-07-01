# Oracle Final Approval Gate

Phase 24M prepares the final manual approval packet before any future Oracle outbox directory creation. It reviews Phase 24L manual commands, separates read-only precheck examples from commented write examples, and verifies that approval records are not pre-approved.

This folder does not connect to Oracle, upload files, create directories, change permissions, touch systemd, modify the live US Trader bot, call broker APIs, or execute orders.

## Build Packet

```bash
python examples/oracle_final_approval/build_final_approval_packet.py \
  --precreation-plan tmp/oracle_outbox_precreation/precreation_plan.json \
  --manual-commands-dir tmp/oracle_outbox_precreation/commands \
  --output tmp/oracle_final_approval \
  --pretty
```

## Review Manual Commands

```bash
python examples/oracle_final_approval/review_manual_commands.py \
  --commands-dir tmp/oracle_outbox_precreation/commands \
  --pretty
```

## Verify Packet

```bash
python examples/oracle_final_approval/verify_final_approval_packet.py \
  --packet tmp/oracle_final_approval \
  --pretty
```

## Dry-run

```bash
scripts/run_oracle_final_approval_dryrun.sh
```

The generated approval packet stays under `tmp/oracle_final_approval/` and is not committed.

## Phase 24N Read-only Precheck

After final approval packet verification, prepare a read-only precheck plan and result recorder:

```bash
scripts/run_oracle_readonly_precheck_dryrun.sh
```

This still does not connect to Oracle or execute remote commands. It only generates local plan/result JSON under `tmp/oracle_readonly_precheck/`.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
