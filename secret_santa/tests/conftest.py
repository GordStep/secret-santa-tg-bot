from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio

from secret_santa.bot.db.database import Database


@pytest_asyncio.fixture
async def db() -> AsyncIterator[Database]:
    database = await Database.connect(":memory:")
    yield database
    await database.close()
