from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import StrEnum

import aiosqlite


class GameStatus(StrEnum):
    COLLECTING = "collecting"
    STARTED = "started"
    ARCHIVED = "archived"


@dataclass(frozen=True, slots=True)
class Game:
    id: int
    code: str
    name: str
    description: str | None
    organizer_id: int
    status: GameStatus
    created_at: str


@dataclass(frozen=True, slots=True)
class Participant:
    id: int
    game_id: int
    user_id: int
    username: str | None
    first_name: str
    wishes: str | None
    gift_ready: bool
    target_user_id: int | None


@dataclass(frozen=True, slots=True)
class Target:
    user_id: int
    username: str | None
    first_name: str
    wishes: str | None


SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    organizer_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('collecting', 'started', 'archived')),
    created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    username TEXT,
    first_name TEXT NOT NULL,
    wishes TEXT,
    gift_ready BOOLEAN NOT NULL DEFAULT 0 CHECK (gift_ready IN (0, 1)),
    target_user_id INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    UNIQUE (game_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_game_id ON participants(game_id);
CREATE INDEX IF NOT EXISTS idx_participants_user_id ON participants(user_id);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    language_code TEXT NOT NULL
);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    db.row_factory = sqlite3.Row
    await db.execute("PRAGMA foreign_keys = ON")
    await db.executescript(SCHEMA)
    await _migrate(db)
    await db.commit()


async def _migrate(db: aiosqlite.Connection) -> None:
    """Apply lightweight schema migrations for databases created before a field existed."""
    cursor = await db.execute("PRAGMA table_info(games)")
    columns = {row["name"] for row in await cursor.fetchall()}
    await cursor.close()
    if "description" not in columns:
        await db.execute("ALTER TABLE games ADD COLUMN description TEXT")
