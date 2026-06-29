from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .council import run_mock_council
from .database import DEFAULT_DB_PATH, init_db
from .reports import DEFAULT_REPORT_DIR, write_markdown_report
from .repository import (
    create_meeting,
    get_meeting,
    get_meeting_outputs,
    get_report,
    list_agents,
    list_meetings,
    replace_meeting_outputs,
    upsert_report,
)
from .schemas import MeetingCreate, MeetingRunResponse
from .seed import seed_agents


def create_app(
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
) -> FastAPI:
    resolved_db_path = Path(db_path or DEFAULT_DB_PATH)
    resolved_report_dir = Path(report_dir or DEFAULT_REPORT_DIR)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(resolved_db_path)
        seed_agents(resolved_db_path)
        yield

    app = FastAPI(title="AI Council", version="0.1.0", lifespan=lifespan)
    app.state.db_path = resolved_db_path
    app.state.report_dir = resolved_report_dir

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _meeting_or_404(meeting_id: str) -> dict:
        meeting = get_meeting(meeting_id, app.state.db_path)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        return meeting

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "AI Council",
            "mode": "phase_1_mock",
            "database": "sqlite",
        }

    @app.get("/api/agents")
    def get_agents() -> list[dict]:
        return list_agents(app.state.db_path)

    @app.get("/api/meetings")
    def get_meetings() -> list[dict]:
        return list_meetings(app.state.db_path)

    @app.post("/api/meetings", status_code=201)
    def post_meeting(payload: MeetingCreate) -> dict:
        topic = payload.topic.strip()
        if not topic:
            raise HTTPException(status_code=422, detail="Topic is required")
        ticker = payload.ticker.strip().upper() if payload.ticker else None
        if ticker == "":
            ticker = None
        return create_meeting(topic=topic, ticker=ticker, db_path=app.state.db_path)

    @app.get("/api/meetings/{meeting_id}")
    def get_meeting_detail(meeting_id: str) -> dict:
        meeting = _meeting_or_404(meeting_id)
        outputs = get_meeting_outputs(meeting_id, app.state.db_path)
        report = get_report(meeting_id, app.state.db_path)
        return {
            "meeting": meeting,
            "outputs": outputs,
            "report": {
                "available": report is not None,
                "path": report["path"] if report else None,
            },
        }

    @app.post("/api/meetings/{meeting_id}/run", response_model=MeetingRunResponse)
    def run_meeting(meeting_id: str) -> dict:
        meeting = _meeting_or_404(meeting_id)
        agents = list_agents(app.state.db_path)
        council_run = run_mock_council(meeting, agents)
        replace_meeting_outputs(
            meeting_id=meeting_id,
            outputs=council_run.outputs,
            trade_review=council_run.trade_review,
            db_path=app.state.db_path,
        )
        updated_meeting = _meeting_or_404(meeting_id)
        outputs = get_meeting_outputs(meeting_id, app.state.db_path)
        report_path, markdown = write_markdown_report(
            updated_meeting,
            outputs,
            app.state.report_dir,
        )
        report = upsert_report(meeting_id, report_path, markdown, app.state.db_path)
        return {
            "meeting": updated_meeting,
            "outputs": outputs,
            "report": {
                "available": True,
                "path": report["path"],
                "created_at": report["created_at"],
            },
        }

    @app.get("/api/meetings/{meeting_id}/report")
    def get_meeting_report(meeting_id: str) -> Response:
        _meeting_or_404(meeting_id)
        report = get_report(meeting_id, app.state.db_path)
        if not report:
            raise HTTPException(status_code=404, detail="Report has not been generated")
        return Response(
            content=report["markdown"],
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'inline; filename="meeting_{meeting_id}.md"',
            },
        )

    return app


app = create_app()

