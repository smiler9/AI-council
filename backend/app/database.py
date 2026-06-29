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
                status TEXT NOT NULL,
                trade_review_json TEXT NOT NULL,
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
            """
        )

