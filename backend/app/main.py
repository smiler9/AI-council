from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .council import build_failed_council_run, run_council
from .database import DEFAULT_DB_PATH, init_db
from .file_context import (
    FileContextError,
    UPLOAD_ROOT,
    build_context_file_record,
    build_meeting_context_summary,
    read_extracted_text,
    remove_context_file_artifacts,
)
from .llm.config import LLMConfig, load_llm_config
from .llm.providers import LLMProviderError, get_llm_provider
from .reports import DEFAULT_REPORT_DIR, write_markdown_report
from .repository import (
    create_context_file,
    create_meeting,
    delete_context_file,
    get_context_file,
    get_meeting,
    get_meeting_outputs,
    get_report,
    list_agents,
    list_context_files,
    list_meetings,
    replace_meeting_outputs,
    upsert_report,
)
from .schemas import MeetingCreate, MeetingRunResponse
from .seed import seed_agents


def create_app(
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
    upload_root: str | Path | None = None,
    llm_config: LLMConfig | None = None,
) -> FastAPI:
    resolved_db_path = Path(db_path or DEFAULT_DB_PATH)
    resolved_report_dir = Path(report_dir or DEFAULT_REPORT_DIR)
    resolved_upload_root = Path(upload_root or UPLOAD_ROOT)
    resolved_llm_config = llm_config or load_llm_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(resolved_db_path)
        seed_agents(resolved_db_path)
        yield

    app = FastAPI(title="AI Council", version="0.1.0", lifespan=lifespan)
    app.state.db_path = resolved_db_path
    app.state.report_dir = resolved_report_dir
    app.state.upload_root = resolved_upload_root
    app.state.llm_config = resolved_llm_config

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
            "llm_provider": app.state.llm_config.provider,
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
        files = list_context_files(meeting_id, app.state.db_path)
        return {
            "meeting": meeting,
            "outputs": outputs,
            "files": files,
            "report": {
                "available": report is not None,
                "path": report["path"] if report else None,
            },
        }

    @app.post("/api/meetings/{meeting_id}/files", status_code=201)
    async def post_meeting_file(meeting_id: str, file: UploadFile = File(...)) -> dict:
        _meeting_or_404(meeting_id)
        data = await file.read()
        try:
            record = build_context_file_record(
                meeting_id=meeting_id,
                filename=file.filename or "",
                data=data,
                upload_root=app.state.upload_root,
            )
        except FileContextError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return create_context_file(record, app.state.db_path)

    @app.get("/api/meetings/{meeting_id}/files")
    def get_meeting_files(meeting_id: str) -> list[dict]:
        _meeting_or_404(meeting_id)
        return list_context_files(meeting_id, app.state.db_path)

    @app.get("/api/files/{file_id}")
    def get_file_detail(file_id: str) -> dict:
        record = get_context_file(file_id, app.state.db_path)
        if not record:
            raise HTTPException(status_code=404, detail="File not found")
        return {
            **record,
            "extracted_text": read_extracted_text(record),
        }

    @app.delete("/api/files/{file_id}")
    def delete_file(file_id: str) -> dict:
        record = delete_context_file(file_id, app.state.db_path)
        if not record:
            raise HTTPException(status_code=404, detail="File not found")
        remove_context_file_artifacts(record, app.state.upload_root)
        return {"deleted": True, "file_id": file_id}

    @app.post("/api/meetings/{meeting_id}/run", response_model=MeetingRunResponse)
    def run_meeting(meeting_id: str) -> dict:
        meeting = _meeting_or_404(meeting_id)
        files = list_context_files(meeting_id, app.state.db_path)
        meeting["context_files"] = files
        meeting["context_summary"] = build_meeting_context_summary(files)
        agents = list_agents(app.state.db_path)
        provider = get_llm_provider(app.state.llm_config)
        try:
            council_run = run_council(meeting, agents, provider)
        except LLMProviderError as exc:
            council_run = build_failed_council_run(
                meeting=meeting,
                agents=agents,
                provider_name=provider.name,
                error=exc,
            )
        replace_meeting_outputs(
            meeting_id=meeting_id,
            outputs=council_run.outputs,
            trade_review=council_run.trade_review,
            db_path=app.state.db_path,
            status=council_run.status,
        )
        updated_meeting = _meeting_or_404(meeting_id)
        updated_meeting["context_files"] = files
        updated_meeting["context_summary"] = build_meeting_context_summary(files)
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
            "files": files,
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
