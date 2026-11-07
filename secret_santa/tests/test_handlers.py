from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from secret_santa.bot import texts
from secret_santa.bot.db.database import Database
from secret_santa.bot.db.models import GameStatus
from secret_santa.bot.handlers.common import router as common_router
from secret_santa.bot.handlers.create_game import router as create_game_router
from secret_santa.bot.handlers.errors import handle_unexpected_error
from secret_santa.bot.handlers.join_game import router as join_game_router
from secret_santa.bot.handlers.organizer import router as organizer_router
from secret_santa.bot.handlers.participant import router as participant_router
from secret_santa.bot.services.games import get_game_details, list_user_games


@pytest.fixture(scope="module")
def dispatcher() -> Dispatcher:
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.errors.register(handle_unexpected_error)
    dispatcher.include_routers(
        common_router,
        create_game_router,
        join_game_router,
        organizer_router,
        participant_router,
    )
    return dispatcher


def _bot() -> Bot:
    bot = Bot(token="123456:test-token")
    bot.session = AsyncMock()
    return bot


def _send_messages(bot: Bot) -> list[SendMessage]:
    return [
        call.args[1]
        for call in bot.session.await_args_list
        if len(call.args) > 1 and isinstance(call.args[1], SendMessage)
    ]


def _callback_answers(bot: Bot) -> list[AnswerCallbackQuery]:
    return [
        call.args[1]
        for call in bot.session.await_args_list
        if len(call.args) > 1 and isinstance(call.args[1], AnswerCallbackQuery)
    ]


def _user(user_id: int) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name=f"User {user_id}",
        username=f"user{user_id}",
    )


def _message(user: User, text: str) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=Chat(id=user.id, type="private"),
        from_user=user,
        text=text,
    )


def _update(user: User, update_id: int, text: str) -> Update:
    return Update(update_id=update_id, message=_message(user, text))


def _callback(user: User, update_id: int, data: str) -> Update:
    callback = CallbackQuery(
        id=str(update_id),
        from_user=user,
        chat_instance="test-chat",
        data=data,
        message=_message(user, "menu"),
    )
    return Update(update_id=update_id, callback_query=callback)


async def _feed(
    dispatcher: Dispatcher,
    bot: Bot,
    db: Database,
    update: Update,
) -> None:
    result = await dispatcher.feed_update(bot, update, db=db)
    assert result is not False


@pytest.mark.asyncio
async def test_handler_game_flow_without_network(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)
    first = _user(101)
    second = _user(102)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "Party <b>"))
    games = await list_user_games(db, 900)
    assert len(games) == 1
    game = games[0]
    assert any("Party &lt;b&gt;" in method.text for method in _send_messages(bot))

    await _feed(dispatcher, bot, db, _callback(first, 3, "join_game"))
    await _feed(dispatcher, bot, db, _update(first, 4, game.code.lower()))
    await _feed(dispatcher, bot, db, _update(first, 5, "<i>Books</i>"))
    await _feed(dispatcher, bot, db, _callback(second, 6, "join_game"))
    await _feed(dispatcher, bot, db, _update(second, 7, game.code))
    await _feed(dispatcher, bot, db, _callback(second, 8, "join:skip_wishes"))

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 9, f"organizer:start:{game.id}"),
    )
    details = await get_game_details(db, game.id, 900)
    assert details.game.status == GameStatus.STARTED
    assert all(item.target_user_id != item.user_id for item in details.participants)
    assert any(
        "&lt;i&gt;Books&lt;/i&gt;" in method.text for method in _send_messages(bot)
    )

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(first, 10, f"participant:ready:{game.id}"),
    )
    details = await get_game_details(db, game.id, 900)
    readiness = {item.user_id: item.gift_ready for item in details.participants}
    assert readiness == {101: True, 102: False}

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 11, f"organizer:archive:{game.id}"),
    )
    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 12, f"organizer:archive_confirm:{game.id}"),
    )
    details = await get_game_details(db, game.id, 900)
    assert details.game.status == GameStatus.ARCHIVED

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(second, 13, f"participant:ready:{game.id}"),
    )
    assert any(
        method.text == texts.GAME_ARCHIVED for method in _callback_answers(bot)
    )
    await bot.session.close()


@pytest.mark.asyncio
async def test_cancel_command_interrupts_fsm(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "/cancel"))

    assert await list_user_games(db, 900) == ()
    assert any(method.text == texts.CANCELLED for method in _send_messages(bot))
    await bot.session.close()
