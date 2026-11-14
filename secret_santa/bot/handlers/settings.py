from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.filters import ButtonText
from secret_santa.bot.i18n import normalize_language
from secret_santa.bot.keyboards import language_keyboard, main_menu_keyboard, settings_keyboard
from secret_santa.bot.lang import set_user_language

router = Router(name="settings")


@router.message(ButtonText("settings_button"))
async def settings_button(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await message.answer(texts.t(lang, "settings_header"), reply_markup=settings_keyboard(lang))


@router.callback_query(F.data == "settings")
async def settings_callback(callback: CallbackQuery, lang: str) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.t(lang, "settings_header"),
        reply_markup=settings_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data == "settings:language")
async def language_callback(callback: CallbackQuery, lang: str) -> None:
    if not isinstance(callback.message, Message):
        raise RuntimeError("Callback message is unavailable")
    await callback.message.answer(
        texts.t(lang, "language_header"),
        reply_markup=language_keyboard(lang),
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^settings:lang:(ru|en)$"))
async def set_language_callback(callback: CallbackQuery, db: Database) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        raise RuntimeError("Callback data is unavailable")
    new_language = normalize_language(callback.data.rsplit(":", maxsplit=1)[1])
    await set_user_language(db, callback.from_user.id, new_language)
    await callback.message.answer(
        texts.t(new_language, "language_changed"),
        reply_markup=main_menu_keyboard(new_language),
    )
    await callback.answer()
