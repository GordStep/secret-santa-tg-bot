from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_path: str

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN environment variable is required")
        database_path = os.environ.get("DATABASE_PATH", "secret_santa.db")
        return cls(bot_token=token, database_path=database_path)
