from __future__ import annotations

import logging

from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram.types.error_event import ErrorEvent

from secret_santa.bot import texts
from secret_santa.bot.db.models import GameStatus
from secret_santa.bot.i18n import detect_language
from secret_santa.bot.services.errors import (
    AlreadyJoinedError,
    GameAccessDeniedError,
    GameAlreadyStartedError,
    GameArchivedError,
    GameError,
    GameNotArchivedError,
    GameNotCollectingError,
    GameNotFoundError,
    GameNotStartedError,
    InvalidCodeError,
    InvalidGameNameError,
    InvalidWishesError,
    NotEnoughParticipantsError,
    NotOrganizerError,
    NotParticipantError,
)

logger = logging.getLogger(__name__)


def game_error_text(language: str, error: GameError) -> str:
    if isinstance(error, InvalidCodeError):
        return texts.t(language, "code_not_found")
    if isinstance(error, GameNotFoundError):
        return texts.t(language, "game_not_found")
    if isinstance(error, GameNotCollectingError):
        if error.status == GameStatus.ARCHIVED:
            return texts.t(language, "game_archived")
        return texts.t(language, "join_already_started")
    if isinstance(error, AlreadyJoinedError):
        return texts.t(language, "already_joined")
    if isinstance(error, NotEnoughParticipantsError):
        return texts.t(language, "need_more_players")
    if isinstance(error, GameAlreadyStartedError):
        return texts.t(language, "already_started")
    if isinstance(error, GameArchivedError):
        return texts.t(language, "game_archived")
    if isinstance(error, GameNotArchivedError):
        return texts.t(language, "game_not_archived")
    if isinstance(error, GameNotStartedError):
        return texts.t(language, "game_not_started")
    if isinstance(error, InvalidGameNameError):
        return texts.t(language, "invalid_game_name")
    if isinstance(error, InvalidWishesError):
        return texts.t(language, "invalid_wishes")
    if isinstance(error, GameAccessDeniedError):
        return texts.t(language, "no_access")
    if isinstance(error, NotOrganizerError):
        return texts.t(language, "not_organizer")
    if isinstance(error, NotParticipantError):
        return texts.t(language, "not_participant")
    return texts.t(language, "internal_error")


async def notify_game_error(
    event: Message | CallbackQuery,
    error: GameError,
    language: str,
) -> None:
    text = game_error_text(language, error)
    if isinstance(event, Message):
        await event.answer(text)
    else:
        await event.answer(text, show_alert=True)


async def handle_unexpected_error(event: ErrorEvent) -> bool:
    error = event.exception
    logger.error(
        "Unhandled update error",
        exc_info=(type(error), error, error.__traceback__),
    )
    update = event.update
    from_user = None
    if update.message is not None:
        from_user = update.message.from_user
    elif update.callback_query is not None:
        from_user = update.callback_query.from_user
    language = detect_language(from_user.language_code if from_user is not None else None)
    text = game_error_text(language, error) if isinstance(error, GameError) else texts.t(language, "internal_error")
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(text, show_alert=True)
        elif update.message is not None:
            await update.message.answer(text)
    except TelegramAPIError:
        logger.warning("Could not deliver an error response")
    return True
