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
- `ORACLE_PREVIEW_LOOP_ALERT_COOLDOWN_SECONDS=3600`
- `ORACLE_PREVIEW_LOOP_COMPACT_IDLE=false`
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

Alert messages are written in Korean with explicit safety flags such as `order_execution_allowed=false` and `simulation_only=true`. Secret values are not printed in summaries, logs, or alert text. If Telegram is not configured, the loop records a disabled alert result and continues.

Identical problem alerts (same reason, file, stage, and error) are suppressed for `ORACLE_PREVIEW_LOOP_ALERT_COOLDOWN_SECONDS` (default 3600 seconds) so a persistently failing signal file or an unreachable backend does not spam Telegram every pass. Suppressed alerts are still counted in the run summary as `suppressed_cooldown`.

## State and Log Growth Controls

- Duplicate skips are recorded once per signal identity in the state file with a `skip_count` and `last_skipped_at` instead of appending a new entry every pass. Legacy state files are compacted automatically on load.
- Failures are recorded once per file/error pair with a `fail_count`.
- Signals containing order-like fields (for example `order_id`, `quantity`, `stop_loss`, `take_profit`) are rejected during validation; preview signals must stay review-only.
- The JSONL log rotates to `<name>.log.1` when it reaches 5 MB, and idle passes (nothing new processed, skipped, or failed) are not appended to it.
- With `--compact-idle` (or `ORACLE_PREVIEW_LOOP_COMPACT_IDLE=true`), idle passes print a one-line compact summary to stdout instead of the full JSON, which keeps screen logs small.

## Launchd Operation (Mac autonomy)

For unattended operation the loop and the AI Council backend run as user LaunchAgents instead of screen sessions. Agents restart on crash (`KeepAlive`) and start at login (`RunAtLoad`); the loop is wrapped in `caffeinate -s` so the Mac does not sleep while on AC power. A lid-closed MacBook still sleeps unless it is in clamshell mode.

- `com.ai-council.backend` — uvicorn on 127.0.0.1:8000, env from `tmp/ai_council_backend.env`
- `com.ai-council.oracle-preview-loop` — runs `scripts/run_oracle_preview_loop_forever.sh` under `caffeinate -s`
- `com.ai-council.daily-risk-brief` — POSTs `/api/operations/risk-brief/telegram/send` daily at 05:10 local time (after US market close)

Plists live in `~/Library/LaunchAgents/` (paths are machine-specific and not committed). Manage with:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ai-council.<name>.plist
launchctl bootout gui/$(id -u)/com.ai-council.<name>
launchctl kickstart -k gui/$(id -u)/com.ai-council.<name>
```

`scripts/run_oracle_preview_loop_forever.sh` sources `tmp/oracle_operations/oracle_preview_loop.env` (override with `ORACLE_PREVIEW_LOOP_ENV`) and runs one preview pass every `ORACLE_PREVIEW_LOOP_INTERVAL_SECONDS` (default 60).

## Safety Boundary

- `order_execution_allowed=false` is enforced before and after every API call.
- `simulation_only=true` is sent to Paper Trading.
- HOLD, BLOCK, and NEED_MORE_DATA results must remain `simulated_skip`.
- Only ALLOW with low or medium risk can produce a simulated entry, and that entry is still Paper Trading only.
- Oracle outbox files are never deleted or moved by this loop.
- Poll mode is available only with `--poll`; run-once is the default.
