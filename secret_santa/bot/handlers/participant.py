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
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    try:
        result = await get_participant_target(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    try:
        await bot.send_message(
            callback.from_user.id,
            texts.target_assignment(
                lang,
                result.game.name,
                result.target,
                result.participant.gift_ready,
            ),
        )
    except TelegramAPIError:
        logger.warning("Could not deliver a target to recipient %s", callback.from_user.id)
        await callback.answer(texts.t(lang, "target_delivery_failed"), show_alert=True)
        return
    await callback.answer(texts.t(lang, "target_sent"))


@router.callback_query(F.data.regexp(r"^participant:ready:\d+$"))
async def mark_ready(callback: CallbackQuery, db: Database, lang: str) -> None:
    game_id = _game_id(callback.data)
    try:
        result = await mark_gift_ready(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    text = texts.t(lang, "gift_ready_success") if result.changed else texts.t(lang, "gift_already_ready")
    await callback.answer(text, show_alert=True)
