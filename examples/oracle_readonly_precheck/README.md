# Oracle Read-only Precheck

Phase 24N prepares the read-only precheck plan and result recorder for Oracle outbox pre-creation.

This folder does not connect to Oracle, upload files, create directories, change permissions, touch systemd services, modify the live US Trader bot, call broker APIs, or execute orders.

## Build Plan

```bash
python examples/oracle_readonly_precheck/build_readonly_precheck_plan.py \
  --output tmp/oracle_readonly_precheck/precheck_plan.json \
  --pretty
```

## Verify Plan

```bash
python examples/oracle_readonly_precheck/verify_readonly_precheck_plan.py \
  --plan tmp/oracle_readonly_precheck/precheck_plan.json \
  --pretty
```

## Record Sample Result

```bash
python examples/oracle_readonly_precheck/record_readonly_precheck_result.py \
  --output tmp/oracle_readonly_precheck/precheck_result.json \
  --pretty
```

## Verify Result

```bash
python examples/oracle_readonly_precheck/verify_readonly_precheck_result.py \
  --result tmp/oracle_readonly_precheck/precheck_result.json \
  --pretty
```

## Full Dry-run

```bash
scripts/run_oracle_readonly_precheck_dryrun.sh
```

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
