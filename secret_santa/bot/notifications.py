from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from secret_santa.bot import texts

logger = logging.getLogger(__name__)


async def notify_organizer_participant_joined(
    bot: Bot,
    organizer_id: int,
    game_name: str,
    user_id: int,
) -> None:
    try:
        await bot.send_message(
            organizer_id,
            texts.organizer_participant_joined(game_name, user_id),
        )
    except TelegramAPIError:
        logger.warning("Could not notify game organizer about a new participant")
