from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from secret_santa.bot.db.database import Database
from secret_santa.bot.i18n import detect_language
from secret_santa.bot.lang import resolve_user_language


class LanguageMiddleware(BaseMiddleware):
    """Resolve the current user's language and expose it to handlers as ``lang``."""

    async def __call__(
        self,
        handler: Callable[..., Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        db: Database | None = data.get("db")
        if user is not None and db is not None:
            data["lang"] = await resolve_user_language(db, user.id, user.language_code)
        else:
            data["lang"] = detect_language(user.language_code if user is not None else None)
        return await handler(event, data)
