# External Bot Sample Client

This folder shows how an external penny-stock scanner can submit candidate signals to AI Council for read-only review.

AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## Setup

Start the AI Council backend with webhooks enabled:

```bash
cd ~/AI-council/backend
WEBHOOKS_ENABLED=true \
WEBHOOK_SECRET=change-me \
WEBHOOK_REQUIRE_SECRET=true \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Set client environment variables:

```bash
export AI_COUNCIL_WEBHOOK_URL=http://127.0.0.1:8000/api/webhooks/trade-signal
export AI_COUNCIL_WEBHOOK_SECRET=change-me
export AI_COUNCIL_TIMEOUT_SECONDS=15
```

## Send A Candidate Signal

```bash
cd ~/AI-council/examples/external_bot
python3 send_trade_signal.py --payload sample_payloads/breakout_signal.json --pretty
python3 send_trade_signal.py --payload sample_payloads/high_spread_signal.json --pretty
```

The client sends JSON to the AI Council webhook endpoint with the `X-AI-Council-Webhook-Secret` header. It does not connect to a broker, create an order, approve an order, cancel an order, or change positions.

## Payload Shape

Required fields:

- `source`
- `signal_id`
- `ticker` or `symbol`
- `strategy_signal` or `signal` or `setup`

Optional fields:

- `side`: stored as review context only. Values such as `buy` or `sell` are not treated as orders.
- `price` or `last_price`
- `volume` or `current_volume`
- `timeframe` or `interval`
- `technical_indicators` or `indicators`
- `news_headlines` or `headlines`
- `risk_context` or `risk`
- `timestamp` or `event_time`

## Response

Important response fields:

- `status`: `reviewed`, `duplicated`, `disabled`, or `failed`
- `duplicated`: true when `source + signal_id` was already reviewed
- `trade_review.id`: saved review id
- `structured_decision.decision`: `ALLOW`, `HOLD`, `BLOCK`, or `NEED_MORE_DATA`
- `structured_decision.risk_level`: `low`, `medium`, `high`, or `critical`
- `order_execution_allowed`: always `false`

`order_execution_allowed=false` means the response is never permission to place a trade. It is only decision-support metadata.
