from __future__ import annotations

import asyncio

import pytest

from secret_santa.bot.db import repo
from secret_santa.bot.db.database import Database
from secret_santa.bot.db.models import GameStatus
from secret_santa.bot.lang import set_user_language
from secret_santa.bot.services.errors import (
    AlreadyJoinedError,
    GameAlreadyStartedError,
    GameArchivedError,
    GameNotArchivedError,
    GameNotCollectingError,
    GameNotFoundError,
    GameNotStartedError,
    InvalidCodeError,
    InvalidGameDescriptionError,
    NotEnoughParticipantsError,
    NotOrganizerError,
)
from secret_santa.bot.services.games import (
    archive_game,
    create_game,
    delete_archived_game,
    get_game_details,
    get_participant_target,
    join_game,
    list_user_games,
    mark_gift_ready,
    start_game,
    update_game_description,
    validate_join,
)


async def _join(
    db: Database,
    game_id: int,
    user_id: int,
    wishes: str | None = None,
) -> None:
    await join_game(
        db,
        game_id,
        user_id,
        f"user{user_id}",
        f"User {user_id}",
        wishes,
    )


@pytest.mark.asyncio
async def test_complete_game_flow(db: Database) -> None:
    game = await create_game(db, 900, "New Year")
    assert game.status == GameStatus.COLLECTING
    assert len(game.code) == 8

    await _join(db, game.id, 101, "Books")
    await _join(db, game.id, 102)
    result = await start_game(db, game.id, 900)

    assert result.game.status == GameStatus.STARTED
    assert {item.recipient_user_id for item in result.notifications} == {101, 102}
    assert len(result.notifications) == 2
    for notification in result.notifications:
        assert notification.recipient_user_id != notification.target.user_id

    first_view = await get_participant_target(db, game.id, 101)
    second_view = await get_participant_target(db, game.id, 101)
    assert first_view.target == second_view.target
    assert first_view.target.user_id == 102
    assert first_view.target.wishes is None

    ready = await mark_gift_ready(db, game.id, 101)
    assert ready.changed is True
    assert ready.participant.gift_ready is True
    repeated = await mark_gift_ready(db, game.id, 101)
    assert repeated.changed is False

    details = await get_game_details(db, game.id, 900)
    statuses = {item.user_id: item.gift_ready for item in details.participants}
    assert statuses == {101: True, 102: False}

    archived = await archive_game(db, game.id, 900)
    assert archived.status == GameStatus.ARCHIVED
    with pytest.raises(GameArchivedError):
        await validate_join(db, game.code, 103)
    with pytest.raises(GameArchivedError):
        await mark_gift_ready(db, game.id, 102)
    with pytest.raises(GameArchivedError):
        await start_game(db, game.id, 900)


@pytest.mark.asyncio
async def test_join_validation_and_duplicate_participation(db: Database) -> None:
    game = await create_game(db, 900, "Friends")
    with pytest.raises(InvalidCodeError):
        await validate_join(db, "not-a-code", 101)
    with pytest.raises(InvalidCodeError):
        await validate_join(db, "AAAAAAAA", 101)

    await _join(db, game.id, 101)
    with pytest.raises(AlreadyJoinedError):
        await validate_join(db, game.code.lower(), 101)
    with pytest.raises(AlreadyJoinedError):
        await _join(db, game.id, 101)


@pytest.mark.asyncio
async def test_start_requires_two_participants_and_organizer(db: Database) -> None:
    game = await create_game(db, 900, "Small game")
    await _join(db, game.id, 101)
    with pytest.raises(NotEnoughParticipantsError):
        await start_game(db, game.id, 900)
    with pytest.raises(NotOrganizerError):
        await start_game(db, game.id, 901)
    with pytest.raises(GameNotStartedError):
        await get_participant_target(db, game.id, 101)
    with pytest.raises(GameNotStartedError):
        await mark_gift_ready(db, game.id, 101)


@pytest.mark.asyncio
async def test_started_game_cannot_be_joined_or_restarted(db: Database) -> None:
    game = await create_game(db, 900, "Started game")
    await _join(db, game.id, 101)
    await _join(db, game.id, 102)
    await start_game(db, game.id, 900)

    with pytest.raises(GameNotCollectingError):
        await validate_join(db, game.code, 103)
    with pytest.raises(GameAlreadyStartedError):
        await start_game(db, game.id, 900)


@pytest.mark.asyncio
async def test_organizer_can_have_multiple_active_games(db: Database) -> None:
    first = await create_game(db, 900, "First")
    second = await create_game(db, 900, "Second")

    games = await list_user_games(db, 900)

    assert {game.id for game in games} == {first.id, second.id}
    assert all(game.status == GameStatus.COLLECTING for game in games)


@pytest.mark.asyncio
async def test_concurrent_game_creation_is_serialized(db: Database) -> None:
    games = await asyncio.gather(
        *(create_game(db, 900 + index, f"Game {index}") for index in range(10))
    )

    assert len(games) == 10
    assert len({game.id for game in games}) == 10
    assert len({game.code for game in games}) == 10


@pytest.mark.asyncio
async def test_organizer_can_delete_only_archived_game(db: Database) -> None:
    game = await create_game(db, 900, "Finished")
    await _join(db, game.id, 101)

    with pytest.raises(GameNotArchivedError):
        await delete_archived_game(db, game.id, 900)

    await archive_game(db, game.id, 900)
    with pytest.raises(NotOrganizerError):
        await delete_archived_game(db, game.id, 901)

    await delete_archived_game(db, game.id, 900)

    assert await list_user_games(db, 900) == ()
    assert await list_user_games(db, 101) == ()
    with pytest.raises(GameNotFoundError):
        await get_game_details(db, game.id, 900)


@pytest.mark.asyncio
async def test_game_description_is_normalized_and_optional(db: Database) -> None:
    game = await create_game(db, 900, "With description", "  Описание игры  ")
    assert game.description == "Описание игры"

    skipped = await create_game(db, 900, "Without description")
    assert skipped.description is None

    longest = await create_game(db, 900, "Long description", "x" * 3000)
    assert longest.description == "x" * 3000

    with pytest.raises(InvalidGameDescriptionError):
        await create_game(db, 900, "Too long", "x" * 3001)


@pytest.mark.asyncio
async def test_organizer_can_edit_description_until_game_is_archived(db: Database) -> None:
    game = await create_game(db, 900, "Editable", "Initial")

    with pytest.raises(NotOrganizerError):
        await update_game_description(db, game.id, 901, "Not allowed")

    updated = await update_game_description(db, game.id, 900, "  Before draw  ")
    assert updated.description == "Before draw"
    details = await get_game_details(db, game.id, 900)
    assert details.game.description == "Before draw"

    with pytest.raises(InvalidGameDescriptionError):
        await update_game_description(db, game.id, 900, "x" * 3001)

    await _join(db, game.id, 101)
    await _join(db, game.id, 102)
    await start_game(db, game.id, 900)
    started = await update_game_description(db, game.id, 900, "After draw")
    assert started.description == "After draw"

    await archive_game(db, game.id, 900)
    with pytest.raises(GameArchivedError):
        await update_game_description(db, game.id, 900, "Archived")


@pytest.mark.asyncio
async def test_language_write_and_game_creation_are_serialized(
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_set_user_language = repo.set_user_language
    write_started = asyncio.Event()
    finish_write = asyncio.Event()

    async def paused_set_user_language(
        database: Database,
        user_id: int,
        language_code: str,
    ) -> None:
        await original_set_user_language(database, user_id, language_code)
        write_started.set()
        await finish_write.wait()

    monkeypatch.setattr(repo, "set_user_language", paused_set_user_language)
    language_task = asyncio.create_task(set_user_language(db, 900, "en"))
    await write_started.wait()

    game_task = asyncio.create_task(create_game(db, 900, "Concurrent game"))
    await asyncio.sleep(0)
    game_was_blocked = not game_task.done()
    finish_write.set()
    await language_task
    game = await game_task

    assert game_was_blocked
    assert game.name == "Concurrent game"
    assert await repo.get_user_language(db, 900) == "en"
