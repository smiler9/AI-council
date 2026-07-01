# Oracle Outbox Rollback Plan

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Before Export Hook Application

- Keep the approval package local.
- Do not create Oracle directories automatically.
- Do not modify `penny_stock_bot.py`.
- Do not touch Oracle systemd services.

Rollback is simply to stop the approval process and keep documents for audit.

## After Export Hook Writes Outbox Files

If a future hook writes only JSON outbox files:

- disable the hook through the separately approved rollback plan
- preserve outbox files for audit
- stop Mac pull processing
- keep AI Council review mode disabled unless separately approved

## Sidecar Preview Rollback

- stop only the preview sidecar process if one was manually started
- preserve sidecar state/log files
- do not restart production bot services

## Mac Pull Rollback

- stop launchd/cron/manual pull task
- leave remote outbox files untouched
- archive local `tmp/oracle_pull` files if needed
- keep duplicate state for audit

## Review Mode Disablement

If review mode was enabled in a later phase:

- switch Mac processing back to preview mode
- confirm `normalize-preview` only
- confirm `order_execution_allowed=false`

## Files That Must Not Be Deleted Automatically

- Oracle live bot files
- `.secrets/` files
- outbox JSON files
- state files
- export logs
- AI Council reports

## Production Service Caution

Do not start, stop, restart, or reload Oracle production bot services as part of Phase 24K.

## Order Safety

Rollback is unrelated to real trading. No broker API is connected and no actual order is created, sent, approved, canceled, or executed.
