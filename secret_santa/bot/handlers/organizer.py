from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.handlers.game_info import answer_game_message
from secret_santa.bot.keyboards import (
    archive_confirmation_keyboard,
    cancel_keyboard,
    delete_confirmation_keyboard,
    game_keyboard,
    main_menu_keyboard,
    open_game_keyboard,
)
from secret_santa.bot.lang import stored_language
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import (
    archive_game,
    delete_archived_game,
    get_game_details,
    get_game_for_description_edit,
    start_game,
    update_game_description,
)
from secret_santa.bot.states import EditGameDescriptionState

router = Router(name="organizer")
logger = logging.getLogger(__name__)


def _game_id(data: str | None) -> int:
    if data is None:
        raise RuntimeError("Callback data is unavailable")
    return int(data.rsplit(":", maxsplit=1)[1])


@router.callback_query(F.data.regexp(r"^organizer:edit_description:\d+$"))
async def begin_description_edit(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await get_game_for_description_edit(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await state.update_data(edit_game_id=game_id)
    await state.set_state(EditGameDescriptionState.waiting_for_description)
    await callback.message.answer(
        texts.t(lang, "ask_edit_game_description"),
        reply_markup=cancel_keyboard(lang),
    )
    await callback.answer()


@router.message(EditGameDescriptionState.waiting_for_description)
async def process_description_edit(
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
    game_id = data.get("edit_game_id")
    if not isinstance(game_id, int):
        await state.clear()
        await message.answer(
            texts.t(lang, "edit_description_session_expired"),
            reply_markup=main_menu_keyboard(lang),
        )
        return
    try:
        await update_game_description(db, game_id, message.from_user.id, message.text)
    except GameError as error:
        await notify_game_error(message, error, lang)
        return
    details = await get_game_details(db, game_id, message.from_user.id)
    await state.clear()
    await message.answer(texts.t(lang, "description_updated"))
    await answer_game_message(
        message,
        lang,
        details.game,
        texts.organizer_list(lang, details.game, details.participants),
        texts.organizer_list(
            lang,
            details.game,
            details.participants,
            include_description=False,
        ),
        reply_markup=game_keyboard(
            details.game,
            details.is_organizer,
            details.participant,
            lang,
        ),
    )


@router.callback_query(F.data.regexp(r"^organizer:start:\d+$"))
async def start_draw(
    callback: CallbackQuery,
    db: Database,
    bot: Bot,
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        result = await start_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await callback.answer()

    failed_deliveries = 0
    for notification in result.notifications:
        recipient_language = await stored_language(db, notification.recipient_user_id)
        try:
            await bot.send_message(
                notification.recipient_user_id,
                texts.target_assignment(
                    recipient_language,
                    result.game.name,
                    notification.target,
                    False,
                ),
            )
        except TelegramAPIError:
            failed_deliveries += 1
            logger.warning(
                "Could not deliver a target to recipient %s in game %s",
                notification.recipient_user_id,
                game_id,
            )
    await callback.message.answer(
        texts.start_result(lang, failed_deliveries),
        reply_markup=open_game_keyboard(game_id, lang),
    )


@router.callback_query(F.data.regexp(r"^organizer:archive:\d+$"))
async def request_archive(callback: CallbackQuery, lang: str) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.t(lang, "archive_confirmation"),
        reply_markup=archive_confirmation_keyboard(game_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:archive_confirm:\d+$"))
async def confirm_archive(
    callback: CallbackQuery,
    db: Database,
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await archive_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await callback.message.answer(
        texts.t(lang, "archived_success"),
        reply_markup=open_game_keyboard(game_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:delete:\d+$"))
async def request_deletion(callback: CallbackQuery, lang: str) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.t(lang, "delete_confirmation"),
        reply_markup=delete_confirmation_keyboard(game_id, lang),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^organizer:delete_confirm:\d+$"))
async def confirm_deletion(
    callback: CallbackQuery,
    db: Database,
    lang: str,
) -> None:
    game_id = _game_id(callback.data)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    try:
        await delete_archived_game(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await callback.message.answer(
        texts.t(lang, "deleted_success"),
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()
