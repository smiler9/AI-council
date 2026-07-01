# Oracle Outbox Signal File Contract

This contract defines the JSON files that a future Oracle export hook may write to the approved outbox directory.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Filename Rule

Use a unique file name:

```text
us_trader_signal_<timestamp>_<signal_id>.json
```

The timestamp should be UTC-friendly and safe for file names.

## Atomic Write

Write to a temporary file first, then rename into the outbox directory.

```text
us_trader_signal_<timestamp>_<signal_id>.json.tmp
us_trader_signal_<timestamp>_<signal_id>.json
```

The `.tmp` file is not consumed by the Mac pull pipeline.

## Required Fields

- `source`
- `signal_id`
- `symbol` or `ticker`
- `signal` or `strategy_signal`
- `action` or `raw_side`
- `price`
- `volume`
- `timestamp`
- `order_execution_allowed=false`

## Optional Fields

- `indicators`
- `technical_indicators`
- `risk_context`
- `risk_flags`
- `news_headlines`
- `adapter_warnings`
- `notes`

## Order-like Field Policy

The following fields may be preserved in the raw payload for audit only:

- `quantity`
- `order_type`
- `stop_loss`
- `take_profit`
- `shares`
- `notional`

They must never be interpreted as order instructions. AI Council stores them as review context only and records adapter warnings.

## Example JSON

```json
{
  "source": "us_trader_oracle",
  "signal_id": "sig_example_001",
  "symbol": "TESTA",
  "signal": "breakout",
  "action": "buy",
  "price": 0.82,
  "volume": 12500000,
  "timestamp": "2026-07-01T09:35:00Z",
  "indicators": {
    "rsi": 68,
    "relative_volume": 4.8
  },
  "risk_context": {
    "spread_pct": 3.2,
    "premarket": false
  },
  "order_execution_allowed": false
}
```

## Duplicate Rule

The duplicate key is:

```text
source + signal_id
```

Mac pull processing must not reprocess a duplicate signal identity.

## Retention

See `outbox_retention_policy.md`.
