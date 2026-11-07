from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import cancel_keyboard, open_game_keyboard, wishes_keyboard
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import join_game, validate_join
from secret_santa.bot.states import JoinGameState

router = Router(name="join_game")


@router.callback_query(F.data == "join_game")
async def begin_join_game(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(JoinGameState.waiting_for_code)
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(texts.ASK_CODE, reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(JoinGameState.waiting_for_code)
async def process_join_code(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    if message.text is None:
        await message.answer(texts.TEXT_REQUIRED)
        return
    try:
        game = await validate_join(db, message.text, message.from_user.id)
    except GameError as error:
        await notify_game_error(message, error)
        return
    await state.update_data(game_id=game.id, game_name=game.name)
    await state.set_state(JoinGameState.waiting_for_wishes)
    await message.answer(texts.ASK_WISHES, reply_markup=wishes_keyboard())


async def _finish_join(
    message: Message,
    user: User,
    state: FSMContext,
    db: Database,
    wishes: str | None,
) -> None:
    data = await state.get_data()
    game_id = data.get("game_id")
    game_name = data.get("game_name")
    if not isinstance(game_id, int) or not isinstance(game_name, str):
        await state.clear()
        await message.answer(texts.JOIN_SESSION_EXPIRED)
        return
    try:
        await join_game(
            db,
            game_id,
            user.id,
            user.username,
            user.first_name,
            wishes,
        )
    except GameError as error:
        await notify_game_error(message, error)
        return
    await state.clear()
    await message.answer(
        texts.joined_game(game_name),
        reply_markup=open_game_keyboard(game_id),
    )


@router.message(JoinGameState.waiting_for_wishes)
async def process_wishes(
    message: Message,
    state: FSMContext,
    db: Database,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    if message.text is None:
        await message.answer(texts.TEXT_REQUIRED)
        return
    await _finish_join(message, message.from_user, state, db, message.text)


@router.callback_query(JoinGameState.waiting_for_wishes, F.data == "join:skip_wishes")
async def skip_wishes(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _finish_join(
        callback.message,
        callback.from_user,
        state,
        db,
        None,
    )
    await callback.answer()
