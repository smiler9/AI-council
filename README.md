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
- `POST /api/meetings/{meeting_id}/files`
- `GET /api/meetings/{meeting_id}/files`
- `POST /api/meetings/{meeting_id}/run`
- `GET /api/meetings/{meeting_id}/report`
- `GET /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
