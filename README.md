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
- `POST /api/trade-reviews`
- `GET /api/trade-reviews`
- `GET /api/trade-reviews/{trade_review_id}`
- `POST /api/trade-reviews/{trade_review_id}/telegram/send`
- `GET /api/webhooks/status`
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

- `ticker` 또는 `symbol`
- `strategy_signal` 또는 `signal` 또는 `setup`
- `price` 또는 `last_price`
- `volume` 또는 `current_volume`
- `timeframe` 또는 `interval`
- `technical_indicators` 또는 `indicators`
- `news_headlines` 또는 `headlines`
- `risk_context` 또는 `risk`
- `timestamp` 또는 `event_time`

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
