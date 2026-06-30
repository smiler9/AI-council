from __future__ import annotations

import sqlite3
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "ai_council.sqlite"


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                focus TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                ticker TEXT,
                mode TEXT NOT NULL DEFAULT 'quick_review',
                status TEXT NOT NULL,
                trade_review_json TEXT NOT NULL,
                final_decision_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                agent_key TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                stage TEXT NOT NULL,
                stance TEXT NOT NULL,
                confidence REAL NOT NULL,
                content TEXT NOT NULL,
                provider_name TEXT NOT NULL DEFAULT 'mock',
                structured_response_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                markdown TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS context_files (
                id TEXT PRIMARY KEY,
                meeting_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                extracted_text_path TEXT,
                summary TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS meeting_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id TEXT NOT NULL,
                agent_id INTEGER,
                agent_key TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                round TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                provider_name TEXT NOT NULL DEFAULT 'mock',
                structured_response_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id) ON DELETE CASCADE,
                FOREIGN KEY (agent_id) REFERENCES agents(id)
            );

            CREATE TABLE IF NOT EXISTS trade_reviews (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                strategy_signal TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL,
                volume INTEGER,
                timeframe TEXT,
                source TEXT,
                input_payload_json TEXT NOT NULL,
                structured_decision_json TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                decision TEXT NOT NULL,
                trade_allowed INTEGER NOT NULL,
                order_execution_allowed INTEGER NOT NULL,
                linked_meeting_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (linked_meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS webhook_events (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                raw_payload_json TEXT NOT NULL,
                normalized_payload_json TEXT NOT NULL,
                trade_review_id TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(source, signal_id),
                FOREIGN KEY (trade_review_id) REFERENCES trade_reviews(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS ticker_reviews (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                review_mode TEXT NOT NULL,
                timeframe TEXT,
                source TEXT NOT NULL,
                auto_payload_json TEXT NOT NULL,
                trade_review_id TEXT NOT NULL,
                linked_meeting_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                order_execution_allowed INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (trade_review_id) REFERENCES trade_reviews(id) ON DELETE CASCADE,
                FOREIGN KEY (linked_meeting_id) REFERENCES meetings(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS autonomous_reviews (
                id TEXT PRIMARY KEY,
                universe TEXT NOT NULL,
                review_mode TEXT NOT NULL,
                max_candidates INTEGER NOT NULL,
                timeframe TEXT,
                candidate_count INTEGER NOT NULL,
                result_summary_json TEXT NOT NULL,
                created_trade_review_ids_json TEXT NOT NULL,
                created_ticker_review_ids_json TEXT NOT NULL,
                order_execution_allowed INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        _ensure_column(
            connection,
            table="meetings",
            column="mode",
            definition="TEXT NOT NULL DEFAULT 'quick_review'",
        )
        _ensure_column(
            connection,
            table="meetings",
            column="final_decision_json",
            definition="TEXT NOT NULL DEFAULT '{}'",
        )
        _ensure_column(
            connection,
            table="agent_outputs",
            column="provider_name",
            definition="TEXT NOT NULL DEFAULT 'mock'",
        )
        _ensure_column(
            connection,
            table="agent_outputs",
            column="structured_response_json",
            definition="TEXT NOT NULL DEFAULT '{}'",
        )


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
