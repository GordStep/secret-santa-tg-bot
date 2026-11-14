from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import cancel_keyboard, main_menu_keyboard, open_game_keyboard
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import (
    get_participant_for_wishes_edit,
    get_participant_target,
    get_participant_wishes,
    mark_gift_ready,
    update_participant_wishes,
)
from secret_santa.bot.states import EditWishesState

router = Router(name="participant")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)
logger = logging.getLogger(__name__)


def _game_id(data: str | None) -> int:
    if data is None:
        raise RuntimeError("Callback data is unavailable")
    return int(data.rsplit(":", maxsplit=1)[1])


@router.callback_query(F.data.regexp(r"^participant:wishes:\d+$"))
async def show_wishes(callback: CallbackQuery, db: Database, lang: str) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        participant = await get_participant_wishes(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await callback.message.answer(
        texts.participant_wishes(lang, participant),
        parse_mode=None,
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^participant:edit_wishes:\d+$"))
async def begin_wishes_edit(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await get_participant_for_wishes_edit(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await state.update_data(edit_wishes_game_id=game_id)
    await state.set_state(EditWishesState.waiting_for_wishes)
    await callback.message.answer(
        texts.t(lang, "ask_edit_wishes"),
        reply_markup=cancel_keyboard(lang),
    )
    await callback.answer()


@router.message(EditWishesState.waiting_for_wishes)
async def process_wishes_edit(
    message: Message,
    state: FSMContext,
    db: Database,
    lang: str,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    if message.text is None:
        await message.answer(texts.t(lang, "text_required"))
        return
    data = await state.get_data()
    game_id = data.get("edit_wishes_game_id")
    if not isinstance(game_id, int):
        await state.clear()
        await message.answer(
            texts.t(lang, "edit_wishes_session_expired"),
            reply_markup=main_menu_keyboard(lang),
        )
        return
    try:
        await update_participant_wishes(db, game_id, message.from_user.id, message.text)
    except GameError as error:
        await notify_game_error(message, error, lang)
        return
    await state.clear()
    await message.answer(
        texts.t(lang, "wishes_updated"),
        reply_markup=open_game_keyboard(game_id, lang),
    )


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
