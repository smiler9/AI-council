# `penny_stock_bot.py` Export Hook Patch Draft

이 문서는 자동 적용용 diff가 아니라, Oracle US Trader 운영본에 export hook을 넣기 전에 검토할 코드 블록 예시입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## 적용하지 말 것

이 draft는 Oracle live bot에 자동 적용하지 않습니다. 실제 적용 전에는 백업, preflight, sidecar dry-run, normalize-preview가 모두 통과해야 합니다.

## 안전한 후보 위치

후보 1: `analyze_signals(ticker)`가 signal dict를 반환한 직후, 호출부에서 export.

후보 2: `scan_and_enter(...)` 내부에서 candidate가 만들어진 직후, 실제 주문 호출 전.

현 로컬 백업본 기준 구조:

```python
result = analyze_signals(ticker)
if result:
    entry = {"ticker": ticker, **result}
    # candidate export hook 후보: entry가 만들어진 직후
```

또는:

```python
for candidate in candidates:
    ticker = candidate["ticker"]
    current_price = candidate["current_price"]
    signals = candidate["signals"]
    # candidate export hook 후보: position sizing 또는 order call 전에 export-only 수행
```

## 절대 넣지 말아야 할 위치

- `place_order(...)` 내부
- `check_exits(...)` 내부
- `force_close_all(...)` 내부
- 실제 주문 호출 직후
- 주문 결과를 처리하는 branch 내부

## 최소 import 예시

```python
from ai_council_signal_exporter_module import (
    build_ai_council_signal,
    export_ai_council_signal,
)
```

## 최소 export 예시

```python
AI_COUNCIL_OUTBOX_DIR = "/path/to/ai_council_outbox"

def maybe_export_ai_council_candidate(candidate):
    try:
        payload = build_ai_council_signal(
            symbol=candidate["ticker"],
            strategy_signal="+".join(candidate.get("signals", [])) or "scanner_candidate",
            raw_side="buy",
            price=candidate.get("current_price"),
            volume=None,
            timeframe="5m",
            indicators={
                "rsi": candidate.get("rsi"),
                "volume_ratio": candidate.get("volume_ratio"),
                "gap_pct": candidate.get("gap_pct"),
                "recent_momentum_pct": candidate.get("recent_momentum_pct"),
                "signal_score": candidate.get("signal_score"),
                "vwap": candidate.get("vwap"),
            },
            risk_context={
                "breakout_ok": candidate.get("breakout_ok"),
                "source_function": "scan_and_enter",
            },
            news_headlines=[],
            notes="Review-only export before any live order path.",
        )
        export_ai_council_signal(payload, AI_COUNCIL_OUTBOX_DIR)
    except Exception as exc:
        print(f"[AI Council export skipped] {candidate.get('ticker')}: {exc}")
```

사용 후보:

```python
if result:
    entry = {"ticker": ticker, **result}
    maybe_export_ai_council_candidate(entry)
```

또는 주문 호출 전에:

```python
for candidate in candidates:
    # ... candidate field extraction ...
    maybe_export_ai_council_candidate(candidate)
    # 이후 기존 live flow는 기존대로 유지. AI Council 결과를 주문 로직에 연결하지 않음.
```

## 안전 규칙

- `raw_side="buy"`는 review context로만 저장합니다.
- `order_execution_allowed=false`를 강제합니다.
- AI Council 결과를 `place_order` 입력으로 사용하지 않습니다.
- sidecar bridge는 기본 `preview` mode로만 먼저 검증합니다.
- review mode와 paper simulation은 별도 단계입니다.

## Expected payload

```json
{
  "source": "us_trader_oracle",
  "signal_id": "us_trader_oracle_TESTA_breakout_...",
  "symbol": "TESTA",
  "signal": "RSI_DIP+VOLUME_EXPLOSION",
  "action": "buy",
  "price": 0.82,
  "volume": null,
  "timeframe": "5m",
  "indicators": {
    "rsi": 68,
    "volume_ratio": 5.2,
    "signal_score": 3.1
  },
  "risk": {
    "source_function": "scan_and_enter"
  },
  "news": [],
  "review_only": true,
  "simulation_only": true,
  "order_execution_allowed": false
}
```

## Rollback

1. Sidecar process만 중지합니다.
2. export hook feature flag를 비활성화합니다.
3. outbox/state directory를 보존한 뒤 분석합니다.
4. live bot service는 별도 지시 없이는 조작하지 않습니다.
5. 기존 `penny_stock_bot.py` 백업본으로 되돌릴 준비가 된 경우에만 maintenance window에서 진행합니다.
