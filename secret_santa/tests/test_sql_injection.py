from __future__ import annotations

import pytest

from secret_santa.bot.db.database import Database
from secret_santa.bot.services.errors import InvalidCodeError
from secret_santa.bot.services.games import (
    create_game,
    get_game_details,
    join_game,
    list_user_games,
    validate_join,
)

MALICIOUS_NAME = "Party'); DROP TABLE games; --"
MALICIOUS_WISHES = "wishes'; DROP TABLE participants; --"
MALICIOUS_USERNAME = "user'); DELETE FROM games; --"
MALICIOUS_FIRST_NAME = "First'); UPDATE games SET code = 'XXXXXXXX'; --"
MALICIOUS_CODE = "' OR '1'='1"


@pytest.mark.asyncio
async def test_malicious_game_name_is_stored_verbatim(db: Database) -> None:
    game = await create_game(db, 900, MALICIOUS_NAME)

    assert game.name == MALICIOUS_NAME

    details = await get_game_details(db, game.id, 900)
    assert details.game.name == MALICIOUS_NAME
    assert [g.name for g in await list_user_games(db, 900)] == [MALICIOUS_NAME]


@pytest.mark.asyncio
async def test_malicious_wishes_and_names_are_stored_verbatim(db: Database) -> None:
    game = await create_game(db, 900, "Normal")

    await join_game(
        db,
        game.id,
        101,
        MALICIOUS_USERNAME,
        MALICIOUS_FIRST_NAME,
        MALICIOUS_WISHES,
    )

    details = await get_game_details(db, game.id, 900)
    participant = next(p for p in details.participants if p.user_id == 101)
    assert participant.username == MALICIOUS_USERNAME
    assert participant.first_name == MALICIOUS_FIRST_NAME
    assert participant.wishes == MALICIOUS_WISHES


@pytest.mark.asyncio
async def test_database_survives_drop_table_payload(db: Database) -> None:
    first = await create_game(db, 900, MALICIOUS_NAME)

    # The "DROP TABLE games" payload is data, not SQL: the schema stays intact.
    second = await create_game(db, 900, "Clean")
    assert second.id != first.id

    await join_game(
        db,
        second.id,
        101,
        MALICIOUS_USERNAME,
        MALICIOUS_FIRST_NAME,
        MALICIOUS_WISHES,
    )

    games = await list_user_games(db, 900)
    assert {g.id for g in games} == {first.id, second.id}

    details = await get_game_details(db, second.id, 900)
    assert details.participants[0].wishes == MALICIOUS_WISHES


@pytest.mark.asyncio
async def test_malicious_code_is_rejected_before_querying(db: Database) -> None:
    await create_game(db, 900, "Game")

    with pytest.raises(InvalidCodeError):
        await validate_join(db, MALICIOUS_CODE, 101)

    # An 8-character injection attempt still fails the [A-Z0-9] charset check.
    with pytest.raises(InvalidCodeError):
        await validate_join(db, "';SELECT", 101)


@pytest.mark.asyncio
async def test_injected_value_does_not_match_unrelated_rows(db: Database) -> None:
    first = await create_game(db, 900, "Real game")
    await create_game(db, 900, MALICIOUS_NAME)

    # The payload must not turn "code = ?" into a tautology that matches any row.
    with pytest.raises(InvalidCodeError):
        await validate_join(db, MALICIOUS_CODE, 101)

    games = await list_user_games(db, 900)
    assert {g.name for g in games} == {"Real game", MALICIOUS_NAME}
    assert first.name == "Real game"
