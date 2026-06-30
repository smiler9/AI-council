# Sample Webhook Smoke Test 결과 예시

아래는 로컬 smoke test가 성공했을 때 볼 수 있는 예시 출력입니다.

```text
Backend health: ok (AI Council)
Webhook status: enabled=True configured=True require_secret=True

Smoke test summary
- breakout_signal.json: status=reviewed duplicated=False review=... decision=HOLD risk=medium orders=False
- high_spread_signal.json: status=reviewed duplicated=False review=... decision=BLOCK risk=critical orders=False
- missing_news_signal.json: status=reviewed duplicated=False review=... decision=HOLD risk=high orders=False
- duplicate_signal.json: status=duplicated duplicated=True review=... decision=HOLD risk=medium orders=False
```

Provider와 입력 데이터에 따라 `decision`과 `risk_level`은 달라질 수 있습니다. 단, `order_execution_allowed`는 항상 `false`여야 합니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.
