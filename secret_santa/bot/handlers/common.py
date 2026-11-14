from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.filters import ButtonText
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


async def _send_main_menu(message: Message, language: str) -> None:
    await message.answer(texts.t(language, "start_message"), reply_markup=main_menu_keyboard(language))


async def _send_my_games(
    message: Message,
    db: Database,
    user_id: int,
    language: str,
) -> None:
    games = await list_user_games(db, user_id)
    if not games:
        await message.answer(texts.t(language, "no_games"), reply_markup=main_menu_keyboard(language))
        return
    await message.answer(
        texts.t(language, "my_games_header"),
        reply_markup=games_keyboard(games, user_id, language),
    )


async def _send_game_details(
    message: Message,
    details: GameDetails,
    language: str,
) -> None:
    if details.is_organizer:
        text = texts.organizer_list(language, details.game, details.participants)
    elif details.participant is not None:
        text = texts.participant_game(language, details.game, details.participant)
    else:
        raise RuntimeError("Participant details are missing")
    await message.answer(
        text,
        reply_markup=game_keyboard(
            details.game,
            details.is_organizer,
            details.participant,
            language,
        ),
    )


async def _join_by_invite(
    message: Message,
    state: FSMContext,
    db: Database,
    code: str,
    language: str,
) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    try:
        game = await validate_join(db, code, message.from_user.id)
    except GameError as error:
        await notify_game_error(message, error, language)
        return
    await state.update_data(
        game_id=game.id,
        game_name=game.name,
        organizer_id=game.organizer_id,
    )
    await state.set_state(JoinGameState.waiting_for_wishes)
    await message.answer(texts.join_game_info(language, game))
    await message.answer(texts.t(language, "ask_wishes"), reply_markup=wishes_keyboard(language))


@router.message(CommandStart())
async def start_command(
    message: Message,
    state: FSMContext,
    db: Database,
    command: CommandObject,
    lang: str,
) -> None:
    await state.clear()
    if not command.args:
        await _send_main_menu(message, lang)
        return
    await _join_by_invite(message, state, db, command.args, lang)


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(texts.t(lang, "cancelled"), reply_markup=main_menu_keyboard(lang))


@router.message(Command("my_games"))
async def my_games_command(message: Message, db: Database, lang: str) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    await _send_my_games(message, db, message.from_user.id, lang)


@router.message(ButtonText("my_games_button"))
async def my_games_button(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    if message.from_user is None:
        raise RuntimeError("Message sender is missing")
    await state.clear()
    await _send_my_games(message, db, message.from_user.id, lang)


@router.message(ButtonText("about_bot_button"))
async def about_bot_button(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(texts.t(lang, "about_bot"))


@router.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _send_main_menu(callback.message, lang)
    await callback.answer()


@router.callback_query(F.data == "my_games")
async def my_games_callback(callback: CallbackQuery, db: Database, lang: str) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await _send_my_games(callback.message, db, callback.from_user.id, lang)
    await callback.answer()


@router.callback_query(F.data == "cancel_dialog")
async def cancel_callback(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(texts.t(lang, "cancelled"), reply_markup=main_menu_keyboard(lang))
    await callback.answer()


@router.callback_query(F.data.regexp(r"^game:\d+$"))
async def game_details_callback(
    callback: CallbackQuery,
    db: Database,
    lang: str,
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        raise RuntimeError("Callback data is unavailable")
    game_id = int(callback.data.rsplit(":", maxsplit=1)[1])
    try:
        details = await get_game_details(db, game_id, callback.from_user.id)
    except GameError as error:
        await notify_game_error(callback, error, lang)
        return
    await _send_game_details(callback.message, details, lang)
    await callback.answer()
