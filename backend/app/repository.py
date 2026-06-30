from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .database import get_connection


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def list_agents(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, agent_key, name, role, focus, created_at
            FROM agents
            ORDER BY id ASC
            """
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def create_meeting(
    topic: str,
    ticker: str | None,
    db_path: str | Path | None = None,
    mode: str = "quick_review",
) -> dict:
    timestamp = now_iso()
    meeting_id = uuid4().hex
    trade_review = {
        "phase": "phase_1_mock",
        "mock_only": True,
        "order_execution_allowed": False,
        "requires_future_risk_gate": True,
        "review_status": "not_requested",
    }
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO meetings (
                id,
                topic,
                ticker,
                mode,
                status,
                trade_review_json,
                final_decision_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                topic,
                ticker,
                mode,
                "draft",
                json.dumps(trade_review, sort_keys=True),
                "{}",
                timestamp,
                timestamp,
            ),
        )
    return get_meeting(meeting_id, db_path)


def list_meetings(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                m.id,
                m.topic,
                m.ticker,
                m.mode,
                m.status,
                m.trade_review_json,
                m.final_decision_json,
                m.created_at,
                m.updated_at,
                COUNT(o.id) AS output_count,
                CASE WHEN r.id IS NULL THEN 0 ELSE 1 END AS report_available
            FROM meetings m
            LEFT JOIN agent_outputs o ON o.meeting_id = m.id
            LEFT JOIN reports r ON r.meeting_id = m.id
            GROUP BY m.id
            ORDER BY m.created_at DESC
            """
        ).fetchall()
    meetings = []
    for row in rows:
        meeting = row_to_dict(row)
        meeting["trade_review"] = json.loads(meeting.pop("trade_review_json"))
        meeting["structured_decision"] = json.loads(meeting.pop("final_decision_json") or "{}")
        meeting["report_available"] = bool(meeting["report_available"])
        meetings.append(meeting)
    return meetings


def get_meeting(meeting_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                topic,
                ticker,
                mode,
                status,
                trade_review_json,
                final_decision_json,
                created_at,
                updated_at
            FROM meetings
            WHERE id = ?
            """,
            (meeting_id,),
        ).fetchone()
    if row is None:
        return None
    meeting = row_to_dict(row)
    meeting["trade_review"] = json.loads(meeting.pop("trade_review_json"))
    meeting["structured_decision"] = json.loads(meeting.pop("final_decision_json") or "{}")
    return meeting


def get_meeting_outputs(meeting_id: str, db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                meeting_id,
                agent_key,
                agent_name,
                stage,
                stance,
                confidence,
                content,
                provider_name,
                structured_response_json,
                created_at
            FROM agent_outputs
            WHERE meeting_id = ?
            ORDER BY id ASC
            """,
            (meeting_id,),
        ).fetchall()
    outputs = []
    for row in rows:
        output = row_to_dict(row)
        output["structured_response"] = json.loads(
            output.pop("structured_response_json") or "{}"
        )
        outputs.append(output)
    return outputs


def replace_meeting_outputs(
    meeting_id: str,
    outputs: list[dict],
    trade_review: dict,
    db_path: str | Path | None = None,
    status: str = "completed",
    messages: list[dict] | None = None,
    structured_decision: dict | None = None,
) -> None:
    timestamp = now_iso()
    with get_connection(db_path) as connection:
        connection.execute("DELETE FROM agent_outputs WHERE meeting_id = ?", (meeting_id,))
        connection.execute("DELETE FROM meeting_messages WHERE meeting_id = ?", (meeting_id,))
        for output in outputs:
            connection.execute(
                """
                INSERT INTO agent_outputs (
                    meeting_id,
                    agent_key,
                    agent_name,
                    stage,
                    stance,
                    confidence,
                    content,
                    provider_name,
                    structured_response_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    output["agent_key"],
                    output["agent_name"],
                    output["stage"],
                    output["stance"],
                    output["confidence"],
                    output["content"],
                    output.get("provider_name", "mock"),
                    json.dumps(
                        output.get("structured_response", {}),
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
        for message in messages or []:
            connection.execute(
                """
                INSERT INTO meeting_messages (
                    meeting_id,
                    agent_id,
                    agent_key,
                    agent_name,
                    round,
                    message_type,
                    content,
                    confidence,
                    risk_level,
                    provider_name,
                    structured_response_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    message.get("agent_id"),
                    message["agent_key"],
                    message["agent_name"],
                    message["round"],
                    message["message_type"],
                    message["content"],
                    message["confidence"],
                    message["risk_level"],
                    message.get("provider_name", "mock"),
                    json.dumps(
                        message.get("structured_response", {}),
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
        connection.execute(
            """
            UPDATE meetings
            SET
                status = ?,
                trade_review_json = ?,
                final_decision_json = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                json.dumps(trade_review, sort_keys=True),
                json.dumps(structured_decision or {}, sort_keys=True),
                timestamp,
                meeting_id,
            ),
        )


def get_meeting_messages(meeting_id: str, db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                meeting_id,
                agent_id,
                agent_key,
                agent_name,
                round,
                message_type,
                content,
                confidence,
                risk_level,
                provider_name,
                structured_response_json,
                created_at
            FROM meeting_messages
            WHERE meeting_id = ?
            ORDER BY id ASC
            """,
            (meeting_id,),
        ).fetchall()
    messages = []
    for row in rows:
        message = row_to_dict(row)
        message["structured_response"] = json.loads(
            message.pop("structured_response_json") or "{}"
        )
        messages.append(message)
    return messages


def upsert_report(
    meeting_id: str,
    report_path: Path,
    markdown: str,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO reports (meeting_id, path, markdown, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(meeting_id) DO UPDATE SET
                path = excluded.path,
                markdown = excluded.markdown,
                created_at = excluded.created_at
            """,
            (meeting_id, str(report_path), markdown, timestamp),
        )
        row = connection.execute(
            """
            SELECT id, meeting_id, path, markdown, created_at
            FROM reports
            WHERE meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()
    return row_to_dict(row)


def get_report(meeting_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, meeting_id, path, markdown, created_at
            FROM reports
            WHERE meeting_id = ?
            """,
            (meeting_id,),
        ).fetchone()
    return row_to_dict(row) if row else None


def create_context_file(record: dict, db_path: str | Path | None = None) -> dict:
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO context_files (
                id,
                meeting_id,
                original_filename,
                stored_path,
                file_type,
                file_size,
                extracted_text_path,
                summary,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["meeting_id"],
                record["original_filename"],
                record["stored_path"],
                record["file_type"],
                record["file_size"],
                record.get("extracted_text_path"),
                record["summary"],
                record["status"],
                record["created_at"],
            ),
        )
    return get_context_file(record["id"], db_path)


def list_context_files(meeting_id: str, db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                meeting_id,
                original_filename,
                stored_path,
                file_type,
                file_size,
                extracted_text_path,
                summary,
                status,
                created_at
            FROM context_files
            WHERE meeting_id = ?
            ORDER BY created_at ASC, original_filename ASC
            """,
            (meeting_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def get_context_file(file_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                meeting_id,
                original_filename,
                stored_path,
                file_type,
                file_size,
                extracted_text_path,
                summary,
                status,
                created_at
            FROM context_files
            WHERE id = ?
            """,
            (file_id,),
        ).fetchone()
    return row_to_dict(row) if row else None


def delete_context_file(file_id: str, db_path: str | Path | None = None) -> dict | None:
    record = get_context_file(file_id, db_path)
    if record is None:
        return None
    with get_connection(db_path) as connection:
        connection.execute("DELETE FROM context_files WHERE id = ?", (file_id,))
    return record


def create_trade_review(
    *,
    ticker: str,
    strategy_signal: str,
    side: str,
    price: float | None,
    volume: int | None,
    timeframe: str | None,
    source: str | None,
    input_payload: dict,
    structured_decision: dict,
    linked_meeting_id: str,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    review_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO trade_reviews (
                id,
                ticker,
                strategy_signal,
                side,
                price,
                volume,
                timeframe,
                source,
                input_payload_json,
                structured_decision_json,
                risk_level,
                decision,
                trade_allowed,
                order_execution_allowed,
                linked_meeting_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                ticker,
                strategy_signal,
                side,
                price,
                volume,
                timeframe,
                source,
                json.dumps(input_payload, sort_keys=True),
                json.dumps(structured_decision, sort_keys=True),
                structured_decision["risk_level"],
                structured_decision["decision"],
                int(bool(structured_decision.get("trade_allowed", False))),
                0,
                linked_meeting_id,
                timestamp,
            ),
        )
    return get_trade_review(review_id, db_path)


def list_trade_reviews(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                ticker,
                strategy_signal,
                side,
                price,
                volume,
                timeframe,
                source,
                input_payload_json,
                structured_decision_json,
                risk_level,
                decision,
                trade_allowed,
                order_execution_allowed,
                linked_meeting_id,
                created_at
            FROM trade_reviews
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_trade_review_row_to_dict(row) for row in rows]


def get_trade_review(review_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                ticker,
                strategy_signal,
                side,
                price,
                volume,
                timeframe,
                source,
                input_payload_json,
                structured_decision_json,
                risk_level,
                decision,
                trade_allowed,
                order_execution_allowed,
                linked_meeting_id,
                created_at
            FROM trade_reviews
            WHERE id = ?
            """,
            (review_id,),
        ).fetchone()
    return _trade_review_row_to_dict(row) if row else None


def create_ticker_review(
    *,
    ticker: str,
    review_mode: str,
    timeframe: str | None,
    source: str,
    auto_payload: dict,
    trade_review_id: str,
    linked_meeting_id: str,
    decision: str,
    risk_level: str,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    review_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO ticker_reviews (
                id,
                ticker,
                review_mode,
                timeframe,
                source,
                auto_payload_json,
                trade_review_id,
                linked_meeting_id,
                decision,
                risk_level,
                order_execution_allowed,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                ticker,
                review_mode,
                timeframe,
                source,
                json.dumps(auto_payload, sort_keys=True),
                trade_review_id,
                linked_meeting_id,
                decision,
                risk_level,
                0,
                timestamp,
            ),
        )
    return get_ticker_review(review_id, db_path)


def get_ticker_review(review_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                ticker,
                review_mode,
                timeframe,
                source,
                auto_payload_json,
                trade_review_id,
                linked_meeting_id,
                decision,
                risk_level,
                order_execution_allowed,
                created_at
            FROM ticker_reviews
            WHERE id = ?
            """,
            (review_id,),
        ).fetchone()
    return _ticker_review_row_to_dict(row) if row else None


def list_ticker_reviews(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                ticker,
                review_mode,
                timeframe,
                source,
                auto_payload_json,
                trade_review_id,
                linked_meeting_id,
                decision,
                risk_level,
                order_execution_allowed,
                created_at
            FROM ticker_reviews
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_ticker_review_row_to_dict(row) for row in rows]


def create_autonomous_review(
    *,
    universe: str,
    review_mode: str,
    max_candidates: int,
    timeframe: str | None,
    candidate_count: int,
    result_summary: dict,
    created_trade_review_ids: list[str],
    created_ticker_review_ids: list[str],
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    review_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO autonomous_reviews (
                id,
                universe,
                review_mode,
                max_candidates,
                timeframe,
                candidate_count,
                result_summary_json,
                created_trade_review_ids_json,
                created_ticker_review_ids_json,
                order_execution_allowed,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                universe,
                review_mode,
                max_candidates,
                timeframe,
                candidate_count,
                json.dumps(result_summary, sort_keys=True),
                json.dumps(created_trade_review_ids, sort_keys=True),
                json.dumps(created_ticker_review_ids, sort_keys=True),
                0,
                timestamp,
            ),
        )
    return get_autonomous_review(review_id, db_path)


def get_autonomous_review(review_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                universe,
                review_mode,
                max_candidates,
                timeframe,
                candidate_count,
                result_summary_json,
                created_trade_review_ids_json,
                created_ticker_review_ids_json,
                order_execution_allowed,
                created_at
            FROM autonomous_reviews
            WHERE id = ?
            """,
            (review_id,),
        ).fetchone()
    return _autonomous_review_row_to_dict(row) if row else None


def _autonomous_review_row_to_dict(row) -> dict:
    review = row_to_dict(row)
    review["summary"] = json.loads(review.pop("result_summary_json"))
    review["created_trade_review_ids"] = json.loads(
        review.pop("created_trade_review_ids_json")
    )
    review["created_ticker_review_ids"] = json.loads(
        review.pop("created_ticker_review_ids_json")
    )
    review["order_execution_allowed"] = False
    return review


def create_watchlist(
    *,
    name: str,
    description: str | None,
    tickers: list[str],
    review_mode: str,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    watchlist_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlists (
                id,
                name,
                description,
                tickers_json,
                review_mode,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                watchlist_id,
                name,
                description,
                json.dumps(tickers, sort_keys=True),
                review_mode,
                timestamp,
                timestamp,
            ),
        )
    return get_watchlist(watchlist_id, db_path)


def list_watchlists(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, description, tickers_json, review_mode, created_at, updated_at
            FROM watchlists
            ORDER BY updated_at DESC, created_at DESC
            """
        ).fetchall()
    return [_watchlist_row_to_dict(row) for row in rows]


def get_watchlist(watchlist_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, name, description, tickers_json, review_mode, created_at, updated_at
            FROM watchlists
            WHERE id = ?
            """,
            (watchlist_id,),
        ).fetchone()
    return _watchlist_row_to_dict(row) if row else None


def update_watchlist(
    watchlist_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    tickers: list[str] | None = None,
    review_mode: str | None = None,
    db_path: str | Path | None = None,
) -> dict | None:
    existing = get_watchlist(watchlist_id, db_path)
    if not existing:
        return None
    updated = {
        "name": name if name is not None else existing["name"],
        "description": description if description is not None else existing.get("description"),
        "tickers": tickers if tickers is not None else existing["tickers"],
        "review_mode": review_mode if review_mode is not None else existing["review_mode"],
    }
    timestamp = now_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE watchlists
            SET name = ?, description = ?, tickers_json = ?, review_mode = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                updated["description"],
                json.dumps(updated["tickers"], sort_keys=True),
                updated["review_mode"],
                timestamp,
                watchlist_id,
            ),
        )
    return get_watchlist(watchlist_id, db_path)


def delete_watchlist(watchlist_id: str, db_path: str | Path | None = None) -> dict | None:
    existing = get_watchlist(watchlist_id, db_path)
    if not existing:
        return None
    with get_connection(db_path) as connection:
        connection.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))
    return existing


def create_watchlist_review(
    *,
    watchlist_id: str,
    review_mode: str,
    ticker_count: int,
    result_summary: dict,
    ticker_review_ids: list[str],
    trade_review_ids: list[str],
    highest_risk_level: str,
    blocked_count: int,
    hold_count: int,
    need_more_data_count: int,
    allow_count: int,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    review_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlist_reviews (
                id,
                watchlist_id,
                review_mode,
                ticker_count,
                result_summary_json,
                ticker_review_ids_json,
                trade_review_ids_json,
                highest_risk_level,
                blocked_count,
                hold_count,
                need_more_data_count,
                allow_count,
                order_execution_allowed,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_id,
                watchlist_id,
                review_mode,
                ticker_count,
                json.dumps(result_summary, sort_keys=True),
                json.dumps(ticker_review_ids, sort_keys=True),
                json.dumps(trade_review_ids, sort_keys=True),
                highest_risk_level,
                blocked_count,
                hold_count,
                need_more_data_count,
                allow_count,
                0,
                timestamp,
            ),
        )
    return get_watchlist_review(review_id, db_path)


def list_watchlist_reviews(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                watchlist_id,
                review_mode,
                ticker_count,
                result_summary_json,
                ticker_review_ids_json,
                trade_review_ids_json,
                highest_risk_level,
                blocked_count,
                hold_count,
                need_more_data_count,
                allow_count,
                order_execution_allowed,
                created_at
            FROM watchlist_reviews
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_watchlist_review_row_to_dict(row) for row in rows]


def get_watchlist_review(review_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                watchlist_id,
                review_mode,
                ticker_count,
                result_summary_json,
                ticker_review_ids_json,
                trade_review_ids_json,
                highest_risk_level,
                blocked_count,
                hold_count,
                need_more_data_count,
                allow_count,
                order_execution_allowed,
                created_at
            FROM watchlist_reviews
            WHERE id = ?
            """,
            (review_id,),
        ).fetchone()
    return _watchlist_review_row_to_dict(row) if row else None


def update_watchlist_review_summary(
    review_id: str,
    result_summary: dict,
    db_path: str | Path | None = None,
) -> dict | None:
    if not get_watchlist_review(review_id, db_path):
        return None
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE watchlist_reviews
            SET result_summary_json = ?
            WHERE id = ?
            """,
            (json.dumps(result_summary, sort_keys=True), review_id),
        )
    return get_watchlist_review(review_id, db_path)


def _watchlist_row_to_dict(row) -> dict:
    watchlist = row_to_dict(row)
    watchlist["tickers"] = json.loads(watchlist.pop("tickers_json"))
    watchlist["ticker_count"] = len(watchlist["tickers"])
    watchlist["order_execution_allowed"] = False
    return watchlist


def _watchlist_review_row_to_dict(row) -> dict:
    review = row_to_dict(row)
    summary = json.loads(review.pop("result_summary_json"))
    review["summary"] = summary.get("summary", {})
    review["results"] = summary.get("results", [])
    review["watchlist_name"] = summary.get("watchlist_name")
    review["report"] = summary.get("report", {})
    review["safety_boundary"] = summary.get("safety_boundary")
    review["ticker_review_ids"] = json.loads(review.pop("ticker_review_ids_json"))
    review["trade_review_ids"] = json.loads(review.pop("trade_review_ids_json"))
    review["order_execution_allowed"] = False
    return review


def create_watchlist_schedule(
    *,
    watchlist_id: str,
    name: str,
    enabled: bool,
    cadence: str,
    run_time: str | None,
    timezone: str,
    auto_send_telegram: bool,
    next_run_at: str | None,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    schedule_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlist_schedules (
                id,
                watchlist_id,
                name,
                enabled,
                cadence,
                run_time,
                timezone,
                auto_send_telegram,
                last_run_at,
                next_run_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule_id,
                watchlist_id,
                name,
                int(bool(enabled)),
                cadence,
                run_time,
                timezone,
                int(bool(auto_send_telegram)),
                None,
                next_run_at,
                timestamp,
                timestamp,
            ),
        )
    return get_watchlist_schedule(schedule_id, db_path)


def list_watchlist_schedules(
    db_path: str | Path | None = None,
    watchlist_id: str | None = None,
) -> list[dict]:
    query = """
        SELECT
            id,
            watchlist_id,
            name,
            enabled,
            cadence,
            run_time,
            timezone,
            auto_send_telegram,
            last_run_at,
            next_run_at,
            created_at,
            updated_at
        FROM watchlist_schedules
    """
    params: tuple = ()
    if watchlist_id:
        query += " WHERE watchlist_id = ?"
        params = (watchlist_id,)
    query += " ORDER BY created_at DESC"
    with get_connection(db_path) as connection:
        rows = connection.execute(query, params).fetchall()
    return [_watchlist_schedule_row_to_dict(row) for row in rows]


def get_watchlist_schedule(schedule_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                watchlist_id,
                name,
                enabled,
                cadence,
                run_time,
                timezone,
                auto_send_telegram,
                last_run_at,
                next_run_at,
                created_at,
                updated_at
            FROM watchlist_schedules
            WHERE id = ?
            """,
            (schedule_id,),
        ).fetchone()
    return _watchlist_schedule_row_to_dict(row) if row else None


def update_watchlist_schedule(
    schedule_id: str,
    *,
    name: str | None = None,
    enabled: bool | None = None,
    cadence: str | None = None,
    run_time: str | None = None,
    clear_run_time: bool = False,
    timezone: str | None = None,
    auto_send_telegram: bool | None = None,
    last_run_at: str | None = None,
    next_run_at: str | None = None,
    clear_next_run_at: bool = False,
    db_path: str | Path | None = None,
) -> dict | None:
    existing = get_watchlist_schedule(schedule_id, db_path)
    if not existing:
        return None
    updated = {
        "name": name if name is not None else existing["name"],
        "enabled": enabled if enabled is not None else existing["enabled"],
        "cadence": cadence if cadence is not None else existing["cadence"],
        "run_time": (
            None if clear_run_time else run_time if run_time is not None else existing.get("run_time")
        ),
        "timezone": timezone if timezone is not None else existing["timezone"],
        "auto_send_telegram": (
            auto_send_telegram
            if auto_send_telegram is not None
            else existing["auto_send_telegram"]
        ),
        "last_run_at": last_run_at if last_run_at is not None else existing.get("last_run_at"),
        "next_run_at": (
            None
            if clear_next_run_at
            else next_run_at if next_run_at is not None else existing.get("next_run_at")
        ),
    }
    timestamp = now_iso()
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE watchlist_schedules
            SET
                name = ?,
                enabled = ?,
                cadence = ?,
                run_time = ?,
                timezone = ?,
                auto_send_telegram = ?,
                last_run_at = ?,
                next_run_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                updated["name"],
                int(bool(updated["enabled"])),
                updated["cadence"],
                updated["run_time"],
                updated["timezone"],
                int(bool(updated["auto_send_telegram"])),
                updated["last_run_at"],
                updated["next_run_at"],
                timestamp,
                schedule_id,
            ),
        )
    return get_watchlist_schedule(schedule_id, db_path)


def delete_watchlist_schedule(schedule_id: str, db_path: str | Path | None = None) -> dict | None:
    existing = get_watchlist_schedule(schedule_id, db_path)
    if not existing:
        return None
    with get_connection(db_path) as connection:
        connection.execute("DELETE FROM watchlist_schedules WHERE id = ?", (schedule_id,))
    return existing


def create_watchlist_schedule_run(
    *,
    schedule_id: str,
    watchlist_id: str,
    watchlist_review_id: str | None,
    status: str,
    started_at: str,
    finished_at: str,
    summary: dict,
    telegram_status: dict,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    run_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlist_schedule_runs (
                id,
                schedule_id,
                watchlist_id,
                watchlist_review_id,
                status,
                started_at,
                finished_at,
                summary_json,
                telegram_status_json,
                error_message,
                order_execution_allowed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                schedule_id,
                watchlist_id,
                watchlist_review_id,
                status,
                started_at,
                finished_at,
                json.dumps(summary, sort_keys=True),
                json.dumps(telegram_status, sort_keys=True),
                error_message,
                0,
            ),
        )
    return get_watchlist_schedule_run(run_id, db_path)


def list_watchlist_schedule_runs(
    db_path: str | Path | None = None,
    *,
    schedule_id: str | None = None,
    watchlist_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    clauses = []
    params: list[str] = []
    if schedule_id:
        clauses.append("schedule_id = ?")
        params.append(schedule_id)
    if watchlist_id:
        clauses.append("watchlist_id = ?")
        params.append(watchlist_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    query = """
        SELECT
            id,
            schedule_id,
            watchlist_id,
            watchlist_review_id,
            status,
            started_at,
            finished_at,
            summary_json,
            telegram_status_json,
            error_message,
            order_execution_allowed
        FROM watchlist_schedule_runs
    """
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY started_at DESC"
    with get_connection(db_path) as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    return [_watchlist_schedule_run_row_to_dict(row) for row in rows]


def get_watchlist_schedule_run(run_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                schedule_id,
                watchlist_id,
                watchlist_review_id,
                status,
                started_at,
                finished_at,
                summary_json,
                telegram_status_json,
                error_message,
                order_execution_allowed
            FROM watchlist_schedule_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()
    return _watchlist_schedule_run_row_to_dict(row) if row else None


def _watchlist_schedule_row_to_dict(row) -> dict:
    schedule = row_to_dict(row)
    schedule["enabled"] = bool(schedule["enabled"])
    schedule["auto_send_telegram"] = bool(schedule["auto_send_telegram"])
    schedule["order_execution_allowed"] = False
    return schedule


def _watchlist_schedule_run_row_to_dict(row) -> dict:
    run = row_to_dict(row)
    run["summary"] = json.loads(run.pop("summary_json") or "{}")
    run["telegram_status"] = json.loads(run.pop("telegram_status_json") or "{}")
    run["order_execution_allowed"] = False
    return run


def _ticker_review_row_to_dict(row) -> dict:
    review = row_to_dict(row)
    review["auto_payload"] = json.loads(review.pop("auto_payload_json"))
    review["order_execution_allowed"] = False
    return review


def _trade_review_row_to_dict(row) -> dict:
    review = row_to_dict(row)
    review["input_payload"] = json.loads(review.pop("input_payload_json"))
    review["structured_decision"] = json.loads(review.pop("structured_decision_json"))
    review["trade_allowed"] = bool(review["trade_allowed"])
    review["order_execution_allowed"] = False
    return review


def create_webhook_event(
    *,
    source: str,
    signal_id: str,
    event_type: str,
    raw_payload: dict,
    normalized_payload: dict,
    status: str,
    trade_review_id: str | None = None,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> dict:
    timestamp = now_iso()
    event_id = uuid4().hex
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO webhook_events (
                id,
                source,
                signal_id,
                event_type,
                raw_payload_json,
                normalized_payload_json,
                trade_review_id,
                status,
                error_message,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                source,
                signal_id,
                event_type,
                json.dumps(raw_payload, sort_keys=True),
                json.dumps(normalized_payload, sort_keys=True),
                trade_review_id,
                status,
                error_message,
                timestamp,
            ),
        )
    return get_webhook_event(event_id, db_path)


def update_webhook_event(
    event_id: str,
    *,
    status: str,
    trade_review_id: str | None = None,
    error_message: str | None = None,
    db_path: str | Path | None = None,
) -> dict | None:
    with get_connection(db_path) as connection:
        connection.execute(
            """
            UPDATE webhook_events
            SET status = ?, trade_review_id = ?, error_message = ?
            WHERE id = ?
            """,
            (status, trade_review_id, error_message, event_id),
        )
    return get_webhook_event(event_id, db_path)


def get_webhook_event(event_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                source,
                signal_id,
                event_type,
                raw_payload_json,
                normalized_payload_json,
                trade_review_id,
                status,
                error_message,
                created_at
            FROM webhook_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
    return _webhook_event_row_to_dict(row) if row else None


def get_webhook_event_by_source_signal(
    source: str,
    signal_id: str,
    db_path: str | Path | None = None,
) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                source,
                signal_id,
                event_type,
                raw_payload_json,
                normalized_payload_json,
                trade_review_id,
                status,
                error_message,
                created_at
            FROM webhook_events
            WHERE source = ? AND signal_id = ?
            """,
            (source, signal_id),
        ).fetchone()
    return _webhook_event_row_to_dict(row) if row else None


def list_webhook_events(db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                source,
                signal_id,
                event_type,
                raw_payload_json,
                normalized_payload_json,
                trade_review_id,
                status,
                error_message,
                created_at
            FROM webhook_events
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [_webhook_event_row_to_dict(row) for row in rows]


def _webhook_event_row_to_dict(row) -> dict:
    event = row_to_dict(row)
    event["raw_payload"] = json.loads(event.pop("raw_payload_json"))
    event["normalized_payload"] = json.loads(event.pop("normalized_payload_json"))
    event["order_execution_allowed"] = False
    return event
