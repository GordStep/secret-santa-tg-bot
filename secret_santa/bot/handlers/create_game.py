from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import cancel_keyboard, game_keyboard
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import create_game
from secret_santa.bot.states import CreateGameState

router = Router(name="create_game")


async def _begin_create_game(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateGameState.waiting_for_name)
    await message.answer(texts.ASK_GAME_NAME, reply_markup=cancel_keyboard())


@router.callback_query(F.data == "create_game")
async def begin_create_game(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _begin_create_game(callback.message, state)
    await callback.answer()


@router.message(F.text == texts.CREATE_GAME_BUTTON)
async def create_game_button(message: Message, state: FSMContext) -> None:
    await _begin_create_game(message, state)


@router.message(CreateGameState.waiting_for_name)
async def create_game_with_name(
    message: Message,
    state: FSMContext,
    db: Database,
    bot: Bot,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    if message.text is None:
        await message.answer(texts.TEXT_REQUIRED)
        return
    bot_user = await bot.get_me()
    if bot_user.username is None:
        raise RuntimeError("Bot username is missing")
    try:
        game = await create_game(db, message.from_user.id, message.text)
    except GameError as error:
        await notify_game_error(message, error)
        return
    await state.clear()
    await message.answer(
        texts.game_created(game, bot_user.username),
        reply_markup=game_keyboard(game, True, None),
    )
