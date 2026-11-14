from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, Message

from secret_santa.bot import texts
from secret_santa.bot.db.models import Game

TELEGRAM_MESSAGE_TEXT_LIMIT = 4096


async def _answer_html_lines(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > TELEGRAM_MESSAGE_TEXT_LIMIT:
            raise ValueError("A single HTML-formatted line exceeds Telegram's message limit")
        if current and len(current) + len(line) > TELEGRAM_MESSAGE_TEXT_LIMIT:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    for index, chunk in enumerate(chunks):
        await message.answer(
            chunk,
            reply_markup=reply_markup if index == len(chunks) - 1 else None,
        )


async def answer_game_message(
    message: Message,
    language: str,
    game: Game,
    text: str,
    brief_text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if len(text) <= TELEGRAM_MESSAGE_TEXT_LIMIT:
        await message.answer(text, reply_markup=reply_markup)
        return
    if game.description is not None:
        await message.answer(
            texts.description_message(language, game.description),
            parse_mode=None,
        )
        text = brief_text
    await _answer_html_lines(message, text, reply_markup)
