from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import (
    archive_confirmation_keyboard,
    delete_confirmation_keyboard,
    main_menu_keyboard,
    open_game_keyboard,
)
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import archive_game, delete_archived_game, start_game

router = Router(name="organizer")
logger = logging.getLogger(__name__)


def _game_id(data: str | None) -> int:
    if data is None:
        raise RuntimeError("Callback data is unavailable")
    return int(data.rsplit(":", maxsplit=1)[1])


@router.callback_query(F.data.regexp(r"^organizer:start:\d+$"))
async def start_draw(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        result = await start_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    await callback.answer()

    failed_deliveries = 0
    for notification in result.notifications:
        try:
            await bot.send_message(
                notification.recipient_user_id,
                texts.target_assignment(result.game.name, notification.target, False),
            )
        except TelegramAPIError:
            failed_deliveries += 1
            logger.warning(
                "Could not deliver a target to recipient %s in game %s",
                notification.recipient_user_id,
                game_id,
            )
    await callback.message.answer(
        texts.start_result(failed_deliveries),
        reply_markup=open_game_keyboard(game_id),
    )


@router.callback_query(F.data.regexp(r"^organizer:archive:\d+$"))
async def request_archive(callback: CallbackQuery) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.ARCHIVE_CONFIRMATION,
        reply_markup=archive_confirmation_keyboard(game_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:archive_confirm:\d+$"))
async def confirm_archive(
    callback: CallbackQuery,
    db: Database,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await archive_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    await callback.message.answer(
        texts.ARCHIVED_SUCCESS,
        reply_markup=open_game_keyboard(game_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:delete:\d+$"))
async def request_deletion(callback: CallbackQuery) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.DELETE_CONFIRMATION,
        reply_markup=delete_confirmation_keyboard(game_id),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:delete_confirm:\d+$"))
async def confirm_deletion(
    callback: CallbackQuery,
    db: Database,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await delete_archived_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    await callback.message.answer(
        texts.DELETED_SUCCESS,
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
