from __future__ import annotations

from secret_santa.bot.db import repo
from secret_santa.bot.db.database import Database
from secret_santa.bot.i18n import DEFAULT_LANGUAGE, detect_language


async def resolve_user_language(
    db: Database,
    user_id: int,
    language_code: str | None,
) -> str:
    """Resolve the user's language, persisting the auto-detected value on first contact."""
    async with db.lock:
        stored = await repo.get_user_language(db, user_id)
        if stored is not None:
            return stored
        detected = detect_language(language_code)
        await repo.ensure_user_language(db, user_id, detected)
        await db.commit()
        return detected


async def set_user_language(db: Database, user_id: int, language_code: str) -> None:
    async with db.lock:
        await repo.set_user_language(db, user_id, language_code)
        await db.commit()


async def stored_language(db: Database, user_id: int) -> str:
    """Return the user's stored language or the default when absent."""
    async with db.lock:
        stored = await repo.get_user_language(db, user_id)
        return stored if stored is not None else DEFAULT_LANGUAGE
