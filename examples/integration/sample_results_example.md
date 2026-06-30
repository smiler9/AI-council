# Sample Webhook Smoke Test Results

Example output from a successful local smoke test:

```text
Backend health: ok (AI Council)
Webhook status: enabled=True configured=True require_secret=True

Smoke test summary
- breakout_signal.json: status=reviewed duplicated=False review=... decision=HOLD risk=medium orders=False
- high_spread_signal.json: status=reviewed duplicated=False review=... decision=BLOCK risk=critical orders=False
- missing_news_signal.json: status=reviewed duplicated=False review=... decision=HOLD risk=high orders=False
- duplicate_signal.json: status=duplicated duplicated=True review=... decision=HOLD risk=medium orders=False
```

Actual decision and risk level can vary by provider, but `order_execution_allowed` must remain `false`.

AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.
