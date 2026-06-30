# 외부 봇 샘플 클라이언트

이 폴더는 기존 외부 스캐너나 penny stock 후보 생성 봇이 AI Council의 read-only webhook으로 후보 신호를 보내는 예시입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

## Backend 준비

Webhook을 활성화한 상태로 backend를 실행합니다.

```bash
cd ~/AI-council/backend
WEBHOOKS_ENABLED=true \
WEBHOOK_SECRET=change-me \
WEBHOOK_REQUIRE_SECRET=true \
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 클라이언트 환경변수

```bash
export AI_COUNCIL_WEBHOOK_URL=http://127.0.0.1:8000/api/webhooks/trade-signal
export AI_COUNCIL_WEBHOOK_SECRET=change-me
export AI_COUNCIL_TIMEOUT_SECONDS=15
```

실제 secret은 Git에 커밋하지 마십시오.

## 후보 신호 전송

```bash
cd ~/AI-council/examples/external_bot
python3 send_trade_signal.py --payload sample_payloads/breakout_signal.json --pretty
python3 send_trade_signal.py --payload sample_payloads/high_spread_signal.json --pretty
```

클라이언트는 JSON payload를 `X-AI-Council-Webhook-Secret` header와 함께 AI Council webhook endpoint로 전송합니다.

이 클라이언트는 브로커 API를 호출하지 않고, 주문을 만들지 않고, 주문을 승인/취소하지 않으며, 포지션을 변경하지 않습니다. 후보 신호를 검토용 webhook으로 보내는 역할만 합니다.

## Payload 형식

필수 필드:

- `source`
- `signal_id`
- `ticker` 또는 `symbol`
- `strategy_signal` 또는 `signal` 또는 `setup`

선택 필드:

- `side`: 검토 문맥으로만 저장합니다. `buy` 또는 `sell` 값도 주문으로 처리하지 않습니다.
- `price` 또는 `last_price`
- `volume` 또는 `current_volume`
- `timeframe` 또는 `interval`
- `technical_indicators` 또는 `indicators`
- `news_headlines` 또는 `headlines`
- `risk_context` 또는 `risk`
- `timestamp` 또는 `event_time`

## 응답 해석

중요 응답 필드:

- `status`: `reviewed`, `duplicated`, `disabled`, `failed`
- `duplicated`: 같은 `source + signal_id`가 이미 검토된 경우 `true`
- `trade_review.id`: 저장된 거래 신호 검토 ID
- `structured_decision.decision`: `ALLOW`, `HOLD`, `BLOCK`, `NEED_MORE_DATA`
- `structured_decision.risk_level`: `low`, `medium`, `high`, `critical`
- `order_execution_allowed`: 항상 `false`

`order_execution_allowed=false`는 이 응답이 실제 거래 실행 권한이 아니라는 의미입니다. AI Council의 결과는 검토와 리스크 분석을 위한 메타데이터입니다.
