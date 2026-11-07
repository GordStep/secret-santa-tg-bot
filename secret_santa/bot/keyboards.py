from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from secret_santa.bot import texts
from secret_santa.bot.db.models import Game, GameStatus, Participant


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=texts.CREATE_GAME_BUTTON)
    builder.button(text=texts.JOIN_GAME_BUTTON)
    builder.button(text=texts.MY_GAMES_BUTTON)
    builder.button(text=texts.ABOUT_BOT_BUTTON)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.CANCEL_BUTTON, callback_data="cancel_dialog")
    return builder.as_markup()


def wishes_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.SKIP_WISHES_BUTTON, callback_data="join:skip_wishes")
    builder.button(text=texts.CANCEL_BUTTON, callback_data="cancel_dialog")
    builder.adjust(1)
    return builder.as_markup()


def games_keyboard(games: Sequence[Game], user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for game in games:
        builder.button(
            text=texts.game_list_button(game, user_id),
            callback_data=f"game:{game.id}",
        )
    builder.button(text=texts.MAIN_MENU_BUTTON, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def open_game_keyboard(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.OPEN_GAME_BUTTON, callback_data=f"game:{game_id}")
    builder.button(text=texts.BACK_TO_GAMES_BUTTON, callback_data="my_games")
    builder.adjust(1)
    return builder.as_markup()


def game_keyboard(
    game: Game,
    is_organizer: bool,
    participant: Participant | None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_organizer:
        if game.status == GameStatus.COLLECTING:
            builder.button(
                text=texts.START_DRAW_BUTTON,
                callback_data=f"organizer:start:{game.id}",
            )
        builder.button(text=texts.REFRESH_BUTTON, callback_data=f"game:{game.id}")
        if game.status != GameStatus.ARCHIVED:
            builder.button(
                text=texts.ARCHIVE_BUTTON,
                callback_data=f"organizer:archive:{game.id}",
            )
        else:
            builder.button(
                text=texts.DELETE_GAME_BUTTON,
                callback_data=f"organizer:delete:{game.id}",
            )
    if participant is not None:
        builder.button(
            text=texts.MY_TARGET_BUTTON,
            callback_data=f"participant:target:{game.id}",
        )
        if game.status == GameStatus.STARTED and not participant.gift_ready:
            builder.button(
                text=texts.GIFT_READY_BUTTON,
                callback_data=f"participant:ready:{game.id}",
            )
    builder.button(text=texts.BACK_TO_GAMES_BUTTON, callback_data="my_games")
    builder.button(text=texts.MAIN_MENU_BUTTON, callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def archive_confirmation_keyboard(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.CONFIRM_ARCHIVE_BUTTON,
        callback_data=f"organizer:archive_confirm:{game_id}",
    )
    builder.button(text=texts.CANCEL_BUTTON, callback_data=f"game:{game_id}")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirmation_keyboard(game_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.CONFIRM_DELETE_GAME_BUTTON,
        callback_data=f"organizer:delete_confirm:{game_id}",
    )
    builder.button(text=texts.CANCEL_BUTTON, callback_data=f"game:{game_id}")
    builder.adjust(1)
    return builder.as_markup()
