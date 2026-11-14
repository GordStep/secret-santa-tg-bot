from __future__ import annotations

import random
import string
from unittest.mock import AsyncMock, Mock

import pytest

from secret_santa.bot.db import repo
from secret_santa.bot.db.database import Database
from secret_santa.bot.services import codes
from secret_santa.bot.services.games import create_game


def test_code_has_required_length_and_charset() -> None:
    for _ in range(100):
        code = codes.generate_code()
        assert len(code) == 8
        assert set(code) <= set(string.ascii_uppercase + string.digits)


def test_code_generation_retries_on_collision() -> None:
    rng = Mock(spec=random.Random)
    rng.choice.side_effect = list("AAAAAAAA" + "BBBBBBBB")
    code = codes.generate_code(lambda candidate: candidate != "AAAAAAAA", rng=rng)
    assert code == "BBBBBBBB"
    assert rng.choice.call_count == 16


@pytest.mark.asyncio
async def test_database_code_generation_retries_on_collision(
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await repo.insert_game(db, "AAAAAAAA", "First game", None, 1, "2026-01-01T00:00:00+00:00")
    await db.commit()
    generated = iter(["AAAAAAAA", "BBBBBBBB"])
    monkeypatch.setattr(codes, "generate_code", lambda: next(generated))

    code = await codes.generate_unique_code(db)

    assert code == "BBBBBBBB"


@pytest.mark.asyncio
async def test_create_game_retries_code_collision_on_insert(
    db: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await repo.insert_game(db, "AAAAAAAA", "First game", None, 1, "2026-01-01T00:00:00+00:00")
    await db.commit()
    generate_unique_code = AsyncMock(side_effect=["AAAAAAAA", "BBBBBBBB"])
    monkeypatch.setattr(
        "secret_santa.bot.services.games.generate_unique_code",
        generate_unique_code,
    )

    game = await create_game(db, 900, "Second game")

    assert game.code == "BBBBBBBB"
    assert generate_unique_code.await_count == 2
