from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / ".env"
_DEFAULT_DATABASE_PATH = _PROJECT_ROOT / "secret_santa.db"


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_path: str

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv(_ENV_FILE)
        token = os.environ.get("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN environment variable is required")

        database_path = Path(
            os.environ.get("DATABASE_PATH", str(_DEFAULT_DATABASE_PATH))
        ).expanduser()
        if database_path != Path(":memory:"):
            if not database_path.is_absolute():
                database_path = _PROJECT_ROOT / database_path
            database_path = database_path.resolve()
        return cls(bot_token=token, database_path=str(database_path))
