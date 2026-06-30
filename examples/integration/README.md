# Webhook Integration Smoke Test

This smoke test verifies that AI Council can receive external bot candidate signals through the read-only webhook receiver.

AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## Required Backend State

Start the backend with webhooks enabled:

```bash
cd ~/AI-council/backend
WEBHOOKS_ENABLED=true \
WEBHOOK_SECRET=change-me \
WEBHOOK_REQUIRE_SECRET=true \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Set smoke test environment variables:

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=change-me
export AI_COUNCIL_TIMEOUT_SECONDS=20
```

## Run

```bash
cd ~/AI-council
python3 examples/integration/run_webhook_smoke_test.py
```

Or:

```bash
scripts/run_webhook_smoke.sh
```

## Expected Behavior

If webhooks are disabled, the script prints the disabled reason and exits without sending payloads.

If webhooks are enabled, the script sends:

- `breakout_signal.json`
- `high_spread_signal.json`
- `missing_news_signal.json`
- `duplicate_signal.json`

The script checks:

- backend `/health`
- `/api/webhooks/status`
- `trade_review.id`
- `structured_decision.decision`
- `structured_decision.risk_level`
- `order_execution_allowed=false`
- duplicate signal returns `duplicated=true`

## Duplicate Signal

`duplicate_signal.json` uses the same `source + signal_id` as `breakout_signal.json`. AI Council should return the existing `trade_review.id` and should not create a new meeting or review.

## Safety

The smoke test does not call broker APIs, create orders, approve orders, cancel orders, route orders, or change positions.
