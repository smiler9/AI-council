from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Body, FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .autonomous_reviews import run_autonomous_review, send_autonomous_review_telegram
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
from .market_data import MarketDataConfig, get_market_data_provider, load_market_data_config
from .reports import DEFAULT_REPORT_DIR, write_markdown_report
from .risk_events import (
    RiskEventConfig,
    detect_risk_events,
    get_news_provider,
    get_sec_filing_provider,
    load_risk_event_config,
    risk_event_status,
)
from .repository import (
    create_context_file,
    create_webhook_event,
    create_meeting,
    delete_context_file,
    get_context_file,
    get_meeting,
    get_meeting_messages,
    get_meeting_outputs,
    get_report,
    get_trade_review,
    get_watchlist,
    get_watchlist_review,
    get_webhook_event,
    get_webhook_event_by_source_signal,
    list_agents,
    list_context_files,
    list_meetings,
    list_trade_reviews,
    list_watchlist_reviews,
    list_watchlists,
    list_webhook_events,
    replace_meeting_outputs,
    create_watchlist,
    update_watchlist,
    delete_watchlist,
    update_webhook_event,
    upsert_report,
)
from .schemas import (
    AutonomousReviewCreate,
    MeetingCreate,
    MeetingRunResponse,
    TickerReviewCreate,
    TradeReviewCreate,
    WatchlistCreate,
    WatchlistUpdate,
)
from .seed import seed_agents
from .services.telegram_service import (
    TelegramConfig,
    TelegramService,
    load_telegram_config,
)
from .ticker_reviews import run_ticker_review
from .trade_reviews import run_trade_review
from .watchlists import (
    WatchlistInputError,
    format_watchlist_review_response,
    normalize_tickers,
    run_watchlist_review,
    send_watchlist_review_telegram,
)
from .webhooks import (
    WEBHOOK_SECRET_HEADER,
    WebhookConfig,
    WebhookInputError,
    auto_send_requested,
    load_webhook_config,
    normalize_trade_signal_payload,
    validate_webhook_secret,
    webhook_identity,
    webhook_status,
)


def create_app(
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
    upload_root: str | Path | None = None,
    llm_config: LLMConfig | None = None,
    telegram_config: TelegramConfig | None = None,
    webhook_config: WebhookConfig | None = None,
    market_data_config: MarketDataConfig | None = None,
    risk_event_config: RiskEventConfig | None = None,
) -> FastAPI:
    resolved_db_path = Path(db_path or DEFAULT_DB_PATH)
    resolved_report_dir = Path(report_dir or DEFAULT_REPORT_DIR)
    resolved_upload_root = Path(upload_root or UPLOAD_ROOT)
    resolved_llm_config = llm_config or load_llm_config()
    resolved_telegram_config = telegram_config or load_telegram_config()
    resolved_webhook_config = webhook_config or load_webhook_config()
    resolved_market_data_config = market_data_config or load_market_data_config()
    resolved_risk_event_config = risk_event_config or load_risk_event_config()

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
    app.state.telegram_config = resolved_telegram_config
    app.state.webhook_config = resolved_webhook_config
    app.state.market_data_config = resolved_market_data_config
    app.state.risk_event_config = resolved_risk_event_config

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

    def _trade_review_or_404(trade_review_id: str) -> dict:
        trade_review = get_trade_review(trade_review_id, app.state.db_path)
        if not trade_review:
            raise HTTPException(status_code=404, detail="Trade review not found")
        return trade_review

    def _webhook_event_or_404(event_id: str) -> dict:
        event = get_webhook_event(event_id, app.state.db_path)
        if not event:
            raise HTTPException(status_code=404, detail="Webhook event not found")
        return event

    def _watchlist_or_404(watchlist_id: str) -> dict:
        watchlist = get_watchlist(watchlist_id, app.state.db_path)
        if not watchlist:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        return watchlist

    def _watchlist_review_or_404(review_id: str) -> dict:
        review = get_watchlist_review(review_id, app.state.db_path)
        if not review:
            raise HTTPException(status_code=404, detail="Watchlist review not found")
        return review

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "service": "AI Council",
            "mode": "phase_1_mock",
            "database": "sqlite",
            "llm_provider": app.state.llm_config.provider,
            "market_data": {
                "provider": app.state.market_data_config.provider,
                "timeout_seconds": app.state.market_data_config.timeout_seconds,
                "external_enabled": app.state.market_data_config.allow_external,
                "order_execution_allowed": False,
            },
            "autonomous_review": {
                "enabled": True,
                "candidate_provider": "mock_market_data",
                "order_execution_allowed": False,
            },
            "risk_events": risk_event_status(app.state.risk_event_config),
            "telegram": TelegramService(app.state.telegram_config).status(),
            "webhooks": webhook_status(app.state.webhook_config),
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
        return create_meeting(
            topic=topic,
            ticker=ticker,
            db_path=app.state.db_path,
            mode=payload.mode,
        )

    @app.get("/api/meetings/{meeting_id}")
    def get_meeting_detail(meeting_id: str) -> dict:
        meeting = _meeting_or_404(meeting_id)
        outputs = get_meeting_outputs(meeting_id, app.state.db_path)
        messages = get_meeting_messages(meeting_id, app.state.db_path)
        report = get_report(meeting_id, app.state.db_path)
        files = list_context_files(meeting_id, app.state.db_path)
        return {
            "meeting": meeting,
            "outputs": outputs,
            "messages": messages,
            "structured_decision": meeting.get("structured_decision", {}),
            "files": files,
            "report": {
                "available": report is not None,
                "path": report["path"] if report else None,
            },
        }

    @app.get("/api/telegram/status")
    def get_telegram_status() -> dict:
        return TelegramService(app.state.telegram_config).status()

    @app.get("/api/market-data/status")
    def get_market_data_status() -> dict:
        provider = get_market_data_provider(app.state.market_data_config)
        return provider.status(app.state.market_data_config)

    @app.get("/api/market-data/quote/{ticker}")
    def get_market_data_quote(ticker: str) -> dict:
        provider = get_market_data_provider(app.state.market_data_config)
        return provider.quote(ticker)

    @app.get("/api/market-data/snapshot/{ticker}")
    def get_market_data_snapshot(ticker: str) -> dict:
        provider = get_market_data_provider(app.state.market_data_config)
        return provider.snapshot(ticker)

    @app.get("/api/market-data/news/{ticker}")
    def get_market_data_news(ticker: str) -> dict:
        provider = get_market_data_provider(app.state.market_data_config)
        return provider.news(ticker)

    @app.get("/api/market-data/filings/{ticker}")
    def get_market_data_filings(ticker: str) -> dict:
        provider = get_market_data_provider(app.state.market_data_config)
        return provider.filings(ticker)

    @app.get("/api/risk-events/status")
    def get_risk_event_status() -> dict:
        return risk_event_status(app.state.risk_event_config)

    @app.get("/api/risk-events/news/{ticker}")
    def get_risk_event_news(ticker: str) -> dict:
        provider = get_news_provider(app.state.risk_event_config)
        return provider.news(ticker)

    @app.get("/api/risk-events/filings/{ticker}")
    def get_risk_event_filings(ticker: str) -> dict:
        provider = get_sec_filing_provider(app.state.risk_event_config)
        return provider.filings(ticker)

    @app.get("/api/risk-events/detect/{ticker}")
    def get_risk_event_detection(ticker: str) -> dict:
        return detect_risk_events(ticker, app.state.risk_event_config)

    @app.get("/api/webhooks/status")
    def get_webhook_status() -> dict:
        status = webhook_status(app.state.webhook_config)
        return {
            **status,
            "endpoint": status["endpoint_path"],
        }

    @app.get("/api/webhooks/events")
    def get_webhook_events() -> list[dict]:
        return list_webhook_events(app.state.db_path)

    @app.get("/api/webhooks/events/{event_id}")
    def get_webhook_event_detail(event_id: str) -> dict:
        event = _webhook_event_or_404(event_id)
        trade_review = (
            get_trade_review(event["trade_review_id"], app.state.db_path)
            if event.get("trade_review_id")
            else None
        )
        return {
            "event": event,
            "trade_review": trade_review,
            "order_execution_allowed": False,
        }

    @app.post("/api/webhooks/trade-signal")
    def post_trade_signal_webhook(
        raw_payload: dict = Body(...),
        auto_send_telegram: bool = Query(False),
        webhook_secret: str | None = Header(default=None, alias=WEBHOOK_SECRET_HEADER),
    ) -> JSONResponse:
        status = webhook_status(app.state.webhook_config)
        if not status["configured"]:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "disabled",
                    "detail": status["disabled_reason"],
                    "webhook_status": status,
                    "duplicated": False,
                    "order_execution_allowed": False,
                },
            )
        if not validate_webhook_secret(app.state.webhook_config, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

        try:
            normalized = normalize_trade_signal_payload(raw_payload)
        except WebhookInputError as exc:
            source = str(raw_payload.get("source") or "external_webhook")
            signal_id = str(raw_payload.get("signal_id") or f"rejected_{uuid4().hex}")
            event = create_webhook_event(
                source=source,
                signal_id=signal_id,
                event_type="trade_signal",
                raw_payload=raw_payload,
                normalized_payload={},
                status="rejected",
                error_message=str(exc),
                db_path=app.state.db_path,
            )
            return JSONResponse(
                status_code=422,
                content={
                    "status": "rejected",
                    "detail": str(exc),
                    "event": event,
                    "duplicated": False,
                    "order_execution_allowed": False,
                },
            )

        source, signal_id = webhook_identity(normalized)
        existing_event = get_webhook_event_by_source_signal(
            source,
            signal_id,
            app.state.db_path,
        )
        requested_telegram = auto_send_requested(raw_payload, auto_send_telegram)
        if existing_event and existing_event.get("trade_review_id"):
            review = get_trade_review(existing_event["trade_review_id"], app.state.db_path)
            report = get_report(review["linked_meeting_id"], app.state.db_path) if review else None
            telegram_result = (
                TelegramService(app.state.telegram_config).send_trade_review_report(review, report)
                if requested_telegram and review
                else None
            )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "duplicated",
                    "duplicated": True,
                    "event": existing_event,
                    "trade_review": review,
                    "structured_decision": review.get("structured_decision") if review else {},
                    "telegram": telegram_result,
                    "order_execution_allowed": False,
                },
            )

        event = create_webhook_event(
            source=source,
            signal_id=signal_id,
            event_type="trade_signal",
            raw_payload=raw_payload,
            normalized_payload=normalized,
            status="normalized",
            db_path=app.state.db_path,
        )
        try:
            result = run_trade_review(
                TradeReviewCreate(**normalized),
                db_path=app.state.db_path,
                report_dir=app.state.report_dir,
                llm_config=app.state.llm_config,
            )
        except Exception as exc:
            failed_event = update_webhook_event(
                event["id"],
                status="failed",
                error_message=str(exc),
                db_path=app.state.db_path,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "status": "failed",
                    "event": failed_event,
                    "detail": str(exc),
                    "duplicated": False,
                    "order_execution_allowed": False,
                },
            )

        event = update_webhook_event(
            event["id"],
            status="reviewed",
            trade_review_id=result["trade_review"]["id"],
            db_path=app.state.db_path,
        )
        report = get_report(result["trade_review"]["linked_meeting_id"], app.state.db_path)
        telegram_result = (
            TelegramService(app.state.telegram_config).send_trade_review_report(
                result["trade_review"],
                report,
            )
            if requested_telegram
            else None
        )
        return JSONResponse(
            status_code=201,
            content={
                "status": "reviewed",
                "duplicated": False,
                "event": event,
                **result,
                "telegram": telegram_result,
                "order_execution_allowed": False,
            },
        )

    @app.post("/api/trade-reviews", status_code=201)
    def post_trade_review(payload: TradeReviewCreate) -> dict:
        if not payload.ticker.strip():
            raise HTTPException(status_code=422, detail="Ticker is required")
        if not payload.strategy_signal.strip():
            raise HTTPException(status_code=422, detail="Strategy signal is required")
        result = run_trade_review(
            payload,
            db_path=app.state.db_path,
            report_dir=app.state.report_dir,
            llm_config=app.state.llm_config,
        )
        return result

    @app.post("/api/ticker-reviews", status_code=201)
    def post_ticker_review(payload: TickerReviewCreate) -> dict:
        if not payload.ticker.strip():
            raise HTTPException(status_code=422, detail="Ticker is required")
        return run_ticker_review(
            payload,
            db_path=app.state.db_path,
            report_dir=app.state.report_dir,
            llm_config=app.state.llm_config,
            market_data_config=app.state.market_data_config,
            risk_event_config=app.state.risk_event_config,
        )

    @app.post("/api/autonomous-reviews", status_code=201)
    def post_autonomous_review(payload: AutonomousReviewCreate) -> dict:
        return run_autonomous_review(
            payload,
            db_path=app.state.db_path,
            report_dir=app.state.report_dir,
            llm_config=app.state.llm_config,
            market_data_config=app.state.market_data_config,
            risk_event_config=app.state.risk_event_config,
        )

    @app.post("/api/autonomous-reviews/{review_id}/telegram/send")
    def send_autonomous_review_to_telegram(review_id: str) -> dict:
        return send_autonomous_review_telegram(
            review_id,
            db_path=app.state.db_path,
            telegram_service=TelegramService(app.state.telegram_config),
        )

    @app.post("/api/watchlists", status_code=201)
    def post_watchlist(payload: WatchlistCreate) -> dict:
        try:
            tickers = normalize_tickers(payload.tickers)
        except WatchlistInputError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return create_watchlist(
            name=payload.name.strip(),
            description=(payload.description or "").strip() or None,
            tickers=tickers,
            review_mode=payload.review_mode,
            db_path=app.state.db_path,
        )

    @app.get("/api/watchlists")
    def get_watchlists() -> list[dict]:
        return list_watchlists(app.state.db_path)

    @app.get("/api/watchlists/{watchlist_id}")
    def get_watchlist_detail(watchlist_id: str) -> dict:
        return _watchlist_or_404(watchlist_id)

    @app.patch("/api/watchlists/{watchlist_id}")
    def patch_watchlist(watchlist_id: str, payload: WatchlistUpdate) -> dict:
        _watchlist_or_404(watchlist_id)
        update_data = payload.model_dump(exclude_unset=True)
        tickers = None
        if "tickers" in update_data:
            try:
                tickers = normalize_tickers(update_data["tickers"] or [])
            except WatchlistInputError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        updated = update_watchlist(
            watchlist_id,
            name=update_data.get("name", None).strip() if update_data.get("name") else None,
            description=(
                update_data.get("description").strip()
                if isinstance(update_data.get("description"), str)
                else update_data.get("description")
            ),
            tickers=tickers,
            review_mode=update_data.get("review_mode"),
            db_path=app.state.db_path,
        )
        return updated

    @app.delete("/api/watchlists/{watchlist_id}")
    def delete_watchlist_endpoint(watchlist_id: str) -> dict:
        deleted = delete_watchlist(watchlist_id, app.state.db_path)
        if not deleted:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        return {
            "deleted": True,
            "watchlist": deleted,
            "order_execution_allowed": False,
        }

    @app.post("/api/watchlists/{watchlist_id}/run-review", status_code=201)
    def run_watchlist_review_endpoint(watchlist_id: str) -> dict:
        try:
            return run_watchlist_review(
                watchlist_id,
                db_path=app.state.db_path,
                report_dir=app.state.report_dir,
                llm_config=app.state.llm_config,
                market_data_config=app.state.market_data_config,
                risk_event_config=app.state.risk_event_config,
            )
        except WatchlistInputError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/watchlist-reviews")
    def get_watchlist_reviews() -> list[dict]:
        return [
            format_watchlist_review_response(review, get_watchlist(review["watchlist_id"], app.state.db_path))
            for review in list_watchlist_reviews(app.state.db_path)
        ]

    @app.get("/api/watchlist-reviews/{review_id}")
    def get_watchlist_review_detail(review_id: str) -> dict:
        review = _watchlist_review_or_404(review_id)
        watchlist = get_watchlist(review["watchlist_id"], app.state.db_path)
        return format_watchlist_review_response(review, watchlist)

    @app.post("/api/watchlist-reviews/{review_id}/telegram/send")
    def send_watchlist_review_to_telegram(review_id: str) -> dict:
        return send_watchlist_review_telegram(
            review_id,
            db_path=app.state.db_path,
            telegram_service=TelegramService(app.state.telegram_config),
        )

    @app.get("/api/trade-reviews")
    def get_trade_reviews() -> list[dict]:
        return list_trade_reviews(app.state.db_path)

    @app.get("/api/trade-reviews/{trade_review_id}")
    def get_trade_review_detail(trade_review_id: str) -> dict:
        trade_review = _trade_review_or_404(trade_review_id)
        meeting = get_meeting(trade_review["linked_meeting_id"], app.state.db_path)
        report = get_report(trade_review["linked_meeting_id"], app.state.db_path)
        return {
            "trade_review": trade_review,
            "meeting": meeting,
            "report": {
                "available": report is not None,
                "path": report["path"] if report else None,
            },
            "order_execution_allowed": False,
        }

    @app.post("/api/trade-reviews/{trade_review_id}/telegram/send")
    def send_trade_review_telegram(trade_review_id: str) -> dict:
        trade_review = _trade_review_or_404(trade_review_id)
        report = get_report(trade_review["linked_meeting_id"], app.state.db_path)
        result = TelegramService(app.state.telegram_config).send_trade_review_report(
            trade_review,
            report,
        )
        return {
            "trade_review_id": trade_review_id,
            "report_available": report is not None,
            **result,
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
            messages=council_run.messages,
            structured_decision=council_run.structured_decision,
        )
        updated_meeting = _meeting_or_404(meeting_id)
        updated_meeting["context_files"] = files
        updated_meeting["context_summary"] = build_meeting_context_summary(files)
        outputs = get_meeting_outputs(meeting_id, app.state.db_path)
        messages = get_meeting_messages(meeting_id, app.state.db_path)
        report_path, markdown = write_markdown_report(
            updated_meeting,
            outputs,
            app.state.report_dir,
            messages=messages,
        )
        report = upsert_report(meeting_id, report_path, markdown, app.state.db_path)
        telegram_result = None
        telegram_service = TelegramService(app.state.telegram_config)
        if telegram_service.config.auto_send_telegram:
            telegram_result = telegram_service.send_meeting_report(updated_meeting, report)
        return {
            "meeting": updated_meeting,
            "outputs": outputs,
            "messages": messages,
            "structured_decision": council_run.structured_decision,
            "files": files,
            "telegram": telegram_result,
            "report": {
                "available": True,
                "path": report["path"],
                "created_at": report["created_at"],
            },
        }

    @app.post("/api/meetings/{meeting_id}/telegram/send")
    def send_meeting_telegram(meeting_id: str) -> dict:
        meeting = _meeting_or_404(meeting_id)
        report = get_report(meeting_id, app.state.db_path)
        result = TelegramService(app.state.telegram_config).send_meeting_report(meeting, report)
        return {
            "meeting_id": meeting_id,
            "report_available": report is not None,
            **result,
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
