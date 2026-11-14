from __future__ import annotations

import asyncio

import pytest

from secret_santa.bot.db.database import Database
from secret_santa.bot.db.models import GameStatus
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

    with pytest.raises(InvalidGameDescriptionError):
        await create_game(db, 900, "Too long", "x" * 1001)
