from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import aiosqlite

from secret_santa.bot.db.models import init_db


@dataclass(slots=True)
class Database:
    connection: aiosqlite.Connection
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    async def connect(cls, path: str) -> Database:
        connection = await aiosqlite.connect(path)
        try:
            await init_db(connection)
        except Exception:
            await connection.close()
            raise
        return cls(connection)

    def execute(
        self,
        sql: str,
        parameters: Iterable[Any] = (),
    ) -> aiosqlite.Cursor:
        return self.connection.execute(sql, parameters)

    def executemany(
        self,
        sql: str,
        parameters: Iterable[Iterable[Any]],
    ) -> aiosqlite.Cursor:
        return self.connection.executemany(sql, parameters)

    async def commit(self) -> None:
        await self.connection.commit()

    async def rollback(self) -> None:
        await self.connection.rollback()

    async def close(self) -> None:
        await self.connection.close()
