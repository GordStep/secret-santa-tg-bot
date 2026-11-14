from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.filters import ButtonText
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import (
    cancel_keyboard,
    description_keyboard,
    game_keyboard,
)
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import MAX_GAME_NAME_LENGTH, create_game
from secret_santa.bot.states import CreateGameState

router = Router(name="create_game")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)


async def _begin_create_game(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(CreateGameState.waiting_for_name)
    await message.answer(texts.t(lang, "ask_game_name"), reply_markup=cancel_keyboard(lang))


@router.callback_query(F.data == "create_game")
async def begin_create_game(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _begin_create_game(callback.message, state, lang)
    await callback.answer()


@router.message(ButtonText("create_game_button"))
async def create_game_button(message: Message, state: FSMContext, lang: str) -> None:
    await _begin_create_game(message, state, lang)


@router.message(CreateGameState.waiting_for_name)
async def process_game_name(message: Message, state: FSMContext, lang: str) -> None:
    if message.text is None:
        await message.answer(texts.t(lang, "text_required"))
        return
    name = message.text.strip()
    if not name or len(name) > MAX_GAME_NAME_LENGTH:
        await message.answer(texts.t(lang, "invalid_game_name"))
        return
    await state.update_data(game_name=name)
    await state.set_state(CreateGameState.waiting_for_description)
    await message.answer(
        texts.t(lang, "ask_game_description"),
        reply_markup=description_keyboard(lang),
    )


async def _create_game(
    message: Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
    lang: str,
    description: str | None,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    data = await state.get_data()
    game_name = data.get("game_name")
    if not isinstance(game_name, str):
        await state.clear()
        await _begin_create_game(message, state, lang)
        return
    bot_user = await bot.get_me()
    if bot_user.username is None:
        raise RuntimeError("Bot username is missing")
    try:
        game = await create_game(db, message.from_user.id, game_name, description)
    except GameError as error:
        await notify_game_error(message, error, lang)
        return
    await state.clear()
    await message.answer(
        texts.game_created(lang, game, bot_user.username),
        reply_markup=game_keyboard(game, True, None, lang),
    )


@router.message(CreateGameState.waiting_for_description)
async def process_game_description(
    message: Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
    lang: str,
) -> None:
    if message.text is None:
        await message.answer(texts.t(lang, "text_required"))
        return
    await _create_game(message, state, db, bot, lang, message.text)


@router.callback_query(
    CreateGameState.waiting_for_description,
    F.data == "create:skip_description",
)
async def skip_description(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    bot: Bot,
    lang: str,
) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _create_game(callback.message, state, db, bot, lang, None)
    await callback.answer()
