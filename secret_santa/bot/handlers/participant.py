from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import get_participant_target, mark_gift_ready

router = Router(name="participant")
logger = logging.getLogger(__name__)


def _game_id(data: str | None) -> int:
    if data is None:
        raise RuntimeError("Callback data is unavailable")
    return int(data.rsplit(":", maxsplit=1)[1])


@router.callback_query(F.data.regexp(r"^participant:target:\d+$"))
async def show_target(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
) -> None:
    game_id = _game_id(callback.data)
    try:
        result = await get_participant_target(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    try:
        await bot.send_message(
            callback.from_user.id,
            texts.target_assignment(
                result.game.name,
                result.target,
                result.participant.gift_ready,
            ),
        )
    except TelegramAPIError:
        logger.warning("Could not deliver a target to recipient %s", callback.from_user.id)
        await callback.answer(texts.TARGET_DELIVERY_FAILED, show_alert=True)
        return
    await callback.answer(texts.TARGET_SENT)


@router.callback_query(F.data.regexp(r"^participant:ready:\d+$"))
async def mark_ready(callback: CallbackQuery, db: Database) -> None:
    game_id = _game_id(callback.data)
    try:
        result = await mark_gift_ready(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    text = texts.GIFT_READY_SUCCESS if result.changed else texts.GIFT_ALREADY_READY
    await callback.answer(text, show_alert=True)
