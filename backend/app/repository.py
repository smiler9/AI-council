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


def create_meeting(topic: str, ticker: str | None, db_path: str | Path | None = None) -> dict:
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
            INSERT INTO meetings (id, topic, ticker, status, trade_review_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                topic,
                ticker,
                "draft",
                json.dumps(trade_review, sort_keys=True),
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
                m.status,
                m.trade_review_json,
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
        meeting["report_available"] = bool(meeting["report_available"])
        meetings.append(meeting)
    return meetings


def get_meeting(meeting_id: str, db_path: str | Path | None = None) -> dict | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, topic, ticker, status, trade_review_json, created_at, updated_at
            FROM meetings
            WHERE id = ?
            """,
            (meeting_id,),
        ).fetchone()
    if row is None:
        return None
    meeting = row_to_dict(row)
    meeting["trade_review"] = json.loads(meeting.pop("trade_review_json"))
    return meeting


def get_meeting_outputs(meeting_id: str, db_path: str | Path | None = None) -> list[dict]:
    with get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, meeting_id, agent_key, agent_name, stage, stance, confidence, content, created_at
            FROM agent_outputs
            WHERE meeting_id = ?
            ORDER BY id ASC
            """,
            (meeting_id,),
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def replace_meeting_outputs(
    meeting_id: str,
    outputs: list[dict],
    trade_review: dict,
    db_path: str | Path | None = None,
) -> None:
    timestamp = now_iso()
    with get_connection(db_path) as connection:
        connection.execute("DELETE FROM agent_outputs WHERE meeting_id = ?", (meeting_id,))
        for output in outputs:
            connection.execute(
                """
                INSERT INTO agent_outputs (
                    meeting_id, agent_key, agent_name, stage, stance, confidence, content, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    meeting_id,
                    output["agent_key"],
                    output["agent_name"],
                    output["stage"],
                    output["stance"],
                    output["confidence"],
                    output["content"],
                    timestamp,
                ),
            )
        connection.execute(
            """
            UPDATE meetings
            SET status = ?, trade_review_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                "completed",
                json.dumps(trade_review, sort_keys=True),
                timestamp,
                meeting_id,
            ),
        )


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

