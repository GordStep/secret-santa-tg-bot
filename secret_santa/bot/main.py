from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from secret_santa.bot import texts
from secret_santa.bot.config import Config
from secret_santa.bot.db.database import Database
from secret_santa.bot.handlers.common import router as common_router
from secret_santa.bot.handlers.create_game import router as create_game_router
from secret_santa.bot.handlers.errors import handle_unexpected_error
from secret_santa.bot.handlers.join_game import router as join_game_router
from secret_santa.bot.handlers.organizer import router as organizer_router
from secret_santa.bot.handlers.participant import router as participant_router
from secret_santa.bot.handlers.settings import router as settings_router
from secret_santa.bot.middlewares import LanguageMiddleware

logger = logging.getLogger(__name__)


def _bot_commands(language: str) -> list[BotCommand]:
    return [
        BotCommand(command="start", description=texts.t(language, "command_start")),
        BotCommand(command="my_games", description=texts.t(language, "command_my_games")),
        BotCommand(command="cancel", description=texts.t(language, "command_cancel")),
    ]


async def run() -> None:
    config = Config.from_env()
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    db: Database | None = None
    try:
        db = await Database.connect(config.database_path)
        dispatcher = Dispatcher(storage=MemoryStorage())
        dispatcher.message.middleware(LanguageMiddleware())
        dispatcher.callback_query.middleware(LanguageMiddleware())
        dispatcher.errors.register(handle_unexpected_error)
        dispatcher.include_routers(
            common_router,
            settings_router,
            create_game_router,
            join_game_router,
            organizer_router,
            participant_router,
        )
        await bot.set_my_commands(_bot_commands("ru"))
        await bot.set_my_commands(_bot_commands("en"), language_code="en")
        await dispatcher.start_polling(bot, db=db, config=config)
    finally:
        if db is not None:
            await db.close()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()
