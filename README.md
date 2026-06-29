# AI Council

AI Council is a local mock-based web program where multiple AI-style agents review one topic, challenge each other, and produce a final chairperson summary.

Phase 1 is intentionally limited to analysis and review:

- No live stock prices
- No live news APIs
- No broker APIs
- No order placement
- No automated trading execution

The backend keeps a `trade_review` structure so a future trading bot can request analysis through a separate Risk Gate, but Phase 1 never executes trades.

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
