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
from secret_santa.bot.handlers.settings import router as settings_router
from secret_santa.bot.middlewares import LanguageMiddleware
from secret_santa.bot.services.games import get_game_details, list_user_games


@pytest.fixture(scope="module")
def dispatcher() -> Dispatcher:
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
    return dispatcher


def _bot() -> Bot:
    bot = Bot(token="123456:test-token")
    bot.session = AsyncMock()
    bot.get_me = AsyncMock(
        return_value=User(
            id=123456,
            is_bot=True,
            first_name="Secret Santa",
            username="secret_santa_test_bot",
        )
    )
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


def _user(user_id: int, language_code: str | None = None) -> User:
    return User(
        id=user_id,
        is_bot=False,
        first_name=f"User {user_id}",
        username=f"user{user_id}",
        language_code=language_code,
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


def _keyboard_texts(bot: Bot) -> list[list[str]]:
    menu_message = _send_messages(bot)[-1]
    assert menu_message.reply_markup is not None
    return [[button.text for button in row] for row in menu_message.reply_markup.keyboard]


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
    await _feed(dispatcher, bot, db, _update(organizer, 3, "Gift exchange for the lab"))
    games = await list_user_games(db, 900)
    assert len(games) == 1
    game = games[0]
    assert game.description == "Gift exchange for the lab"
    assert any("Party &lt;b&gt;" in method.text for method in _send_messages(bot))
    invite_link = f"https://t.me/secret_santa_test_bot?start={game.code}"
    assert any(invite_link in method.text for method in _send_messages(bot))

    await _feed(dispatcher, bot, db, _callback(first, 4, "join_game"))
    await _feed(dispatcher, bot, db, _update(first, 5, game.code.lower()))
    await _feed(dispatcher, bot, db, _update(first, 6, "<i>Books</i>"))
    await _feed(dispatcher, bot, db, _callback(second, 7, "join_game"))
    await _feed(dispatcher, bot, db, _update(second, 8, game.code))
    await _feed(dispatcher, bot, db, _callback(second, 9, "join:skip_wishes"))
    organizer_messages = [
        method for method in _send_messages(bot) if method.chat_id == organizer.id
    ]
    assert any(
        method.text == "К игре: <b>Party &lt;b&gt;</b> присоединился @user101"
        for method in organizer_messages
    )
    assert any(
        method.text == "К игре: <b>Party &lt;b&gt;</b> присоединился @user102"
        for method in organizer_messages
    )

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 10, f"organizer:start:{game.id}"),
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
        _callback(first, 11, f"participant:ready:{game.id}"),
    )
    details = await get_game_details(db, game.id, 900)
    readiness = {item.user_id: item.gift_ready for item in details.participants}
    assert readiness == {101: True, 102: False}

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 12, f"organizer:archive:{game.id}"),
    )
    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 13, f"organizer:archive_confirm:{game.id}"),
    )
    details = await get_game_details(db, game.id, 900)
    assert details.game.status == GameStatus.ARCHIVED

    await _feed(
        dispatcher,
        bot,
        db,
        _callback(second, 14, f"participant:ready:{game.id}"),
    )
    assert any(
        method.text == texts.t("ru", "game_archived") for method in _callback_answers(bot)
    )
    await bot.session.close()


@pytest.mark.asyncio
async def test_archived_game_deletion_flow(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "Finished"))
    await _feed(dispatcher, bot, db, _callback(organizer, 3, "create:skip_description"))
    game = (await list_user_games(db, organizer.id))[0]
    await _feed(dispatcher, bot, db, _callback(organizer, 4, f"organizer:archive:{game.id}"))
    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 5, f"organizer:archive_confirm:{game.id}"),
    )

    await _feed(dispatcher, bot, db, _callback(organizer, 6, f"game:{game.id}"))
    game_markup = _send_messages(bot)[-1].reply_markup
    assert game_markup is not None
    assert any(
        button.text == texts.t("ru", "delete_game_button")
        and button.callback_data == f"organizer:delete:{game.id}"
        for row in game_markup.inline_keyboard
        for button in row
    )

    await _feed(dispatcher, bot, db, _callback(organizer, 7, f"organizer:delete:{game.id}"))
    assert _send_messages(bot)[-1].text == texts.t("ru", "delete_confirmation")
    await _feed(
        dispatcher,
        bot,
        db,
        _callback(organizer, 8, f"organizer:delete_confirm:{game.id}"),
    )

    assert await list_user_games(db, organizer.id) == ()
    assert _send_messages(bot)[-1].text == texts.t("ru", "deleted_success")
    await bot.session.close()


@pytest.mark.asyncio
async def test_invite_link_asks_for_wishes_and_joins_user(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)
    participant = _user(101)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "Deep link"))
    await _feed(dispatcher, bot, db, _callback(organizer, 3, "create:skip_description"))
    game = (await list_user_games(db, organizer.id))[0]

    await _feed(dispatcher, bot, db, _update(participant, 4, f"/start {game.code}"))

    assert _send_messages(bot)[-1].text == texts.t("ru", "ask_wishes")
    assert await list_user_games(db, participant.id) == ()

    await _feed(dispatcher, bot, db, _update(participant, 5, "Books"))
    details = await get_game_details(db, game.id, participant.id)
    assert details.participant is not None
    assert details.participant.wishes == "Books"
    assert any(
        method.chat_id == participant.id and method.text == texts.joined_game("ru", game.name)
        for method in _send_messages(bot)
    )
    expected_notification = texts.organizer_participant_joined(
        "ru",
        game.name,
        participant.username,
        participant.first_name,
    )
    assert any(
        method.chat_id == organizer.id and method.text == expected_notification
        for method in _send_messages(bot)
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
    assert any(method.text == texts.t("ru", "cancelled") for method in _send_messages(bot))
    await bot.session.close()


@pytest.mark.asyncio
async def test_reply_main_menu_buttons(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    user = _user(900)

    await _feed(dispatcher, bot, db, _update(user, 1, "/start"))
    menu_message = _send_messages(bot)[-1]
    assert menu_message.text == texts.t("ru", "start_message")
    assert menu_message.reply_markup is not None
    assert menu_message.reply_markup.resize_keyboard is True
    assert [
        [button.text for button in row]
        for row in menu_message.reply_markup.keyboard
    ] == [
        [texts.t("ru", "create_game_button"), texts.t("ru", "join_game_button")],
        [texts.t("ru", "my_games_button"), texts.t("ru", "about_bot_button")],
        [texts.t("ru", "settings_button")],
    ]

    await _feed(dispatcher, bot, db, _update(user, 2, texts.t("ru", "about_bot_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "about_bot")

    await _feed(dispatcher, bot, db, _update(user, 3, texts.t("ru", "my_games_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "no_games")

    await _feed(dispatcher, bot, db, _update(user, 4, texts.t("ru", "create_game_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "ask_game_name")

    await _feed(dispatcher, bot, db, _update(user, 5, texts.t("ru", "about_bot_button")))
    await _feed(dispatcher, bot, db, _update(user, 6, texts.t("ru", "join_game_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "ask_code")
    await bot.session.close()


@pytest.mark.asyncio
async def test_english_localization(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    user = _user(700, language_code="en")

    await _feed(dispatcher, bot, db, _update(user, 1, "/start"))
    menu_message = _send_messages(bot)[-1]
    assert menu_message.text == texts.t("en", "start_message")
    assert menu_message.reply_markup is not None
    assert [
        [button.text for button in row]
        for row in menu_message.reply_markup.keyboard
    ] == [
        [texts.t("en", "create_game_button"), texts.t("en", "join_game_button")],
        [texts.t("en", "my_games_button"), texts.t("en", "about_bot_button")],
        [texts.t("en", "settings_button")],
    ]
    await bot.session.close()


@pytest.mark.asyncio
async def test_unknown_language_falls_back_to_russian(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    user = _user(701, language_code="fr")

    await _feed(dispatcher, bot, db, _update(user, 1, "/start"))
    assert _send_messages(bot)[-1].text == texts.t("ru", "start_message")
    await bot.session.close()


@pytest.mark.asyncio
async def test_settings_language_switch_persists(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    user = _user(702, language_code="en")

    await _feed(dispatcher, bot, db, _update(user, 1, "/start"))
    await _feed(dispatcher, bot, db, _update(user, 2, texts.t("en", "settings_button")))
    assert _send_messages(bot)[-1].text == texts.t("en", "settings_header")

    await _feed(dispatcher, bot, db, _callback(user, 3, "settings:lang:ru"))
    assert _send_messages(bot)[-1].text == texts.t("ru", "language_changed")

    await _feed(dispatcher, bot, db, _update(user, 4, "/start"))
    assert _send_messages(bot)[-1].text == texts.t("ru", "start_message")
    assert _keyboard_texts(bot) == [
        [texts.t("ru", "create_game_button"), texts.t("ru", "join_game_button")],
        [texts.t("ru", "my_games_button"), texts.t("ru", "about_bot_button")],
        [texts.t("ru", "settings_button")],
    ]
    await bot.session.close()


@pytest.mark.asyncio
async def test_settings_button_interrupts_dialog(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    user = _user(703, language_code="ru")

    await _feed(dispatcher, bot, db, _update(user, 1, texts.t("ru", "create_game_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "ask_game_name")

    await _feed(dispatcher, bot, db, _update(user, 2, texts.t("ru", "settings_button")))
    assert _send_messages(bot)[-1].text == texts.t("ru", "settings_header")
    await bot.session.close()


@pytest.mark.asyncio
async def test_target_notifications_use_recipient_language(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(800, language_code="en")
    first = _user(801, language_code="ru")
    second = _user(802, language_code="en")

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "Mixed"))
    await _feed(dispatcher, bot, db, _callback(organizer, 3, "create:skip_description"))
    game = (await list_user_games(db, organizer.id))[0]

    await _feed(dispatcher, bot, db, _callback(first, 4, "join_game"))
    await _feed(dispatcher, bot, db, _update(first, 5, game.code))
    await _feed(dispatcher, bot, db, _callback(first, 6, "join:skip_wishes"))

    await _feed(dispatcher, bot, db, _callback(second, 7, "join_game"))
    await _feed(dispatcher, bot, db, _update(second, 8, game.code))
    await _feed(dispatcher, bot, db, _callback(second, 9, "join:skip_wishes"))

    await _feed(dispatcher, bot, db, _callback(organizer, 10, f"organizer:start:{game.id}"))

    first_messages = [method for method in _send_messages(bot) if method.chat_id == first.id]
    second_messages = [method for method in _send_messages(bot) if method.chat_id == second.id]
    assert any(
        method.text.startswith("Игра: <b>Mixed</b>") for method in first_messages
    )
    assert any(
        method.text.startswith("Game: <b>Mixed</b>") for method in second_messages
    )
    await bot.session.close()


@pytest.mark.asyncio
async def test_game_description_is_shown_when_joining_and_selecting(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)
    participant = _user(101)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "Secret Santa"))
    assert _send_messages(bot)[-1].text == texts.t("ru", "ask_game_description")

    await _feed(dispatcher, bot, db, _update(organizer, 3, "Дарим подарки коллегам"))
    game = (await list_user_games(db, organizer.id))[0]
    assert game.description == "Дарим подарки коллегам"

    # Selecting the game from "My games" shows the description in the organizer view.
    await _feed(dispatcher, bot, db, _callback(organizer, 4, f"game:{game.id}"))
    assert any(
        "Описание: Дарим подарки коллегам" in method.text
        for method in _send_messages(bot)
    )

    # Joining shows the description before asking for wishes.
    await _feed(dispatcher, bot, db, _callback(participant, 5, "join_game"))
    await _feed(dispatcher, bot, db, _update(participant, 6, game.code))
    participant_join_messages = [
        method for method in _send_messages(bot) if method.chat_id == participant.id
    ]
    assert any(
        method.text == texts.join_game_info("ru", game)
        for method in participant_join_messages
    )

    # The participant view also shows the description after opening the game.
    await _feed(dispatcher, bot, db, _callback(participant, 7, "join:skip_wishes"))
    await _feed(dispatcher, bot, db, _callback(participant, 8, f"game:{game.id}"))
    participant_messages = [
        method for method in _send_messages(bot) if method.chat_id == participant.id
    ]
    assert any(
        "Описание: Дарим подарки коллегам" in method.text
        for method in participant_messages
    )
    await bot.session.close()


@pytest.mark.asyncio
async def test_skipping_description_creates_game_without_it(
    db: Database,
    dispatcher: Dispatcher,
) -> None:
    bot = _bot()
    organizer = _user(900)

    await _feed(dispatcher, bot, db, _callback(organizer, 1, "create_game"))
    await _feed(dispatcher, bot, db, _update(organizer, 2, "No description"))
    await _feed(dispatcher, bot, db, _callback(organizer, 3, "create:skip_description"))

    game = (await list_user_games(db, organizer.id))[0]
    assert game.description is None
    assert texts.game_description("ru", None) == texts.t("ru", "description_not_provided")
    await bot.session.close()
