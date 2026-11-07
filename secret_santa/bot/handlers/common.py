from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.errors import notify_game_error
from secret_santa.bot.keyboards import (
    game_keyboard,
    games_keyboard,
    main_menu_keyboard,
    wishes_keyboard,
)
from secret_santa.bot.services.errors import GameError
from secret_santa.bot.services.games import (
    GameDetails,
    get_game_details,
    list_user_games,
    validate_join,
)
from secret_santa.bot.states import JoinGameState

router = Router(name="common")


async def _send_main_menu(message: Message) -> None:
    await message.answer(texts.START_MESSAGE, reply_markup=main_menu_keyboard())


async def _send_my_games(
    message: Message,
    db: Database,
    user_id: int,
) -> None:
    games = await list_user_games(db, user_id)
    if not games:
        await message.answer(texts.NO_GAMES, reply_markup=main_menu_keyboard())
        return
    await message.answer(
        texts.MY_GAMES_HEADER,
        reply_markup=games_keyboard(games, user_id),
    )


async def _send_game_details(message: Message, details: GameDetails) -> None:
    if details.is_organizer:
        text = texts.organizer_list(details.game, details.participants)
    elif details.participant is not None:
        text = texts.participant_game(details.game, details.participant)
    else:
        raise RuntimeError("Participant details are missing")
    await message.answer(
        text,
        reply_markup=game_keyboard(
            details.game,
            details.is_organizer,
            details.participant,
        ),
    )


async def _join_by_invite(
    message: Message,
    state: FSMContext,
    db: Database,
    code: str,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    try:
        game = await validate_join(db, code, message.from_user.id)
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


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    db: Database,
    command: CommandObject,
) -> None:
    await state.clear()
    if not command.args:
        await _send_main_menu(message)
        return
    await _join_by_invite(message, state, db, command.args)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.CANCELLED, reply_markup=main_menu_keyboard())


@router.message(Command("my_games"))
async def my_games_command(message: Message, db: Database) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    await _send_my_games(message, db, message.from_user.id)


@router.message(F.text == texts.MY_GAMES_BUTTON)
async def my_games_button(message: Message, state: FSMContext, db: Database) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    await state.clear()
    await _send_my_games(message, db, message.from_user.id)


@router.message(F.text == texts.ABOUT_BOT_BUTTON)
async def about_bot_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ABOUT_BOT)


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _send_main_menu(callback.message)
    await callback.answer()


@router.callback_query(F.data == "my_games")
async def my_games_callback(callback: CallbackQuery, db: Database) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _send_my_games(callback.message, db, callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "cancel_dialog")
async def cancel_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(texts.CANCELLED, reply_markup=main_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.regexp(r"^game:\d+$"))
async def game_details_callback(
    callback: CallbackQuery,
    db: Database,
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        raise RuntimeError("Callback data is unavailable")
    game_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    try:
        details = await get_game_details(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error)
        return
    await _send_game_details(callback.message, details)
    await callback.answer()
