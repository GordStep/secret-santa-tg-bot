from __future__ import annotations

from collections.abc import Sequence

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from secret_santa.bot import texts
from secret_santa.bot.db.models import Game, GameStatus, Participant


def main_menu_keyboard(language: str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text=texts.t(language, "create_game_button"))
    builder.button(text=texts.t(language, "join_game_button"))
    builder.button(text=texts.t(language, "my_games_button"))
    builder.button(text=texts.t(language, "about_bot_button"))
    builder.button(text=texts.t(language, "settings_button"))
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def cancel_keyboard(language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.t(language, "cancel_button"), callback_data="cancel_dialog")
    return builder.as_markup()


def wishes_keyboard(language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.t(language, "skip_wishes_button"), callback_data="join:skip_wishes")
    builder.button(text=texts.t(language, "cancel_button"), callback_data="cancel_dialog")
    builder.adjust(1)
    return builder.as_markup()


def description_keyboard(language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.t(language, "skip_description_button"),
        callback_data="create:skip_description",
    )
    builder.button(text=texts.t(language, "cancel_button"), callback_data="cancel_dialog")
    builder.adjust(1)
    return builder.as_markup()


def games_keyboard(
    games: Sequence[Game],
    user_id: int,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for game in games:
        builder.button(
            text=texts.game_list_button(language, game, user_id),
            callback_data=f"game:{game.id}",
        )
    builder.button(text=texts.t(language, "main_menu_button"), callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def open_game_keyboard(game_id: int, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.t(language, "open_game_button"), callback_data=f"game:{game_id}")
    builder.button(text=texts.t(language, "back_to_games_button"), callback_data="my_games")
    builder.adjust(1)
    return builder.as_markup()


def game_keyboard(
    game: Game,
    is_organizer: bool,
    participant: Participant | None,
    language: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_organizer:
        if game.status == GameStatus.COLLECTING:
            builder.button(
                text=texts.t(language, "start_draw_button"),
                callback_data=f"organizer:start:{game.id}",
            )
        builder.button(text=texts.t(language, "refresh_button"), callback_data=f"game:{game.id}")
        if game.status != GameStatus.ARCHIVED:
            builder.button(
                text=texts.t(language, "edit_description_button"),
                callback_data=f"organizer:edit_description:{game.id}",
            )
            builder.button(
                text=texts.t(language, "archive_button"),
                callback_data=f"organizer:archive:{game.id}",
            )
        else:
            builder.button(
                text=texts.t(language, "delete_game_button"),
                callback_data=f"organizer:delete:{game.id}",
            )
    if participant is not None:
        builder.button(
            text=texts.t(language, "my_target_button"),
            callback_data=f"participant:target:{game.id}",
        )
        if game.status == GameStatus.STARTED and not participant.gift_ready:
            builder.button(
                text=texts.t(language, "gift_ready_button"),
                callback_data=f"participant:ready:{game.id}",
            )
    builder.button(text=texts.t(language, "back_to_games_button"), callback_data="my_games")
    builder.button(text=texts.t(language, "main_menu_button"), callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def archive_confirmation_keyboard(game_id: int, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.t(language, "confirm_archive_button"),
        callback_data=f"organizer:archive_confirm:{game_id}",
    )
    builder.button(text=texts.t(language, "cancel_button"), callback_data=f"game:{game_id}")
    builder.adjust(1)
    return builder.as_markup()


def delete_confirmation_keyboard(game_id: int, language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=texts.t(language, "confirm_delete_game_button"),
        callback_data=f"organizer:delete_confirm:{game_id}",
    )
    builder.button(text=texts.t(language, "cancel_button"), callback_data=f"game:{game_id}")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.t(language, "language_button"), callback_data="settings:language")
    builder.button(text=texts.t(language, "main_menu_button"), callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def language_keyboard(language: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=texts.t(language, "language_ru_label"), callback_data="settings:lang:ru")
    builder.button(text=texts.t(language, "language_en_label"), callback_data="settings:lang:en")
    builder.button(text=texts.t(language, "back_button"), callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()
