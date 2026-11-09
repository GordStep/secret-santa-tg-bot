from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message

from secret_santa.bot.i18n import button_labels


class ButtonText(Filter):
    """Match a message whose text equals a button label in any supported language."""

    def __init__(self, key: str) -> None:
        self.key = key

    async def __call__(self, message: Message) -> bool:
        return message.text is not None and message.text in button_labels(self.key)
