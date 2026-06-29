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
```

Run with local settings:

```bash
cd ~/AI-council/backend
LLM_PROVIDER=local_openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_MODEL=qwen3-coder:30b \
LLM_API_KEY=local \
LLM_TIMEOUT_SECONDS=60 \
../.venv/bin/python -m uvicorn app.main:app --reload
```

Provider responses are stored as structured JSON with the agent output. If a provider fails, the meeting is marked `failed`, the error is recorded, and no broker connection or order execution is attempted.

## Tests

```bash
cd ~/AI-council/backend
../.venv/bin/python -m pytest
```

## API

- `GET /health`
- `GET /api/agents`
- `GET /api/meetings`
- `POST /api/meetings`
- `GET /api/meetings/{meeting_id}`
- `POST /api/meetings/{meeting_id}/run`
- `GET /api/meetings/{meeting_id}/report`
