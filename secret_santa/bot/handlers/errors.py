from __future__ import annotations

import logging

from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message
from aiogram.types.error_event import ErrorEvent

from secret_santa.bot import texts
from secret_santa.bot.db.models import GameStatus
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


def game_error_text(error: GameError) -> str:
    if isinstance(error, InvalidCodeError):
        return texts.CODE_NOT_FOUND
    if isinstance(error, GameNotFoundError):
        return texts.GAME_NOT_FOUND
    if isinstance(error, GameNotCollectingError):
        if error.status == GameStatus.ARCHIVED:
            return texts.GAME_ARCHIVED
        return texts.JOIN_ALREADY_STARTED
    if isinstance(error, AlreadyJoinedError):
        return texts.ALREADY_JOINED
    if isinstance(error, NotEnoughParticipantsError):
        return texts.NEED_MORE_PLAYERS
    if isinstance(error, GameAlreadyStartedError):
        return texts.ALREADY_STARTED
    if isinstance(error, GameArchivedError):
        return texts.GAME_ARCHIVED
    if isinstance(error, GameNotArchivedError):
        return texts.GAME_NOT_ARCHIVED
    if isinstance(error, GameNotStartedError):
        return texts.GAME_NOT_STARTED
    if isinstance(error, InvalidGameNameError):
        return texts.INVALID_GAME_NAME
    if isinstance(error, InvalidWishesError):
        return texts.INVALID_WISHES
    if isinstance(error, GameAccessDeniedError):
        return texts.NO_ACCESS
    if isinstance(error, NotOrganizerError):
        return texts.NOT_ORGANIZER
    if isinstance(error, NotParticipantError):
        return texts.NOT_PARTICIPANT
    return texts.INTERNAL_ERROR


async def notify_game_error(
    event: Message | CallbackQuery,
    error: GameError,
) -> None:
    text = game_error_text(error)
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
    text = game_error_text(error) if isinstance(error, GameError) else texts.INTERNAL_ERROR
    update = event.update
    try:
        if update.callback_query is not None:
            await update.callback_query.answer(text, show_alert=True)
        elif update.message is not None:
            await update.message.answer(text)
    except TelegramAPIError:
        logger.warning("Could not deliver an error response")
    return True
