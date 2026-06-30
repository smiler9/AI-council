# AI Council

AI Council은 여러 AI 에이전트가 하나의 주제나 외부 봇 후보 신호를 함께 검토하고, 반박하고, 리스크를 정리한 뒤 구조화된 판단을 만드는 로컬 웹 프로그램입니다.

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

영문 안전 경계도 함께 유지합니다:

> AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## 현재 구현 범위

- Phase 1: FastAPI backend, React/Vite frontend, SQLite, mock 기반 AI 회의실
- Phase 2: LLM Provider abstraction, 기본 `mock`, `local_openai_compatible` 구조
- Phase 3: 회의 참고 파일 업로드와 context summary 반영
- Phase 4: 토론 라운드와 structured decision JSON
- Phase 5: 선택적 Telegram 리포트 전송, 기본 비활성화
- Phase 6: Ollama/vLLM OpenAI-compatible local LLM 연결 검증 구조
- Phase 7: read-only 거래 신호 검토 API
- Phase 8: 외부 봇 webhook receiver와 input adapter
- Phase 9: 외부 봇 샘플 클라이언트, smoke test, sample payload, 개발 스크립트
- Phase 10: 한글 중심 UI/문서/리포트 정리
- Phase 11: 티커만 입력하는 종목 자동 분석, 자율 후보 발굴 검토, mock market data provider
- Phase 12: Market Data Provider Framework와 real-data ready read-only API
- Phase 13: 선택적 Yahoo Finance/yfinance read-only quote/snapshot provider
- Phase 14: 뉴스, SEC 공시, 리스크 이벤트 provider framework
- Phase 15: Watchlist Batch Review와 Portfolio Risk Brief
- Phase 16: Scheduled Watchlist Review와 자동 Risk Brief 보고
- Phase 17: Operations Dashboard와 Recent Risk Brief
- Phase 18: 외부 봇 payload 호환성 확장, normalize-preview API, bridge client
- Phase 19: 실제 주문 없는 Paper Trading Simulation Mode
- Phase 20: Paper Trading 슬리피지, 스프레드, 가상 청산, mark-to-market 시뮬레이션
- Phase 21: Paper Trading Performance Analytics와 가상 전략 성과 리포트
- Phase 22: 전체 E2E 시나리오 테스트와 smoke pipeline
- Phase 23: 원클릭 운영 진단과 health check

## 프로젝트 구조

```text
AI-council/
  backend/      FastAPI + SQLite API
  frontend/     React + Vite UI
  examples/     외부 봇 샘플 클라이언트와 통합 smoke test
  scripts/      로컬 개발 실행 스크립트
  reports/      생성된 Markdown 회의 리포트, Git 제외
```

## 실행 방법

Backend:

```bash
cd ~/AI-council/backend
python3 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements.txt
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd ~/AI-council/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

접속 URL:

- Frontend: `http://127.0.0.1:5173/`
- Backend: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/health`

개발 스크립트:

```bash
scripts/run_backend.sh
scripts/run_frontend.sh
scripts/run_tests.sh
scripts/run_webhook_smoke.sh
scripts/run_full_e2e.sh
scripts/run_diagnostics.sh
```

## 주요 API

- `GET /health`
- `GET /api/agents`
- `GET /api/meetings`
- `POST /api/meetings`
- `GET /api/meetings/{meeting_id}`
- `POST /api/meetings/{meeting_id}/run`
- `GET /api/meetings/{meeting_id}/report`
- `POST /api/meetings/{meeting_id}/files`
- `GET /api/meetings/{meeting_id}/files`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `GET /api/telegram/status`
- `POST /api/meetings/{meeting_id}/telegram/send`
- `GET /api/market-data/status`
- `GET /api/market-data/quote/{ticker}`
- `GET /api/market-data/snapshot/{ticker}`
- `GET /api/market-data/news/{ticker}`
- `GET /api/market-data/filings/{ticker}`
- `GET /api/risk-events/status`
- `GET /api/risk-events/news/{ticker}`
- `GET /api/risk-events/filings/{ticker}`
- `GET /api/risk-events/detect/{ticker}`
- `POST /api/watchlists`
- `GET /api/watchlists`
- `GET /api/watchlists/{watchlist_id}`
- `PATCH /api/watchlists/{watchlist_id}`
- `DELETE /api/watchlists/{watchlist_id}`
- `POST /api/watchlists/{watchlist_id}/run-review`
- `GET /api/watchlist-reviews`
- `GET /api/watchlist-reviews/{review_id}`
- `POST /api/watchlist-reviews/{review_id}/telegram/send`
- `POST /api/watchlists/{watchlist_id}/schedules`
- `GET /api/watchlists/{watchlist_id}/schedules`
- `GET /api/watchlist-schedules`
- `GET /api/watchlist-schedules/{schedule_id}`
- `PATCH /api/watchlist-schedules/{schedule_id}`
- `DELETE /api/watchlist-schedules/{schedule_id}`
- `POST /api/watchlist-schedules/{schedule_id}/run-now`
- `POST /api/watchlist-schedules/run-due`
- `GET /api/watchlist-schedule-runs`
- `GET /api/watchlist-schedule-runs/{run_id}`
- `GET /api/operations/summary`
- `GET /api/operations/risk-brief`
- `POST /api/operations/risk-brief/telegram/send`
- `GET /api/operations/schedule-health`
- `GET /api/diagnostics/summary`
- `GET /api/diagnostics/security`
- `GET /api/diagnostics/providers`
- `GET /api/diagnostics/runtime`
- `GET /api/diagnostics/e2e-status`
- `POST /api/paper/portfolios`
- `GET /api/paper/portfolios`
- `GET /api/paper/portfolios/{portfolio_id}`
- `PATCH /api/paper/portfolios/{portfolio_id}`
- `DELETE /api/paper/portfolios/{portfolio_id}`
- `POST /api/paper/portfolios/{portfolio_id}/simulate-review`
- `POST /api/paper/portfolios/{portfolio_id}/positions/{position_id}/simulate-exit`
- `POST /api/paper/portfolios/{portfolio_id}/evaluate-exits`
- `GET /api/paper/portfolios/{portfolio_id}/positions`
- `GET /api/paper/portfolios/{portfolio_id}/trades`
- `GET /api/paper/portfolios/{portfolio_id}/summary`
- `GET /api/paper/portfolios/{portfolio_id}/performance`
- `GET /api/paper/portfolios/{portfolio_id}/performance/by-strategy`
- `GET /api/paper/portfolios/{portfolio_id}/performance/by-decision`
- `GET /api/paper/portfolios/{portfolio_id}/performance/by-risk-event`
- `GET /api/paper/portfolios/{portfolio_id}/performance/by-watchlist`
- `POST /api/paper/portfolios/{portfolio_id}/performance/report`
- `POST /api/trade-reviews`
- `POST /api/ticker-reviews`
- `POST /api/autonomous-reviews`
- `POST /api/autonomous-reviews/{review_id}/telegram/send`
- `GET /api/trade-reviews`
- `GET /api/trade-reviews/{trade_review_id}`
- `POST /api/trade-reviews/{trade_review_id}/telegram/send`
- `GET /api/webhooks/status`
- `POST /api/webhooks/normalize-preview`
- `POST /api/webhooks/trade-signal`
- `GET /api/webhooks/events`
- `GET /api/webhooks/events/{event_id}`

## 회의 모드와 토론 라운드

회의 모드:

- `quick_review`: 빠른 검토
- `deep_debate`: 심층 토론
- `skeptic_review`: 비판 중심 검토
- `risk_gate_review`: 리스크 게이트 검토
- `action_plan`: 실행 계획 수립

토론 라운드:

1. `initial_opinion`: 에이전트 1차 의견
2. `rebuttal`: 비판 검토와 리스크 반박
3. `revision`: 반박 반영 수정 의견
4. `chairman_summary`: 의장 요약
5. `structured_decision`: 구조화된 판단

Structured decision 예시:

```json
{
  "decision": "HOLD",
  "confidence": 0.62,
  "risk_level": "high",
  "trade_allowed": false,
  "position_size_multiplier": 0.0,
  "primary_reasons": [],
  "risk_flags": [],
  "required_follow_up": [],
  "data_quality": "limited",
  "order_execution_allowed": false
}
```

`order_execution_allowed`는 항상 `false`입니다.

## Local LLM 설정

기본값은 mock provider입니다.

```bash
LLM_PROVIDER=mock
```

Ollama 예시:

```bash
LLM_PROVIDER=local_openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:8b
LLM_API_KEY=local
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=1200
```

vLLM 예시:

```bash
LLM_PROVIDER=local_openai_compatible
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=<served-model-name>
LLM_API_KEY=local
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=1200
```

Local LLM 서버가 없거나 실패하면 meeting은 실패 또는 안전한 fallback 상태로 기록되고, 앱 전체가 죽지 않도록 처리합니다. 실패하더라도 브로커 연결이나 주문 실행은 시도하지 않습니다.

## 파일 업로드

회의 상세 화면에서 참고 파일을 업로드할 수 있습니다. 파일 요약은 다음 회의 실행 시 context로 포함됩니다.

지원 형식:

- `.txt`
- `.md`
- `.csv`
- `.json`
- `.log`
- `.pdf`: Phase 3 stub, unsupported 상태로 안전 처리

제한:

- 최대 2MB
- 파일명 sanitization
- path traversal 방지
- 허용 확장자 제한
- text 기반 형식의 binary content 거부

## Telegram 설정

Telegram은 리포트 전송 전용이며 기본 비활성화입니다.

```bash
TELEGRAM_ENABLED=false
```

활성화 예시:

```bash
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat id>
TELEGRAM_TIMEOUT_SECONDS=10
```

실제 token과 chat id는 Git에 커밋하지 마십시오. `.env`는 `.gitignore`에 포함되어 있습니다.

## Webhook 설정

외부 봇은 후보 신호를 webhook으로 보낼 수 있습니다. 이 endpoint는 주문 지시를 받는 곳이 아니라 read-only 검토 접수 endpoint입니다.

기본값:

```bash
WEBHOOKS_ENABLED=false
WEBHOOK_SECRET=change-me
WEBHOOK_REQUIRE_SECRET=true
```

Endpoint:

```text
POST /api/webhooks/trade-signal
```

Secret header:

```text
X-AI-Council-Webhook-Secret: <your local secret>
```

Webhook payload alias:

- ticker: `ticker`, `symbol`, `code`, `stock`, `instrument`, `asset`
- signal: `strategy_signal`, `signal`, `setup`, `pattern`, `trigger`, `reason`
- side: `side`, `direction`, `action`, `intent`
- price: `price`, `last_price`, `close`, `current_price`, `entry_price`, `trigger_price`
- volume: `volume`, `current_volume`, `vol`, `day_volume`
- timeframe: `timeframe`, `interval`, `tf`, `candle_interval`
- indicators: `technical_indicators`, `indicators`, `ta`, `metrics`
- news: `news_headlines`, `headlines`, `news`, `catalysts`
- risk: `risk_context`, `risk`, `risk_flags`, `meta`
- `timestamp` 또는 `event_time`

`buy`, `sell`, `long`, `short`, `entry`, `exit` 같은 값은 주문 의도로 처리하지 않고 `review_only` 문맥으로만 저장합니다. `quantity`, `order_type`, `stop_loss`, `take_profit`, `broker`, `account` 같은 order-like 필드는 raw payload에는 보존하지만 주문 처리로 연결하지 않고 adapter warning에 기록합니다.

정규화 미리보기:

```bash
curl -X POST http://127.0.0.1:8000/api/webhooks/normalize-preview \
  -H "Content-Type: application/json" \
  -d @examples/external_bot/sample_payloads/generic_bot_signal.json
```

이 API는 trade review를 생성하지 않고 표준 payload와 `adapter_warnings`만 반환합니다.

Bridge client dry-run:

```bash
cd ~/AI-council/examples/external_bot
python3 bridge_client.py --payload sample_payloads/penny_bot_v1_signal.json --profile penny_bot_v1 --dry-run --pretty
cat sample_payloads/generic_bot_signal.json | python3 bridge_client.py --stdin --profile generic --dry-run --pretty
```

Bridge client 전송:

```bash
export AI_COUNCIL_WEBHOOK_URL=http://127.0.0.1:8000/api/webhooks/trade-signal
export AI_COUNCIL_WEBHOOK_SECRET=change-me
python3 bridge_client.py --payload sample_payloads/generic_bot_signal.json --profile generic --pretty
```

`normalize-preview`와 bridge client 모두 브로커 API에 연결하지 않고 주문을 생성/전송/승인/취소/실행하지 않습니다.

중복 방지:

- `source + signal_id` 조합이 이미 들어온 경우 기존 `trade_review_id`를 반환합니다.
- 중복 요청은 새 meeting이나 새 review를 만들지 않습니다.

## External Bot 샘플 클라이언트

```bash
cd ~/AI-council/examples/external_bot
export AI_COUNCIL_WEBHOOK_URL=http://127.0.0.1:8000/api/webhooks/trade-signal
export AI_COUNCIL_WEBHOOK_SECRET=change-me
python3 send_trade_signal.py --payload sample_payloads/breakout_signal.json --pretty
```

샘플 payload:

- `breakout_signal.json`: 일반 watch-only breakout 후보
- `high_spread_signal.json`: 높은 spread와 premarket 리스크 후보
- `missing_news_signal.json`: 뉴스가 비어 있어 data_quality가 제한적인 후보
- `duplicate_signal.json`: breakout과 같은 `source + signal_id`로 idempotency 검증

## Smoke Test

Backend를 webhook 활성화 상태로 실행합니다.

```bash
cd ~/AI-council/backend
WEBHOOKS_ENABLED=true \
WEBHOOK_SECRET=change-me \
WEBHOOK_REQUIRE_SECRET=true \
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

다른 터미널에서 smoke test를 실행합니다.

```bash
cd ~/AI-council
export AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
export AI_COUNCIL_WEBHOOK_SECRET=change-me
scripts/run_webhook_smoke.sh
```

검증 항목:

- `/health`
- `/api/webhooks/status`
- sample payload 전송
- `order_execution_allowed=false`
- duplicate payload의 `duplicated=true`

## Phase 11 종목 자동 분석과 자율 후보 발굴

종목 자동 분석은 사용자가 ticker만 입력해도 AI Council이 기본 분석 payload를 생성하고 기존 Trade Review / Risk Gate Review 엔진을 실행하는 기능입니다.

이 기능은 주문을 실행하지 않습니다. `side`는 항상 `review_only` 중심으로 처리하며, 응답의 `order_execution_allowed`는 항상 `false`입니다.

API:

```text
POST /api/ticker-reviews
```

요청 예시:

```bash
curl -X POST "http://127.0.0.1:8000/api/ticker-reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "TESTA",
    "review_mode": "penny_stock_risk",
    "timeframe": "1d",
    "notes": "종목만 입력한 자동 리서치 요청"
  }'
```

`ticker`만 필수입니다. 나머지 값은 기본값을 사용합니다.

지원 review mode:

- `penny_stock_risk`
- `momentum_review`
- `long_term_review`
- `news_catalyst_review`
- `general_review`

자동 생성 payload 예시:

```json
{
  "ticker": "TESTA",
  "strategy_signal": "auto_research",
  "side": "review_only",
  "price": 0.82,
  "volume": 12500000,
  "timeframe": "1d",
  "source": "ticker_only_auto_research",
  "notes": "Ticker-only auto research request",
  "technical_indicators": {
    "relative_volume": 4.8
  },
  "news_headlines": [
    "TESTA sample catalyst requires validation"
  ],
  "risk_context": {
    "auto_research": true,
    "review_mode": "penny_stock_risk",
    "data_source": "mock_market_data",
    "market_data_available": true,
    "news_available": true,
    "data_quality": "sufficient",
    "spread_pct": 2.2,
    "premarket": false
  },
  "order_execution_allowed": false
}
```

Market data provider 구조:

- `mock_market_data`: Phase 11에서 실제 구현된 로컬 mock provider
- `external_market_data_stub`: future extension stub, 실제 외부 API 호출 없음
- `news_provider_stub`: future extension stub, 실제 외부 API 호출 없음
- `sec_filing_provider_stub`: future extension stub, 실제 외부 API 호출 없음

환경변수:

```bash
MARKET_DATA_PROVIDER=mock
MARKET_DATA_TIMEOUT_SECONDS=10
```

`penny_stock_risk` 모드에서 `TEST`로 시작하는 ticker는 안전한 mock 테스트 데이터로 처리됩니다. 그 외 ticker는 market data unavailable 상태로 처리되어 `data_quality=limited`가 됩니다.

Ticker-only review는 내부적으로 Trade Review를 생성하고, `risk_gate_review` meeting과 Markdown report를 연결합니다. 생성된 report에는 `종목 자동 분석 요청`, `자동 생성된 분석 payload`, `사용된 데이터 provider`, `데이터 품질`, `구조화된 판단`, `안전 경계` 섹션이 포함됩니다.

### Autonomous Trader Review Mode

Autonomous Trader Review Mode는 이름과 달리 자율 주문 실행 기능이 아닙니다. AI Council이 mock market data 기반으로 후보 종목을 자동 발굴하고, 각 후보를 Trade Review / Risk Gate Review로 검토한 뒤 결과를 보고하는 review-only 모드입니다.

실제 브로커 API 연결, 주문 생성, 주문 전송, 주문 승인, 주문 취소, 포지션 변경 기능은 없습니다. `ALLOW`가 나오더라도 “검토상 허용”일 뿐 실제 주문 실행 허용이 아닙니다. `order_execution_allowed`는 항상 `false`입니다.

API:

```text
POST /api/autonomous-reviews
```

요청 예시:

```bash
curl -X POST "http://127.0.0.1:8000/api/autonomous-reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "universe": "mock_penny_stocks",
    "review_mode": "penny_stock_risk",
    "max_candidates": 5,
    "timeframe": "1d",
    "notes": "자율 후보 발굴 및 검토"
  }'
```

지원 universe:

- `mock_penny_stocks`
- `mock_momentum_stocks`
- `mock_watchlist`
- `custom_stub`

지원 review mode:

- `penny_stock_risk`
- `momentum_review`
- `news_catalyst_review`
- `general_review`

Mock scanner 후보 예시:

```json
[
  {
    "ticker": "TESTA",
    "last_price": 0.82,
    "volume": 12500000,
    "relative_volume": 4.8,
    "spread_pct": 2.2,
    "premarket": false,
    "mock_news_headlines": ["TESTA sample catalyst requires validation"],
    "scan_reason": "relative_volume_spike"
  },
  {
    "ticker": "TESTB",
    "last_price": 0.47,
    "volume": 850000,
    "relative_volume": 7.4,
    "spread_pct": 8.4,
    "premarket": true,
    "mock_news_headlines": ["TESTB sample premarket attention increases"],
    "scan_reason": "high_spread_risk"
  }
]
```

응답 요약 예시:

```json
{
  "id": "...",
  "universe": "mock_penny_stocks",
  "review_mode": "penny_stock_risk",
  "candidate_count": 5,
  "results": [
    {
      "ticker": "TESTA",
      "decision": "HOLD",
      "risk_level": "high",
      "trade_allowed": false,
      "order_execution_allowed": false,
      "scan_reason": "relative_volume_spike",
      "linked_trade_review_id": "...",
      "linked_ticker_review_id": "...",
      "linked_meeting_id": "..."
    }
  ],
  "summary": {
    "allow_count": 0,
    "hold_count": 3,
    "block_count": 1,
    "need_more_data_count": 1,
    "order_execution_allowed": false
  },
  "order_execution_allowed": false
}
```

Telegram 전송 구조:

```text
POST /api/autonomous-reviews/{review_id}/telegram/send
```

`TELEGRAM_ENABLED=false`이면 disabled 상태로 안전하게 응답합니다. Telegram은 보고 전용이며 주문 실행과 연결되지 않습니다.

## Phase 12 Market Data Provider Framework

Phase 12는 ticker-only review와 autonomous review가 나중에 실제 시장 데이터 API를 안전하게 연결할 수 있도록 provider framework를 정리한 단계입니다. 현재 실제 동작 provider는 `mock_market_data`뿐이며, 외부 provider는 기본 비활성화된 stub입니다.

지원 provider 구조:

- `mock_market_data`: 기본값, 로컬 mock 데이터만 사용
- `external_market_data_stub`: future extension stub
- `polygon_stub`: future Polygon 연동 stub, 실제 호출 없음
- `alpaca_data_stub`: future market-data-only 연동 stub, 실제 호출 없음
- `yahoo_finance`: Phase 13 선택적 read-only Yahoo Finance/yfinance provider
- `yahoo_finance_stub`: future extension stub, 실제 호출 없음
- `news_provider_stub`: mock headlines/stub
- `sec_filing_provider_stub`: mock filings/stub

환경변수 예시:

```bash
MARKET_DATA_PROVIDER=mock_market_data
MARKET_DATA_ENABLED=true
MARKET_DATA_TIMEOUT_SECONDS=10
MARKET_DATA_ALLOW_EXTERNAL=false

POLYGON_API_KEY=
ALPACA_DATA_API_KEY=
ALPACA_DATA_API_SECRET=
NEWS_PROVIDER_API_KEY=
SEC_PROVIDER_ENABLED=false
```

실제 API key나 token은 Git에 커밋하지 마십시오. `.env` 또는 로컬 shell 환경변수로만 관리하십시오.

Provider status:

```bash
curl "http://127.0.0.1:8000/api/market-data/status"
```

응답 예시:

```json
{
  "provider": "mock_market_data",
  "enabled": true,
  "external_enabled": false,
  "available_providers": ["mock_market_data", "polygon_stub"],
  "active_provider": "mock_market_data",
  "api_key_configured": false,
  "yahoo_finance_available": false,
  "yfinance_installed": false,
  "external_calls_allowed": false,
  "last_check_status": "ok",
  "provider_warning": null,
  "order_execution_allowed": false
}
```

Read-only data API:

```bash
curl "http://127.0.0.1:8000/api/market-data/quote/TESTA"
curl "http://127.0.0.1:8000/api/market-data/snapshot/TESTA"
curl "http://127.0.0.1:8000/api/market-data/news/TESTA"
curl "http://127.0.0.1:8000/api/market-data/filings/TESTA"
```

이 API들은 데이터 조회 전용입니다. 주문/거래 기능과 연결하지 않습니다.

Ticker Review와 Autonomous Review 관계:

- `POST /api/ticker-reviews`는 market data snapshot 결과를 기반으로 자동 payload를 구성합니다.
- `POST /api/autonomous-reviews`는 provider의 mock universe 후보를 가져와 후보별 ticker review와 trade review를 생성합니다.
- provider 실패 또는 데이터 부족 시 `data_quality=limited`와 `NEED_MORE_DATA`/`HOLD` 성격의 안전한 review-only 흐름으로 처리됩니다.
- 모든 응답에서 `order_execution_allowed=false`를 유지합니다.

## Phase 13 Yahoo Finance Read-only Provider

Phase 13은 Phase 12의 provider framework에 `yahoo_finance` provider를 추가합니다. 이 provider는 `yfinance`를 통해 quote/snapshot을 읽기 전용으로 조회합니다. 기본 provider는 계속 `mock_market_data`이며, Yahoo Finance는 명시적으로 활성화한 경우에만 외부 네트워크 호출을 시도합니다.

설치:

```bash
cd ~/AI-council/backend
../.venv/bin/python -m pip install -r requirements.txt
```

기본값, 외부 호출 없음:

```bash
MARKET_DATA_PROVIDER=mock_market_data
MARKET_DATA_ENABLED=true
MARKET_DATA_ALLOW_EXTERNAL=false
```

Yahoo Finance 활성화 예시:

```bash
MARKET_DATA_PROVIDER=yahoo_finance
MARKET_DATA_ENABLED=true
MARKET_DATA_ALLOW_EXTERNAL=true
MARKET_DATA_TIMEOUT_SECONDS=10
```

mock provider로 되돌리기:

```bash
MARKET_DATA_PROVIDER=mock_market_data
MARKET_DATA_ENABLED=true
MARKET_DATA_ALLOW_EXTERNAL=false
```

`MARKET_DATA_ALLOW_EXTERNAL=false`이면 `MARKET_DATA_PROVIDER=yahoo_finance`를 선택해도 실제 외부 호출을 하지 않고 disabled/fallback 상태로 응답합니다. `yfinance`가 설치되어 있지 않거나 Yahoo Finance 조회가 실패해도 앱 전체가 죽지 않으며, provider warning과 `data_quality=unavailable` 또는 `limited`로 안전하게 처리합니다.

Yahoo Finance/yfinance 데이터는 공식 브로커 데이터가 아니며 지연, 누락, 부정확성이 있을 수 있습니다. 이 데이터는 검토와 리스크 분석 보조용이며 주문 실행에 사용되지 않습니다.

Quote 예시:

```bash
curl "http://127.0.0.1:8000/api/market-data/quote/AAPL"
```

응답 필드:

- `provider`: `yahoo_finance` 또는 fallback provider
- `last_price`, `bid`, `ask`, `spread_pct`, `volume`
- `data_quality`: `sufficient`, `limited`, `unavailable`
- `provider_warning`
- `order_execution_allowed=false`

Snapshot 예시:

```bash
curl "http://127.0.0.1:8000/api/market-data/snapshot/AAPL"
```

Ticker Review / Autonomous Review 연동:

- `POST /api/ticker-reviews`는 활성 provider의 snapshot 결과를 payload에 반영합니다.
- `POST /api/autonomous-reviews`는 mock universe 후보를 유지하되, 가능하면 후보별 snapshot에 활성 provider 결과를 반영합니다.
- provider 실패 시 mock fallback 또는 제한된 데이터 품질로 처리합니다.

News/filings endpoint는 Phase 13에서 계속 stub입니다.

## Phase 14 뉴스/공시 리스크 이벤트 Provider

Phase 14는 penny stock 검토에서 중요한 뉴스, SEC 공시, offering, reverse split, delisting notice, halt, promotion성 뉴스 같은 리스크 이벤트를 읽기 전용으로 수집/분류하는 framework입니다. 기본값은 mock provider이며, 외부 뉴스/공시 provider는 비활성화된 stub입니다.

지원 provider 구조:

- `mock_news_provider`: Phase 14 실제 동작 mock 뉴스 provider
- `mock_sec_filing_provider`: Phase 14 실제 동작 mock SEC filing provider
- `risk_event_detector`: rule-based 리스크 이벤트 감지기
- `external_news_stub`: future extension stub, 실제 호출 없음
- `sec_edgar_stub`: future SEC EDGAR 연동 stub, 실제 호출 없음
- `finnhub_news_stub`: future Finnhub 뉴스 연동 stub, 실제 호출 없음
- `polygon_news_stub`: future Polygon 뉴스 연동 stub, 실제 호출 없음

환경변수:

```bash
NEWS_PROVIDER=mock_news_provider
NEWS_PROVIDER_ENABLED=true
NEWS_ALLOW_EXTERNAL=false
NEWS_TIMEOUT_SECONDS=10

SEC_FILING_PROVIDER=mock_sec_filing_provider
SEC_FILING_ENABLED=true
SEC_ALLOW_EXTERNAL=false
SEC_TIMEOUT_SECONDS=10

RISK_EVENT_DETECTOR_ENABLED=true

FINNHUB_API_KEY=
POLYGON_API_KEY=
```

실제 API key나 token은 Git에 커밋하지 마십시오. `.env` 또는 로컬 shell 환경변수로만 관리하십시오.

Risk event status:

```bash
curl "http://127.0.0.1:8000/api/risk-events/status"
```

뉴스/공시/감지 API:

```bash
curl "http://127.0.0.1:8000/api/risk-events/news/TESTB"
curl "http://127.0.0.1:8000/api/risk-events/filings/TESTB"
curl "http://127.0.0.1:8000/api/risk-events/detect/TESTB"
```

Mock 뉴스 응답 예시:

```json
{
  "ticker": "TESTB",
  "headlines": [
    {
      "title": "TESTB announces proposed public offering",
      "source": "mock_news",
      "published_at": "...",
      "url": null
    }
  ],
  "provider": "mock_news_provider",
  "data_quality": "mock",
  "order_execution_allowed": false
}
```

Mock 공시 응답 예시:

```json
{
  "ticker": "TESTB",
  "filings": [
    {
      "form": "424B",
      "filed_at": "2026-06-10",
      "description": "Prospectus supplement for proposed public offering."
    }
  ],
  "provider": "mock_sec_filing_provider",
  "data_quality": "mock",
  "order_execution_allowed": false
}
```

Risk event detect 응답 예시:

```json
{
  "ticker": "TESTB",
  "provider": "risk_event_detector",
  "events": [
    {
      "event_type": "offering",
      "severity": "high",
      "confidence": 0.86,
      "evidence": ["TESTB announces proposed public offering"],
      "recommended_decision_impact": "HOLD_OR_BLOCK"
    }
  ],
  "high_severity_event_count": 2,
  "order_execution_allowed": false
}
```

Ticker Review / Autonomous Review 연동:

- `POST /api/ticker-reviews`는 risk event detector 결과를 `risk_context.risk_events`, `detected_event_count`, `high_severity_event_count`, `top_risk_event`에 포함합니다.
- offering, reverse split, delisting notice, trading halt 같은 이벤트는 structured decision의 risk flags와 required follow-up에 반영됩니다.
- critical event가 감지되면 decision은 `BLOCK` 또는 `HOLD` 성격으로 제한됩니다.
- `POST /api/autonomous-reviews`는 후보별 detector 결과와 top risk event를 결과 카드에 포함합니다.
- 모든 결과에서 `order_execution_allowed=false`를 유지합니다.

이 기능은 뉴스/공시 텍스트를 분석하는 read-only risk analysis 기능입니다. 실제 주문 실행, 브로커 API 연결, 포지션 변경 기능은 없습니다.

## Phase 15 Watchlist Batch Review

Phase 15는 관심종목 Watchlist를 등록하고 여러 ticker를 한 번에 ticker-only auto research / Risk Gate Review로 검토하는 기능입니다. 시장 데이터, 뉴스/공시 리스크 이벤트, structured decision을 종합해 Watchlist Risk Brief를 생성합니다.

이 기능은 주문을 실행하지 않습니다. `ALLOW`는 “검토상 허용”일 뿐 실제 매수 허용이 아니며, 모든 API 응답의 `order_execution_allowed`는 `false`입니다.

Watchlist 생성:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlists" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Penny Stock Watchlist",
    "description": "관심 penny stock 후보군",
    "tickers": ["TESTA", "TESTB", "TESTC", "TESTD", "TESTE"],
    "review_mode": "penny_stock_risk"
  }'
```

입력 규칙:

- ticker는 대문자로 정규화됩니다.
- 중복 ticker는 제거됩니다.
- 빈 ticker는 거부됩니다.
- 기본 최대 ticker 수는 50개입니다.
- Watchlist API는 주문 의도를 받지 않습니다.

Watchlist 분석 실행:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlists/{watchlist_id}/run-review"
```

응답 예시:

```json
{
  "id": "...",
  "watchlist_id": "...",
  "watchlist_name": "Penny Stock Watchlist",
  "ticker_count": 5,
  "summary": {
    "allow_count": 0,
    "hold_count": 2,
    "block_count": 2,
    "need_more_data_count": 1,
    "highest_risk_level": "critical",
    "order_execution_allowed": false
  },
  "results": [
    {
      "ticker": "TESTB",
      "decision": "HOLD",
      "risk_level": "high",
      "top_risk_event": "offering",
      "risk_event_severity": "high",
      "trade_allowed": false,
      "order_execution_allowed": false,
      "linked_ticker_review_id": "...",
      "linked_trade_review_id": "...",
      "linked_meeting_id": "..."
    }
  ],
  "order_execution_allowed": false
}
```

결과 분류:

- 위험 종목: `decision=BLOCK` 또는 `risk_level=critical`
- 주의 종목: `decision=HOLD` 또는 `risk_level=high`
- 추가 데이터 필요: `decision=NEED_MORE_DATA`
- 검토상 허용: `decision=ALLOW`

Watchlist review 조회:

```bash
curl "http://127.0.0.1:8000/api/watchlist-reviews"
curl "http://127.0.0.1:8000/api/watchlist-reviews/{review_id}"
```

Telegram 보고:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlist-reviews/{review_id}/telegram/send"
```

`TELEGRAM_ENABLED=false`이면 disabled 상태로 안전하게 응답합니다. Telegram은 보고 전용이며 주문 실행과 연결되지 않습니다.

Watchlist Risk Brief report에는 다음 섹션이 포함됩니다.

- Watchlist 이름
- 분석 종목 수
- 전체 요약
- 위험 종목
- 주의 종목
- 추가 데이터 필요 종목
- 검토상 허용 종목
- 종목별 판단 요약
- 주요 리스크 이벤트
- 데이터 품질
- 추가 확인 필요사항
- 안전 경계

## Phase 16 Scheduled Watchlist Review

Phase 16은 등록된 Watchlist를 정해진 일정 또는 수동 트리거로 자동 분석하고, Watchlist Risk Brief를 저장하며, 선택적으로 Telegram으로 자동 보고하는 기능입니다.

이 기능은 “자동 분석/자동 보고” 전용입니다. 백그라운드 자동매매, 자동 주문, 브로커 연결, 포지션 변경 기능은 없습니다. 모든 schedule, run, review 응답의 `order_execution_allowed`는 `false`입니다.

지원 cadence:

- `manual_only`: 수동 실행 전용, `next_run_at=null`
- `daily`: 매일 지정한 `run_time`
- `weekdays`: 평일 지정한 `run_time`
- `hourly_stub`: future extension stub, 현재는 1시간 뒤로 단순 계산
- `market_open_stub`: future extension stub, 현재는 자동 next run 없음
- `market_close_stub`: future extension stub, 현재는 자동 next run 없음

Schedule 생성:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlists/{watchlist_id}/schedules" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "매일 장전 리스크 점검",
    "enabled": true,
    "cadence": "daily",
    "run_time": "08:30",
    "timezone": "Asia/Seoul",
    "auto_send_telegram": false
  }'
```

응답 예시:

```json
{
  "id": "...",
  "watchlist_id": "...",
  "name": "매일 장전 리스크 점검",
  "enabled": true,
  "cadence": "daily",
  "run_time": "08:30",
  "timezone": "Asia/Seoul",
  "auto_send_telegram": false,
  "last_run_at": null,
  "next_run_at": "2026-06-30T23:30:00+00:00",
  "order_execution_allowed": false
}
```

Schedule 조회/수정/삭제:

```bash
curl "http://127.0.0.1:8000/api/watchlist-schedules"
curl "http://127.0.0.1:8000/api/watchlist-schedules/{schedule_id}"
curl -X PATCH "http://127.0.0.1:8000/api/watchlist-schedules/{schedule_id}" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
curl -X DELETE "http://127.0.0.1:8000/api/watchlist-schedules/{schedule_id}"
```

지금 실행:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlist-schedules/{schedule_id}/run-now"
```

`run-now`는 연결된 Watchlist를 즉시 `run-review`하고, Watchlist Review와 schedule run log를 생성합니다. `auto_send_telegram=true`이면 Telegram 전송을 시도하지만, `TELEGRAM_ENABLED=false`이면 `telegram_disabled` 또는 disabled 결과로 안전하게 기록됩니다. Telegram 실패가 Watchlist Review 생성을 취소하지 않습니다.

Run-now 응답 예시:

```json
{
  "schedule": {"id": "...", "last_run_at": "...", "next_run_at": "..."},
  "review": {
    "id": "...",
    "watchlist_name": "Penny Stock Watchlist",
    "ticker_count": 5,
    "summary": {
      "block_count": 2,
      "hold_count": 2,
      "need_more_data_count": 1,
      "allow_count": 0,
      "order_execution_allowed": false
    }
  },
  "run": {
    "id": "...",
    "status": "completed",
    "watchlist_review_id": "...",
    "order_execution_allowed": false
  },
  "telegram": {"requested": false, "status": "not_requested"},
  "order_execution_allowed": false
}
```

실행 대상 스케줄 실행:

```bash
curl -X POST "http://127.0.0.1:8000/api/watchlist-schedules/run-due"
```

`run-due`는 현재 시각 기준 `enabled=true`이고 `next_run_at <= now`인 schedule만 실행합니다. 실패한 schedule은 전체 실행을 중단하지 않고 `errors` 배열과 schedule run log에 기록합니다.

Run-due 응답 예시:

```json
{
  "due_count": 1,
  "executed_count": 1,
  "failed_count": 0,
  "skipped_count": 2,
  "results": [],
  "errors": [],
  "order_execution_allowed": false
}
```

Schedule run log 조회:

```bash
curl "http://127.0.0.1:8000/api/watchlist-schedule-runs"
curl "http://127.0.0.1:8000/api/watchlist-schedule-runs?schedule_id={schedule_id}"
curl "http://127.0.0.1:8000/api/watchlist-schedule-runs/{run_id}"
```

macOS/Linux에서 외부 스케줄러로 `run-due`를 호출할 수 있습니다. Phase 16은 backend daemon을 만들지 않고, cron/launchd/systemd timer 또는 다른 로컬 스케줄러가 아래 endpoint를 호출하는 구조입니다.

Cron 개념 예시:

```cron
*/15 * * * * curl -s -X POST http://127.0.0.1:8000/api/watchlist-schedules/run-due >/tmp/ai-council-run-due.log 2>&1
```

macOS launchd에서도 같은 endpoint를 `curl -X POST http://127.0.0.1:8000/api/watchlist-schedules/run-due`로 호출하면 됩니다. 실제 secret이나 token은 launchd plist 또는 shell 환경에 하드코딩하지 말고 로컬 환경변수로 관리하십시오.

## Phase 17 Operations Dashboard & Recent Risk Brief

Phase 17은 AI Council 운영 상태를 한 화면에서 확인하기 위한 운영 대시보드와 최근 리스크 브리프 API를 추가합니다.

운영 대시보드는 분석/보고/모니터링 전용입니다. 실제 브로커 API 연결, 주문 생성, 주문 전송, 주문 승인, 주문 취소, 주문 실행, 포지션 변경 기능은 없습니다. 모든 operations API 응답의 `order_execution_allowed`는 `false`입니다.

운영 요약 API:

```bash
curl "http://127.0.0.1:8000/api/operations/summary"
```

응답 예시:

```json
{
  "status": "ok",
  "counts": {
    "meetings": 0,
    "trade_reviews": 0,
    "ticker_reviews": 0,
    "autonomous_reviews": 0,
    "watchlists": 0,
    "watchlist_reviews": 0,
    "watchlist_schedules": 0,
    "schedule_runs": 0
  },
  "risk_summary": {
    "block_count": 0,
    "hold_count": 0,
    "need_more_data_count": 0,
    "allow_count": 0,
    "highest_risk_level": "low",
    "order_execution_allowed": false
  },
  "provider_status": {
    "llm_provider": "mock",
    "market_data_provider": "mock_market_data",
    "telegram_enabled": false,
    "webhooks_enabled": false,
    "order_execution_allowed": false
  },
  "order_execution_allowed": false
}
```

Recent Risk Brief:

```bash
curl "http://127.0.0.1:8000/api/operations/risk-brief?limit=20"
```

이 API는 최근 Watchlist Review, Ticker Review, Trade Review, Autonomous Review를 종합해 다음 그룹으로 분류합니다.

- 위험 종목: `BLOCK` 또는 `critical`
- 주의 종목: `HOLD` 또는 `high`
- 추가 데이터 필요 종목: `NEED_MORE_DATA`
- 검토상 허용 종목: `ALLOW`

응답 예시:

```json
{
  "generated_at": "...",
  "limit": 20,
  "danger_items": [],
  "warning_items": [],
  "need_more_data_items": [],
  "allow_items": [],
  "summary": {
    "danger_count": 0,
    "warning_count": 0,
    "need_more_data_count": 0,
    "allow_count": 0,
    "order_execution_allowed": false
  },
  "order_execution_allowed": false
}
```

Schedule Health:

```bash
curl "http://127.0.0.1:8000/api/operations/schedule-health"
```

응답에는 활성/비활성 schedule 수, 현재 due schedule 수, 마지막 실행 상태, 실패한 schedule run 수, Telegram disabled 건수, 다음 예정 실행 목록이 포함됩니다.

Operations Risk Brief Telegram 전송:

```bash
curl -X POST "http://127.0.0.1:8000/api/operations/risk-brief/telegram/send"
```

`TELEGRAM_ENABLED=false`이면 disabled 상태로 안전하게 응답합니다. Telegram은 운영 브리프 보고 전용이며 주문 실행과 연결되지 않습니다.

Frontend의 “운영 대시보드” 섹션은 다음을 표시합니다.

- 시스템 상태
- Provider 상태
- 최근 분석 요약
- 최근 고위험 종목
- 최근 Watchlist 분석
- 최근 스케줄 실행
- 스케줄 상태
- Telegram 상태
- Webhook 상태
- 주문 실행 상태: 비활성화
- 안전 경계

## Phase 19 Paper Trading Simulation Mode

Phase 19는 AI Council의 검토 결과를 실제 주문 없이 내부 가상 포트폴리오에 기록하는 시뮬레이션 기능입니다. Paper Trading은 브로커 계좌, 실제 주문 API, 실제 체결 API와 연결되지 않습니다.

Portfolio 생성:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/portfolios \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AI Council Paper Portfolio",
    "description": "실제 주문 없는 가상 검증용 포트폴리오",
    "starting_cash": 10000
  }'
```

Simulate review:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/simulate-review \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "trade_review",
    "source_id": "<review_id>",
    "simulation_policy": "risk_gate_conservative",
    "max_notional_per_trade": 100,
    "allow_only_decision": false
  }'
```

지원 source type:

- `trade_review`
- `ticker_review`
- `autonomous_review`
- `watchlist_review`
- `webhook_event`

Simulation policy:

- `risk_gate_conservative`: `ALLOW`이면서 risk level이 `low` 또는 `medium`인 경우에만 `simulated_entry`를 기록하고, 그 외는 `simulated_skip`
- `observe_only`: 모든 신호를 `simulated_skip`으로 기록
- `aggressive_research_only`: `ALLOW`만 내부 가상 진입으로 기록하고 나머지는 skip

가상 체결 가격은 source payload의 `price`, read-only market data quote의 `last_price` 순서로 사용합니다. 가격이 없으면 `skipped_missing_price`로 기록합니다. 이 값은 실제 브로커 체결 가격이 아닙니다.

조회 API:

```bash
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/summary
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/positions
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/trades
```

응답은 항상 `order_execution_allowed=false`를 포함합니다. 내부 시뮬레이션 플래그는 `paper_trade_execution_allowed="simulation_only"`로 표시됩니다.

## Phase 20 Paper Trading Slippage, Spread & Exit Simulation

Phase 20은 Phase 19의 내부 가상 포트폴리오에 슬리피지, 스프레드, 가상 손절/익절, 가상 청산, mark-to-market 성과 요약을 추가합니다. 모든 기록은 `simulation_only=true`인 내부 시뮬레이션이며 실제 주문, 실제 체결, 브로커 계좌 변경과 연결되지 않습니다.

가상 진입 가격 계산:

```text
simulated_entry_price = base_price * (1 + spread_bps / 10000 + slippage_bps / 10000)
```

기본 시뮬레이션 설정:

```json
{
  "slippage_bps": 25,
  "spread_bps": 50,
  "max_spread_pct": 5.0,
  "take_profit_pct": 8.0,
  "stop_loss_pct": 5.0,
  "max_holding_minutes": 240,
  "max_notional_per_trade": 100,
  "allow_partial_fill_simulation": false,
  "simulation_only": true
}
```

스프레드가 `max_spread_pct`를 초과하면 `simulated_skip`과 `skipped_spread_too_wide`로 기록합니다.

가상 청산:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/positions/{position_id}/simulate-exit \
  -H "Content-Type: application/json" \
  -d '{
    "exit_reason": "manual_simulated_exit",
    "exit_price": 1.05,
    "slippage_bps": 25,
    "spread_bps": 50
  }'
```

청산 조건 평가:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/evaluate-exits \
  -H "Content-Type: application/json" \
  -d '{
    "execute_simulated_exits": false,
    "take_profit_pct": 8.0,
    "stop_loss_pct": 5.0
  }'
```

`execute_simulated_exits=true`로 설정해도 실제 주문은 생성하지 않습니다. 조건을 충족한 포지션에 대해 `paper_trades`에 `simulated_exit` 기록만 남깁니다.

Portfolio summary는 다음 가상 성과 필드를 포함합니다.

- `total_position_value`
- `total_equity`
- `unrealized_pnl`
- `realized_pnl`
- `total_pnl`
- `exposure_pct`
- `open_position_count`
- `closed_trade_count`
- `simulated_win_count`
- `simulated_loss_count`

모든 응답은 `simulation_only=true`와 `order_execution_allowed=false`를 포함합니다.

## Phase 21 Paper Trading Performance Analytics

Phase 21은 Paper Trading Simulation 기록을 기반으로 내부 가상 성과를 분석합니다. 전략별 성과, AI Council 판단별 성과, 리스크 이벤트별 성과, Watchlist별 성과를 집계하고 Markdown 가상 성과 리포트를 생성할 수 있습니다.

중요:

> 이 리포트는 내부 가상 시뮬레이션 결과이며 실제 주문, 실제 체결, 실제 투자 성과가 아닙니다.

성과 요약:

```bash
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance
```

그룹별 분석:

```bash
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance/by-strategy
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance/by-decision
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance/by-risk-event
curl http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance/by-watchlist
```

가상 성과 리포트 생성:

```bash
curl -X POST http://127.0.0.1:8000/api/paper/portfolios/{portfolio_id}/performance/report
```

리포트 섹션:

- 가상 성과 리포트
- 포트폴리오 요약
- 총 가상 손익
- 실현 손익
- 평가 손익
- 승률
- 평균 수익/손실
- 전략별 성과
- 판단별 성과
- 리스크 이벤트별 성과
- Watchlist별 성과
- 주요 관찰점
- 한계 및 주의사항
- 안전 경계

모든 성과 API는 `simulation_only=true`와 `order_execution_allowed=false`를 반환합니다. 이 기능은 브로커 API와 연결하지 않으며 실제 주문/체결/투자성과를 만들지 않습니다.

## Phase 22 Full E2E Scenario Test

Phase 22는 AI Council의 핵심 운영 흐름을 실행 중인 backend에 대해 HTTP API 기반으로 끝까지 점검하는 smoke pipeline입니다.

검증 흐름:

1. Backend health 확인
2. Operations summary 확인
3. Watchlist 생성
4. Watchlist 일괄 분석
5. 뉴스/공시 리스크 이벤트 감지
6. Ticker-only review 생성
7. Trade review 직접 생성
8. Paper portfolio 생성
9. Review 결과를 가상 포트폴리오에 반영
10. ALLOW low-risk 진입 가능 케이스 확인
11. Paper summary, positions, trades 조회
12. 가상 청산 조건 평가
13. Paper performance 분석
14. 가상 성과 리포트 생성
15. Operations risk brief 확인
16. Schedule health 확인
17. Telegram disabled 안전 처리 확인

Backend가 실행 중일 때:

```bash
scripts/run_full_e2e.sh
```

직접 실행:

```bash
python3 examples/integration/run_full_e2e_scenario.py --pretty
python3 examples/integration/run_full_e2e_scenario.py --base-url http://127.0.0.1:8000
```

환경변수:

```bash
AI_COUNCIL_BASE_URL=http://127.0.0.1:8000
AI_COUNCIL_TIMEOUT_SECONDS=30
```

기대 결과:

- 모든 API 응답에서 `order_execution_allowed=false`
- Paper Trading 관련 응답에서 `simulation_only=true`
- Telegram이 기본 비활성화면 disabled 응답
- 가상 성과 리포트에 실제 주문/체결/투자성과가 아니라는 문구 포함
- 브로커 API, 실제 주문 생성, 실제 주문 전송, 실제 포지션 변경 없음

실패 시 backend 실행 여부, DB 상태, 최근 코드 변경, provider 설정을 먼저 확인하십시오. E2E 점검은 secret/API key/token을 요구하지 않습니다.

## Phase 23 One-click Operations Diagnostics

Phase 23은 운영자가 AI Council 상태를 한 번에 점검할 수 있는 read-only diagnostics API, CLI script, 프론트 “운영 진단” 화면을 추가합니다.

Diagnostics API:

```bash
curl http://127.0.0.1:8000/api/diagnostics/summary
curl http://127.0.0.1:8000/api/diagnostics/security
curl http://127.0.0.1:8000/api/diagnostics/providers
curl http://127.0.0.1:8000/api/diagnostics/runtime
curl http://127.0.0.1:8000/api/diagnostics/e2e-status
```

CLI 실행:

```bash
scripts/run_diagnostics.sh
python3 examples/integration/run_diagnostics.py --pretty
python3 examples/integration/run_diagnostics.py --base-url http://127.0.0.1:8000
```

진단 항목:

- Backend health
- Security diagnostics
- LLM, Market Data, Risk Event, Telegram, Webhook provider 상태
- Runtime 정보
- E2E script 사용 가능 여부
- `order_execution_allowed=false`
- `simulation_only=true` 확인
- Secret/API key/token 값 비노출

보안 정책:

- Diagnostics API는 `.env` 내용을 읽거나 반환하지 않습니다.
- Telegram token, Webhook secret, 외부 provider key는 configured 여부만 boolean으로 표시합니다.
- E2E는 API에서 자동 실행하지 않습니다. 긴 점검은 CLI `scripts/run_full_e2e.sh`로 실행합니다.
- Diagnostics는 브로커 API에 연결하지 않고, 실제 주문 생성/전송/승인/취소/실행을 수행하지 않습니다.

## Phase 24B US Trader Oracle Read-only Bridge

Phase 24B는 Oracle에서 실행 중인 US Trader 운영본을 직접 수정하지 않고, AI Council 쪽에서 payload 호환성을 확인하는 read-only bridge를 추가합니다.

추가 파일:

- `examples/external_bot/mapping_profiles/us_trader_oracle_v1.json`
- `examples/external_bot/us_trader_oracle_bridge.py`
- `examples/external_bot/sample_payloads/us_trader_oracle_*.json`
- `examples/integration/run_us_trader_oracle_bridge_smoke.py`
- `scripts/run_us_trader_oracle_bridge_smoke.sh`
- `docs/US_TRADER_ORACLE_READONLY_INTEGRATION.md`

Normalize preview:

```bash
cd ~/AI-council
python3 examples/external_bot/us_trader_oracle_bridge.py \
  --payload examples/external_bot/sample_payloads/us_trader_oracle_signal.json \
  --profile us_trader_oracle_v1 \
  --preview \
  --pretty
```

Dry-run:

```bash
python3 examples/external_bot/us_trader_oracle_bridge.py \
  --payload examples/external_bot/sample_payloads/us_trader_oracle_order_like_signal.json \
  --profile us_trader_oracle_v1 \
  --dry-run \
  --pretty
```

Smoke test:

```bash
scripts/run_us_trader_oracle_bridge_smoke.sh
```

`buy`, `sell`, `entry`, `exit` 같은 값은 주문 의도가 아니라 검토용 context로만 저장됩니다. `quantity`, `order_type`, `stop_loss`, `take_profit`, `broker`, `account` 같은 order-like field는 raw payload에는 보존되지만 adapter warning으로 기록되고 주문 로직으로 연결되지 않습니다.

Oracle live bot, systemd service, secret/config 파일은 AI Council bridge가 수정하지 않습니다. 실제 Oracle host, SSH key path, secret/API key/token 값은 README에 하드코딩하지 않습니다.

이 기능은 브로커 API에 연결하지 않고, 실제 주문 생성/전송/승인/취소/실행을 수행하지 않습니다. `order_execution_allowed`는 항상 `false`입니다.

## Phase 24C Oracle Sidecar Signal Bridge Plan

Phase 24C는 Oracle live bot을 직접 수정하거나 재시작하지 않고, 향후 signal JSON outbox를 통해 AI Council로 read-only review를 보낼 수 있는 sidecar 구조와 샘플을 추가합니다.

추가 파일:

- `examples/oracle_sidecar/us_trader_signal_outbox_bridge.py`
- `examples/oracle_sidecar/signal_exporter_hook_example.py`
- `examples/oracle_sidecar/sample_outbox/*.json`
- `examples/integration/run_oracle_sidecar_smoke.py`
- `scripts/run_oracle_sidecar_smoke.sh`
- `docs/US_TRADER_ORACLE_SIDECAR_PLAN.md`

Dry-run:

```bash
cd ~/AI-council
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --dry-run \
  --pretty
```

Preview mode:

```bash
python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \
  --outbox examples/oracle_sidecar/sample_outbox \
  --mode preview \
  --pretty
```

Smoke test:

```bash
scripts/run_oracle_sidecar_smoke.sh
```

Review-only mode는 명시적으로 `--mode review`를 줄 때만 AI Council `/api/webhooks/trade-signal`로 전송합니다. 이 경우에도 실제 주문이 아니라 AI Council trade review 생성만 수행합니다.

Sidecar 원칙:

- Oracle live bot 직접 수정 없음
- Oracle systemd service 조작 없음
- 브로커 API 연결 없음
- 실제 주문 생성/전송/승인/취소/실행 없음
- outbox JSON과 state file 기반 중복 방지
- order-like fields는 adapter warning으로만 처리
- `order_execution_allowed=false`

## Phase 24D Oracle Export Hook Patch Draft

Phase 24D는 Oracle US Trader 운영봇을 바로 수정하지 않고, 나중에 안전하게 signal export hook을 삽입하기 위한 patch draft, preflight script, 적용 checklist를 추가합니다.

추가 파일:

- `docs/US_TRADER_ORACLE_EXPORT_HOOK_PATCH_DRAFT.md`
- `examples/oracle_sidecar/patch_drafts/`
- `examples/oracle_sidecar/oracle_export_hook_preflight.py`
- `scripts/run_oracle_export_hook_preflight.sh`

Preflight 실행:

```bash
cd ~/AI-council
scripts/run_oracle_export_hook_preflight.sh
```

Patch draft 원칙:

- Oracle live bot 직접 수정 없음
- `penny_stock_bot.py`에 자동 적용하지 않음
- `place_order`, `check_exits`, `force_close_all` 내부에 hook 금지
- exporter module은 outbox JSON 파일만 atomic write
- HTTP 전송과 review 생성은 sidecar bridge가 담당
- 기본 검증은 preview-only
- 실제 주문 실행 없음
- 브로커 API 연결 없음
- `order_execution_allowed=false`

## Phase 24E Oracle Staging Patch Rehearsal

Phase 24E는 Oracle 운영봇을 직접 수정하지 않고, 로컬 스테이징 복사본 또는 fixture에서 export hook patch preview를 리허설하는 도구를 추가합니다.

추가 파일:

- `examples/oracle_staging/analyze_us_trader_bot.py`
- `examples/oracle_staging/prepare_staging_rehearsal.py`
- `examples/oracle_staging/generate_export_hook_patch_preview.py`
- `examples/oracle_staging/validate_staging_patch.py`
- `examples/oracle_staging/fixtures/`
- `docs/US_TRADER_ORACLE_STAGING_REHEARSAL.md`
- `scripts/run_oracle_staging_rehearsal.sh`

전체 리허설:

```bash
cd ~/AI-council
scripts/run_oracle_staging_rehearsal.sh
```

리허설 흐름:

1. staging copy 생성
2. 함수 위치 정적 분석
3. patch preview diff 생성
4. patched preview file 생성
5. patched preview 정적 검증
6. export hook preflight 실행

Patch preview는 운영본에 적용하지 않습니다. 생성물은 임시 staging output에만 만들어지며 Git에 포함하지 않습니다.

안전 원칙:

- Oracle live bot 직접 수정 없음
- 로컬 백업 원본 직접 수정 없음
- Oracle systemd service 조작 없음
- 브로커 API 연결 없음
- 실제 주문 실행 없음
- `place_order/check_exits/force_close_all` 내부 hook 삽입 금지
- `order_execution_allowed=false`

## Phase 24F Oracle Deployment Bundle Approval Gate

Phase 24F는 Oracle 운영봇에 signal export hook을 실제 적용하기 전, 사람이 수동으로 검토하고 승인할 수 있는 deployment bundle, readiness dry-run, manual approval gate, deployment runbook을 추가합니다.

추가 파일:

- `examples/oracle_deployment/build_signal_export_bundle.py`
- `examples/oracle_deployment/verify_signal_export_bundle.py`
- `examples/oracle_deployment/oracle_readiness_check.py`
- `examples/oracle_deployment/templates/`
- `docs/US_TRADER_ORACLE_MANUAL_APPROVAL_GATE.md`
- `docs/US_TRADER_ORACLE_DEPLOYMENT_RUNBOOK.md`
- `scripts/build_oracle_signal_export_bundle.sh`
- `scripts/verify_oracle_signal_export_bundle.sh`
- `scripts/run_oracle_readiness_check_dryrun.sh`

로컬 bundle 생성:

```bash
cd ~/AI-council
scripts/build_oracle_signal_export_bundle.sh
```

bundle 검증:

```bash
scripts/verify_oracle_signal_export_bundle.sh
```

Oracle readiness dry-run:

```bash
scripts/run_oracle_readiness_check_dryrun.sh
```

Phase 24F의 기본 원칙:

- deployment bundle은 `tmp/oracle_signal_export_bundle/`에 생성되며 Git에 포함하지 않음
- readiness check 기본값은 SSH 없이 command preview만 출력
- 실제 Oracle 적용은 별도 수동 승인 전까지 하지 않음
- systemd start/stop/restart 자동 실행 없음
- Oracle live bot 직접 수정 없음
- 브로커 API 연결 없음
- 실제 주문 실행 없음
- `order_execution_allowed=false`

## 테스트

```bash
cd ~/AI-council/backend
../.venv/bin/python -m pytest
```

Frontend build:

```bash
cd ~/AI-council/frontend
npm run build
```

## Git에 포함하면 안 되는 파일

다음 파일과 산출물은 Git에 포함하지 않습니다.

- `.env`
- `.env.local`
- `.venv/`
- `node_modules/`
- `frontend/dist/`
- `backend/data/*.sqlite`
- `backend/data/uploads/`
- `data/uploads/`
- `reports/*.md`
- `data/reports/*.md`
- `__pycache__/`

## 안전 경계

AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.

구현 금지 범위:

- 실제 브로커 API 연결
- 매수/매도 주문 생성
- 주문 전송
- 주문 승인
- 주문 취소
- 포지션 변경
- 자동매매 실행

외부 봇 연동은 후보 신호를 받아 검토 결과를 반환하는 용도입니다. `trade_allowed`는 분석상 판단 메타데이터일 뿐이며, 실제 주문 실행 허가가 아닙니다. `order_execution_allowed`는 항상 `false`입니다.
