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


def _trade_review_row_to_dict(row) -> dict:
    review = row_to_dict(row)
    review["input_payload"] = json.loads(review.pop("input_payload_json"))
    review["structured_decision"] = json.loads(review.pop("structured_decision_json"))
    review["trade_allowed"] = bool(review["trade_allowed"])
    review["order_execution_allowed"] = False
    return review
