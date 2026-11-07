from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, User

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import cancel_keyboard, open_game_keyboard, wishes_keyboard
from secret_santa.bot.notifications import notify_organizer_participant_joined
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import join_game, validate_join
from secret_santa.bot.states import JoinGameState

router = Router(name="join_game")


async def _begin_join_game(message: Message, state: FSMContext) -> None:
    await state.set_state(JoinGameState.waiting_for_code)
    await message.answer(texts.ASK_CODE, reply_markup=cancel_keyboard())


@router.callback_query(F.data == "join_game")
async def begin_join_game(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _begin_join_game(callback.message, state)
    await callback.answer()


@router.message(F.text == texts.JOIN_GAME_BUTTON)
async def join_game_button(message: Message, state: FSMContext) -> None:
    await _begin_join_game(message, state)


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
    await state.update_data(
        game_id=game.id,
        game_name=game.name,
        organizer_id=game.organizer_id,
    )
    await state.set_state(JoinGameState.waiting_for_wishes)
    await message.answer(texts.ASK_WISHES, reply_markup=wishes_keyboard())


async def _finish_join(
    message: Message,
    user: User,
    state: FSMContext,
    db: Database,
    bot: Bot,
    wishes: str | None,
) -> None:
    data = await state.get_data()
    game_id = data.get("game_id")
    game_name = data.get("game_name")
    organizer_id = data.get("organizer_id")
    if (
        not isinstance(game_id, int)
        or not isinstance(game_name, str)
        or not isinstance(organizer_id, int)
    ):
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
    await notify_organizer_participant_joined(
        bot,
        organizer_id,
        game_name,
        user.username,
        user.first_name,
    )


@router.message(JoinGameState.waiting_for_wishes)
async def process_wishes(
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
    await _finish_join(message, message.from_user, state, db, bot, message.text)


@router.callback_query(JoinGameState.waiting_for_wishes, F.data == "join:skip_wishes")
async def skip_wishes(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    bot: Bot,
) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _finish_join(
        callback.message,
        callback.from_user,
        state,
        db,
        bot,
        None,
    )
    await callback.answer()
