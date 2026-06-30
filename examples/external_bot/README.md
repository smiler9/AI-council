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

## Bridge client

`bridge_client.py`는 기존 봇이 만든 JSON 파일 또는 stdin payload를 AI Council webhook으로 전달하기 위한 호환성 bridge입니다.

Dry-run은 webhook을 호출하지 않고 profile mapping 결과와 adapter warning만 출력합니다.

```bash
python3 bridge_client.py --payload sample_payloads/generic_bot_signal.json --profile generic --dry-run --pretty
python3 bridge_client.py --payload sample_payloads/penny_bot_v1_signal.json --profile penny_bot_v1 --dry-run --pretty
cat sample_payloads/minimal_signal.json | python3 bridge_client.py --stdin --profile minimal_signal --dry-run --pretty
```

Webhook 전송:

```bash
python3 bridge_client.py --payload sample_payloads/generic_bot_signal.json --profile generic --pretty
```

Mapping profiles:

- `mapping_profiles/generic.json`: 여러 scanner payload alias를 폭넓게 지원
- `mapping_profiles/penny_bot_v1.json`: 예시 penny stock bot payload 구조
- `mapping_profiles/minimal_signal.json`: ticker/signal 중심 최소 payload
- `mapping_profiles/us_trader_oracle_v1.json`: Oracle US Trader 운영본 payload 호환성 점검용 read-only mapping

Bridge client는 브로커 API를 호출하지 않고 주문을 생성/전송/승인/취소/실행하지 않습니다.

## US Trader Oracle read-only bridge

`us_trader_oracle_bridge.py`는 Oracle에서 실행 중인 US Trader 운영본을 직접 수정하지 않고, signal JSON 파일이나 stdin payload를 AI Council normalize-preview 또는 trade-signal endpoint로 전달하는 전용 bridge입니다.

Preview mode는 trade review를 생성하지 않습니다.

```bash
python3 us_trader_oracle_bridge.py \
  --payload sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --preview \
  --pretty
```

Dry-run은 HTTP 호출도 하지 않습니다.

```bash
python3 us_trader_oracle_bridge.py \
  --payload sample_payloads/us_trader_oracle_order_like_signal.json \
  --profile us_trader_oracle_v1 \
  --dry-run \
  --pretty
```

stdin 입력:

```bash
cat sample_payloads/us_trader_oracle_minimal_signal.json | \
  python3 us_trader_oracle_bridge.py --stdin --profile us_trader_oracle_v1 --preview --pretty
```

Review mode는 AI Council webhook이 활성화되어 있고 secret이 설정된 경우에만 사용합니다.

```bash
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=<webhook-secret>
python3 us_trader_oracle_bridge.py \
  --payload sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --review \
  --pretty
```

이 bridge는 Oracle SSH 접속, systemd 조작, live bot 실행/중지/재시작, 브로커 API 호출, 주문 생성/전송을 수행하지 않습니다.

Order-like field 안전 정책:

- `quantity`, `qty`, `shares`, `order_type`, `stop_loss`, `take_profit`, `broker`, `account`, `route`, `tif`, `submit_order`, `place_order`는 raw payload에만 남고 `adapter_warnings`에 기록됩니다.
- `buy`, `sell`, `entry`, `exit`는 `raw_side`에 보존되며 normalized `side`는 `review_only`입니다.
- `order_execution_allowed=false`가 유지됩니다.

## Normalize preview API

외부 봇을 연결하기 전에 payload 정규화 결과만 확인할 수 있습니다. 이 API는 trade review를 생성하지 않습니다.

```bash
curl -X POST http://127.0.0.1:8000/api/webhooks/normalize-preview \
  -H "Content-Type: application/json" \
  -d @sample_payloads/order_like_fields_signal.json
```

응답의 `adapter_warnings`에서 누락 필드, order-like field 무시, side 안전 변환을 확인합니다.

## Payload 형식

필수 필드:

- `source`
- `signal_id`
- `ticker` 또는 `symbol` 또는 `code` 또는 `stock` 또는 `instrument` 또는 `asset`
- `strategy_signal` 또는 `signal` 또는 `setup` 또는 `pattern` 또는 `trigger` 또는 `reason`

선택 필드:

- `side` 또는 `direction` 또는 `action` 또는 `intent`: 검토 문맥으로만 저장합니다. `buy`, `sell`, `long`, `short`, `entry`, `exit` 값도 주문으로 처리하지 않습니다.
- `price` 또는 `last_price` 또는 `close` 또는 `current_price` 또는 `entry_price` 또는 `trigger_price`
- `volume` 또는 `current_volume` 또는 `vol` 또는 `day_volume`
- `timeframe` 또는 `interval` 또는 `tf` 또는 `candle_interval`
- `technical_indicators` 또는 `indicators` 또는 `ta` 또는 `metrics`
- `news_headlines` 또는 `headlines` 또는 `news` 또는 `catalysts`
- `risk_context` 또는 `risk` 또는 `risk_flags` 또는 `meta`
- `timestamp` 또는 `event_time`

Order-like field 안전 정책:

- `quantity`, `qty`, `shares`, `notional`, `order_type`, `take_profit`, `stop_loss`, `broker`, `account`, `route`, `tif`, `extended_hours` 같은 필드는 raw payload에는 보존되지만 주문 로직으로 연결되지 않습니다.
- adapter는 해당 필드를 `adapter_warnings`에 기록하고 `order_execution_allowed=false`를 유지합니다.

## 응답 해석

중요 응답 필드:

- `status`: `reviewed`, `duplicated`, `disabled`, `failed`
- `duplicated`: 같은 `source + signal_id`가 이미 검토된 경우 `true`
- `trade_review.id`: 저장된 거래 신호 검토 ID
- `structured_decision.decision`: `ALLOW`, `HOLD`, `BLOCK`, `NEED_MORE_DATA`
- `structured_decision.risk_level`: `low`, `medium`, `high`, `critical`
- `order_execution_allowed`: 항상 `false`

`order_execution_allowed=false`는 이 응답이 실제 거래 실행 권한이 아니라는 의미입니다. AI Council의 결과는 검토와 리스크 분석을 위한 메타데이터입니다.
