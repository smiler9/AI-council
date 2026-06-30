# AI Council

AI Council is a local mock-based web program where multiple AI-style agents review one topic, challenge each other, and produce a final chairperson summary.

Phase 1 is intentionally limited to analysis and review:

- No live stock prices
- No live news APIs
- No broker APIs
- No order placement
- No automated trading execution

The backend keeps a `trade_review` structure so a future trading bot can request analysis through a separate Risk Gate, but Phase 1 never executes trades.

Phase 2 adds an LLM provider abstraction while keeping `mock` as the default. AI Council remains a review, risk analysis, and decision-support layer only. Broker APIs and automated order execution are still not implemented.

Phase 3 adds meeting context files. Uploaded files are parsed into summaries and included as council context for mock or LLM-backed meetings. The system can review uploaded trading-related material, but it still does not connect to brokers or execute orders.

Phase 4 adds a debate engine and structured decision output. Meetings now run through explicit debate rounds and produce a JSON decision schema for review-only risk assessment. Future auto-trading integration remains decision-support only in this phase.

Phase 5 adds optional Telegram report delivery. Telegram is disabled by default and is used only for notification and report delivery, never for broker access or order execution.

Phase 6 verifies local LLM integration against OpenAI-compatible endpoints such as Ollama and vLLM. The default provider remains `mock`; local LLM failures are recorded safely and do not enable broker access or order execution.

Phase 7 adds a read-only Trade Signal Review API. External bots can submit candidate penny-stock signals for AI Council review, risk analysis, and structured decision support. The API never connects to brokers and never creates, sends, routes, or executes orders.

Phase 8 adds a read-only external bot webhook receiver and input adapter. Webhooks are disabled by default, support a shared secret header, normalize common bot payload aliases, and reuse the Phase 7 Trade Signal Review engine.

## Structure

```text
AI-council/
  backend/      FastAPI + SQLite API
  frontend/     React + Vite UI
  reports/      generated Markdown meeting reports
```

## Backend

```bash
cd ~/AI-council/backend
python3 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements.txt
../.venv/bin/python -m uvicorn app.main:app --reload
```

Backend URL: `http://127.0.0.1:8000`

## Frontend

```bash
cd ~/AI-council/frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

## Phase 2 LLM Providers

Supported provider names:

- `mock`
- `local_openai_compatible`
- `openai_stub`
- `anthropic_stub`
- `gemini_stub`

Implemented in Phase 2:

- `mock`: deterministic local responses, used by default.
- `local_openai_compatible`: calls `/chat/completions` on a local OpenAI-compatible API such as Ollama or vLLM.

Stub only:

- `openai_stub`
- `anthropic_stub`
- `gemini_stub`

The stub providers do not call external APIs. They exist only to keep the extension boundary explicit.

Default `.env`:

```bash
LLM_PROVIDER=mock
```

Local LLM example:

```bash
LLM_PROVIDER=local_openai_compatible
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3-coder:30b
LLM_API_KEY=local
LLM_TIMEOUT_SECONDS=60
LLM_MAX_TOKENS=1200
```

Run with local settings:

```bash
cd ~/AI-council/backend
LLM_PROVIDER=local_openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_MODEL=qwen3-coder:30b \
LLM_API_KEY=local \
LLM_TIMEOUT_SECONDS=60 \
LLM_MAX_TOKENS=1200 \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Provider responses are stored as structured JSON with the agent output. If a provider fails, the meeting is marked `failed`, the error is recorded, and no broker connection or order execution is attempted.

## Phase 3 Context Files

Meeting files can be uploaded from the web UI or API. The backend stores the original file, extracted text, and a context summary under:

```text
data/uploads/{meeting_id}/
```

Supported file types:

- `.txt`
- `.md`
- `.csv`
- `.json`
- `.log`
- `.pdf` is accepted as a Phase 3 stub, stored as `unsupported`, and excluded from evidence-based analysis until a PDF parser is added.

Safety limits:

- Maximum file size: 2MB
- Filenames are sanitized before storage
- Path traversal is prevented by storing files under the controlled upload directory
- Unsupported extensions are rejected
- Binary content is rejected for text-based file types
- Uploaded context is treated as user-provided evidence that still requires validation

API example:

```bash
MEETING_ID="<meeting id>"
curl -F "file=@notes.md" "http://127.0.0.1:8000/api/meetings/${MEETING_ID}/files"
curl "http://127.0.0.1:8000/api/meetings/${MEETING_ID}/files"
curl -X POST "http://127.0.0.1:8000/api/meetings/${MEETING_ID}/run"
```

When a meeting is run, ready file summaries are included in the provider prompt. Reports include `Attached Context Files`, `File Summaries`, and `Context-aware Agent Notes`.

## Phase 4 Debate Engine

Meeting modes:

- `quick_review`
- `deep_debate`
- `skeptic_review`
- `risk_gate_review`
- `action_plan`

Debate rounds:

1. `initial_opinion`: primary agents create first-pass role-specific opinions.
2. `rebuttal`: Skeptic Agent and Risk Manager Agent challenge assumptions and downside.
3. `revision`: primary agents revise notes after rebuttal.
4. `chairman_summary`: Chairman Agent synthesizes consensus, dissent, and risk posture.
5. `structured_decision`: final review-only JSON decision.

Structured decision schema:

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

Decision values: `ALLOW`, `HOLD`, `BLOCK`, `NEED_MORE_DATA`.

Risk levels: `low`, `medium`, `high`, `critical`.

Safety boundary:

> AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

Create a mode-specific meeting:

```bash
curl -X POST "http://127.0.0.1:8000/api/meetings" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Review a high-risk setup","ticker":"RISK","mode":"risk_gate_review"}'
```

## Phase 5 Telegram Notifications

Telegram delivery is disabled by default:

```bash
TELEGRAM_ENABLED=false
```

Enable it with environment variables:

```bash
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<your bot token>
TELEGRAM_CHAT_ID=<your chat id>
TELEGRAM_TIMEOUT_SECONDS=10
```

Do not commit real bot tokens or chat IDs. Keep secrets in a local `.env` or shell environment only. The repository `.gitignore` excludes `.env`.

Send a completed meeting report:

```bash
curl -X POST "http://127.0.0.1:8000/api/meetings/${MEETING_ID}/telegram/send"
```

Check Telegram configuration status:

```bash
curl "http://127.0.0.1:8000/api/telegram/status"
```

Telegram messages include the meeting title, mode, structured decision, confidence, risk level, risk flags, required follow-up, report path, and safety boundary. Telegram delivery is report-only and does not connect to broker APIs or execute orders.

## Phase 6 Local LLM Verification

AI Council can use a local OpenAI-compatible LLM server for agent responses while keeping the same debate engine, structured decision schema, and safety boundary.

Default safe mode:

```bash
LLM_PROVIDER=mock
```

Check for an Ollama OpenAI-compatible endpoint:

```bash
curl "http://localhost:11434/v1/models"
```

Run the backend with Ollama:

```bash
cd ~/AI-council/backend
LLM_PROVIDER=local_openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_MODEL=qwen3:8b \
LLM_API_KEY=local \
LLM_TIMEOUT_SECONDS=60 \
LLM_MAX_TOKENS=1200 \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Check for a vLLM OpenAI-compatible endpoint:

```bash
curl "http://localhost:8000/v1/models"
```

Run the backend with vLLM:

```bash
cd ~/AI-council/backend
LLM_PROVIDER=local_openai_compatible \
LLM_BASE_URL=http://localhost:8000/v1 \
LLM_MODEL=<served-model-name> \
LLM_API_KEY=local \
LLM_TIMEOUT_SECONDS=60 \
LLM_MAX_TOKENS=1200 \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Use the API as usual:

```bash
curl -X POST "http://127.0.0.1:8000/api/meetings" \
  -H "Content-Type: application/json" \
  -d '{"topic":"Verify local LLM review","ticker":"LLM","mode":"deep_debate"}'

curl -X POST "http://127.0.0.1:8000/api/meetings/${MEETING_ID}/run"
```

If the local LLM server is not running, or if it returns invalid JSON, the meeting is marked `failed`, the provider error is stored in the meeting output and trade review metadata, and `order_execution_allowed` remains `false`.

For Ollama Qwen thinking models, the local provider sends a `/no_think` directive and a `max_tokens` cap so the final JSON response is returned in `message.content`. Raw provider metadata is stored without saving reasoning text.

Return to mock mode:

```bash
LLM_PROVIDER=mock
```

Safety boundary:

> AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## Phase 7 Trade Signal Review API

The Trade Signal Review API accepts candidate signals from an external scanner or automation bot as read-only context. It creates an internal `risk_gate_review` meeting, runs the same AI Council debate engine, stores a `trade_reviews` record, and returns the structured decision.

Endpoints:

- `POST /api/trade-reviews`
- `GET /api/trade-reviews`
- `GET /api/trade-reviews/{trade_review_id}`
- `POST /api/trade-reviews/{trade_review_id}/telegram/send`

Example request:

```bash
curl -X POST "http://127.0.0.1:8000/api/trade-reviews" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "ABCD",
    "strategy_signal": "breakout",
    "side": "watch_only",
    "price": 0.82,
    "volume": 12500000,
    "timeframe": "1m",
    "source": "external_bot",
    "notes": "candidate signal generated by existing bot",
    "technical_indicators": {
      "rsi": 68,
      "vwap_distance": 0.04
    },
    "news_headlines": [],
    "risk_context": {
      "spread_pct": 4.5,
      "float_rotation": 2.1,
      "premarket": true
    }
  }'
```

Example response shape:

```json
{
  "trade_review": {
    "id": "...",
    "ticker": "ABCD",
    "strategy_signal": "breakout",
    "side": "watch_only",
    "decision": "HOLD",
    "risk_level": "high",
    "trade_allowed": false,
    "order_execution_allowed": false,
    "linked_meeting_id": "..."
  },
  "structured_decision": {
    "decision": "HOLD",
    "confidence": 0.72,
    "risk_level": "high",
    "trade_allowed": false,
    "position_size_multiplier": 0.0,
    "primary_reasons": [],
    "risk_flags": [],
    "required_follow_up": [],
    "data_quality": "limited",
    "order_execution_allowed": false
  },
  "order_execution_allowed": false
}
```

Safety rules:

- `side` is stored as review context only. Values such as `buy` or `sell` do not trigger order behavior.
- High spreads add spread risk flags and result in `HOLD` or `BLOCK`.
- Low or missing volume results in additional evidence gaps or risk flags.
- Premarket signals add a premarket risk flag.
- Missing news headlines mark data quality as `limited`.
- `order_execution_allowed` is always `false`.

Telegram delivery for trade reviews is optional and disabled by default. With `TELEGRAM_ENABLED=false`, the send endpoint returns a safe disabled response.

Safety boundary:

> AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## Phase 8 External Bot Webhooks

The webhook receiver lets an external penny-stock scanner or automation bot submit candidate signals to AI Council. It is a review intake endpoint only. It does not accept order instructions, connect to brokers, approve orders, cancel orders, or execute trades.

Environment defaults:

```bash
WEBHOOKS_ENABLED=false
WEBHOOK_SECRET=change-me
WEBHOOK_REQUIRE_SECRET=true
```

Endpoint:

```text
POST /api/webhooks/trade-signal
```

Status and event APIs:

- `GET /api/webhooks/status`
- `GET /api/webhooks/events`
- `GET /api/webhooks/events/{event_id}`

When enabled with a required secret, send the shared secret in this header:

```text
X-AI-Council-Webhook-Secret: <your local secret>
```

Example webhook request:

```bash
curl -X POST "http://127.0.0.1:8000/api/webhooks/trade-signal" \
  -H "Content-Type: application/json" \
  -H "X-AI-Council-Webhook-Secret: ${WEBHOOK_SECRET}" \
  -d '{
    "source": "external_penny_bot",
    "signal_id": "sig_20260630_001",
    "ticker": "ABCD",
    "strategy_signal": "breakout",
    "side": "buy",
    "price": 0.82,
    "volume": 12500000,
    "timeframe": "1m",
    "timestamp": "2026-06-30T09:35:00Z",
    "technical_indicators": {
      "rsi": 68,
      "vwap_distance": 0.04,
      "relative_volume": 5.2
    },
    "news_headlines": [],
    "risk_context": {
      "spread_pct": 4.5,
      "float_rotation": 2.1,
      "premarket": true
    },
    "notes": "candidate generated by external bot"
  }'
```

Supported aliases:

- `ticker` or `symbol`
- `strategy_signal` or `signal` or `setup`
- `price` or `last_price`
- `volume` or `current_volume`
- `timeframe` or `interval`
- `technical_indicators` or `indicators`
- `news_headlines` or `headlines`
- `risk_context` or `risk`
- `timestamp` or `event_time`

Example normalized output:

```json
{
  "ticker": "ABCD",
  "strategy_signal": "breakout",
  "side": "buy",
  "price": 0.82,
  "volume": 12500000,
  "timeframe": "1m",
  "source": "external_penny_bot",
  "technical_indicators": {
    "rsi": 68,
    "vwap_distance": 0.04,
    "relative_volume": 5.2
  },
  "news_headlines": [],
  "risk_context": {
    "spread_pct": 4.5,
    "float_rotation": 2.1,
    "premarket": true,
    "event_time": "2026-06-30T09:35:00Z",
    "signal_id": "sig_20260630_001"
  },
  "order_execution_allowed": false
}
```

Idempotency:

- `source + signal_id` is unique.
- If the same signal is received again, AI Council returns the existing `trade_review_id`.
- Duplicate requests do not create a new meeting or a new trade review.

Telegram option:

- Add `?auto_send_telegram=true` or `"auto_send_telegram": true` to request report delivery.
- If Telegram is disabled, the response includes a safe disabled result.
- Telegram is reporting-only and is not connected to trading or order systems.

Safety boundary:

> AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.

## Tests

```bash
cd ~/AI-council/backend
../.venv/bin/python -m pytest
```

## API

- `GET /health`
- `GET /api/agents`
- `GET /api/meetings`
- `POST /api/meetings` accepts optional `mode`
- `GET /api/meetings/{meeting_id}` includes `messages` and `structured_decision`
- `GET /api/telegram/status`
- `POST /api/trade-reviews`
- `GET /api/trade-reviews`
- `GET /api/trade-reviews/{trade_review_id}`
- `POST /api/trade-reviews/{trade_review_id}/telegram/send`
- `GET /api/webhooks/status`
- `POST /api/webhooks/trade-signal`
- `GET /api/webhooks/events`
- `GET /api/webhooks/events/{event_id}`
- `POST /api/meetings/{meeting_id}/files`
- `GET /api/meetings/{meeting_id}/files`
- `POST /api/meetings/{meeting_id}/run`
- `POST /api/meetings/{meeting_id}/telegram/send`
- `GET /api/meetings/{meeting_id}/report`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
