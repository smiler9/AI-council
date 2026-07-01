# Oracle Preview Operations Loop

This directory contains the local Mac preview-only loop for Oracle US Trader signals.

The loop reads Oracle outbox JSON files into a local ignored inbox, creates an AI Council read-only trade review, and records a Paper Trading simulation. It does not delete or move Oracle files, does not touch Oracle systemd services, does not modify the live bot, and never calls a broker order API.

## Run Once

```bash
scripts/run_oracle_preview_operations_once.sh --pretty
```

If Oracle connection values are provided, the loop calls the existing read-only pull helper with `--enable-readonly-copy`:

```bash
ORACLE_HOST=<oracle-host> \
ORACLE_USER=<oracle-user> \
ORACLE_SSH_KEY=<path-to-private-key> \
ORACLE_OUTBOX_DIR=<oracle-outbox-dir> \
scripts/run_oracle_preview_operations_once.sh --pretty
```

Without those values, it processes JSON files already present in `tmp/oracle_pull/inbox`.

## Environment

- `AI_COUNCIL_BASE_URL=http://127.0.0.1:8000`
- `AI_COUNCIL_WEBHOOK_SECRET=<optional-secret>`
- `ORACLE_PULL_LOCAL_INBOX=tmp/oracle_pull/inbox`
- `ORACLE_PREVIEW_LOOP_STATE=tmp/oracle_operations/preview_loop_state.json`
- `ORACLE_PREVIEW_LOOP_LOG=tmp/oracle_operations/preview_loop.log`
- `PAPER_PORTFOLIO_NAME=Oracle Preview Paper Portfolio`
- `ORACLE_PREVIEW_LOOP_MODE=run_once`
- `ORACLE_PREVIEW_LOOP_TELEGRAM_ALERTS=false`
- `TELEGRAM_ENABLED=false`
- `TELEGRAM_BOT_TOKEN=<telegram-bot-token>`
- `TELEGRAM_CHAT_ID=<telegram-chat-id>`

## Telegram Problem Alerts

The loop can send Telegram alerts only when a signal or loop run has a problem, such as invalid JSON, missing required fields, unsafe `order_execution_allowed`, webhook failure, Paper simulation safety failure, or a remote pull safety violation.

Telegram alerts are optional and report-only. They never trigger broker calls, order creation, Oracle file moves/deletes, or systemd operations. Enable them on the Mac loop process with:

```bash
ORACLE_PREVIEW_LOOP_TELEGRAM_ALERTS=true \
TELEGRAM_ENABLED=true \
TELEGRAM_BOT_TOKEN=<telegram-bot-token> \
TELEGRAM_CHAT_ID=<telegram-chat-id> \
scripts/run_oracle_preview_operations_once.sh --pretty
```

Secret values are not printed in summaries, logs, or alert text. If Telegram is not configured, the loop records a disabled alert result and continues.

## Safety Boundary

- `order_execution_allowed=false` is enforced before and after every API call.
- `simulation_only=true` is sent to Paper Trading.
- HOLD, BLOCK, and NEED_MORE_DATA results must remain `simulated_skip`.
- Only ALLOW with low or medium risk can produce a simulated entry, and that entry is still Paper Trading only.
- Oracle outbox files are never deleted or moved by this loop.
- Poll mode is available only with `--poll`; run-once is the default.
