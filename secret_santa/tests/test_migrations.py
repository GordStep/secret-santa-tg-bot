from __future__ import annotations

import aiosqlite
import pytest

from secret_santa.bot.db.database import Database
from secret_santa.bot.services.games import create_game, list_user_games

LEGACY_GAMES_SCHEMA = """
CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    organizer_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('collecting', 'started', 'archived')),
    created_at DATETIME NOT NULL
);
"""


@pytest.mark.asyncio
async def test_legacy_database_is_migrated_with_description(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    async with aiosqlite.connect(path) as connection:
        await connection.executescript(LEGACY_GAMES_SCHEMA)
        await connection.commit()

    db = await Database.connect(str(path))
    try:
        game = await create_game(db, 900, "Legacy game", "Legacy description")
        assert game.description == "Legacy description"
        assert (await list_user_games(db, 900))[0].description == "Legacy description"
    finally:
        await db.close()
