from __future__ import annotations

import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from secret_santa.bot.db import repo
from secret_santa.bot.db.database import Database
from secret_santa.bot.db.models import Game, GameStatus, Participant, Target
from secret_santa.bot.services.codes import CODE_ALPHABET, CODE_LENGTH, generate_unique_code
from secret_santa.bot.services.derangement import make_derangement
from secret_santa.bot.services.errors import (
    AlreadyJoinedError,
    GameAccessDeniedError,
    GameAlreadyStartedError,
    GameArchivedError,
    GameNotArchivedError,
    GameNotCollectingError,
    GameNotFoundError,
    GameNotStartedError,
    InvalidCodeError,
    InvalidGameDescriptionError,
    InvalidGameNameError,
    InvalidWishesError,
    NotEnoughParticipantsError,
    NotOrganizerError,
    NotParticipantError,
)

MAX_GAME_NAME_LENGTH = 100
MAX_GAME_DESCRIPTION_LENGTH = 3000
MAX_WISHES_LENGTH = 2000
P = ParamSpec("P")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class GameDetails:
    game: Game
    participant: Participant | None
    participants: tuple[Participant, ...]
    is_organizer: bool


@dataclass(frozen=True, slots=True)
class TargetNotification:
    recipient_user_id: int
    target: Target


@dataclass(frozen=True, slots=True)
class StartResult:
    game: Game
    notifications: tuple[TargetNotification, ...]


@dataclass(frozen=True, slots=True)
class TargetResult:
    game: Game
    participant: Participant
    target: Target


@dataclass(frozen=True, slots=True)
class GiftReadyResult:
    participant: Participant
    changed: bool


def _synchronized(
    function: Callable[Concatenate[Database, P], Awaitable[R]],
) -> Callable[Concatenate[Database, P], Awaitable[R]]:
    @wraps(function)
    async def wrapped(db: Database, *args: P.args, **kwargs: P.kwargs) -> R:
        async with db.lock:
            return await function(db, *args, **kwargs)

    return wrapped


def _normalize_game_name(name: str) -> str:
    normalized = name.strip()
    if not normalized or len(normalized) > MAX_GAME_NAME_LENGTH:
        raise InvalidGameNameError
    return normalized


def _normalize_game_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    if len(normalized) > MAX_GAME_DESCRIPTION_LENGTH:
        raise InvalidGameDescriptionError
    return normalized or None


def _normalize_wishes(wishes: str | None) -> str | None:
    if wishes is None:
        return None
    normalized = wishes.strip()
    if len(normalized) > MAX_WISHES_LENGTH:
        raise InvalidWishesError
    return normalized or None


async def _get_game(db: Database, game_id: int) -> Game:
    game = await repo.get_game_by_id(db, game_id)
    if game is None:
        raise GameNotFoundError
    return game


async def _ensure_can_join(
    db: Database,
    game: Game,
    user_id: int,
) -> None:
    if game.status == GameStatus.ARCHIVED:
        raise GameArchivedError
    if game.status != GameStatus.COLLECTING:
        raise GameNotCollectingError(game.status)
    if await repo.get_participant(db, game.id, user_id) is not None:
        raise AlreadyJoinedError


@_synchronized
async def create_game(
    db: Database,
    organizer_id: int,
    name: str,
    description: str | None = None,
) -> Game:
    normalized_name = _normalize_game_name(name)
    normalized_description = _normalize_game_description(description)
    created_at = datetime.now(timezone.utc).isoformat()
    await db.execute("BEGIN IMMEDIATE")
    try:
        while True:
            code = await generate_unique_code(db)
            try:
                game = await repo.insert_game(
                    db,
                    code,
                    normalized_name,
                    normalized_description,
                    organizer_id,
                    created_at,
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed: games.code" not in str(error):
                    raise
            else:
                break
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return game


@_synchronized
async def validate_join(
    db: Database,
    code: str,
    user_id: int,
) -> Game:
    normalized_code = code.strip().upper()
    if len(normalized_code) != CODE_LENGTH or any(
        char not in CODE_ALPHABET for char in normalized_code
    ):
        raise InvalidCodeError
    game = await repo.get_game_by_code(db, normalized_code)
    if game is None:
        raise InvalidCodeError
    await _ensure_can_join(db, game, user_id)
    return game


@_synchronized
async def join_game(
    db: Database,
    game_id: int,
    user_id: int,
    username: str | None,
    first_name: str,
    wishes: str | None,
) -> Participant:
    normalized_wishes = _normalize_wishes(wishes)
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        await _ensure_can_join(db, game, user_id)
        participant = await repo.insert_participant(
            db,
            game_id,
            user_id,
            username,
            first_name,
            normalized_wishes,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return participant


@_synchronized
async def list_user_games(db: Database, user_id: int) -> tuple[Game, ...]:
    return tuple(await repo.list_user_games(db, user_id))


@_synchronized
async def get_game_details(
    db: Database,
    game_id: int,
    user_id: int,
) -> GameDetails:
    game = await _get_game(db, game_id)
    participant = await repo.get_participant(db, game_id, user_id)
    is_organizer = game.organizer_id == user_id
    if not is_organizer and participant is None:
        raise GameAccessDeniedError
    participants = tuple(await repo.list_participants(db, game_id)) if is_organizer else ()
    return GameDetails(game, participant, participants, is_organizer)


def _ensure_can_edit_description(game: Game, organizer_id: int) -> None:
    if game.organizer_id != organizer_id:
        raise NotOrganizerError
    if game.status == GameStatus.ARCHIVED:
        raise GameArchivedError


@_synchronized
async def get_game_for_description_edit(
    db: Database,
    game_id: int,
    organizer_id: int,
) -> Game:
    game = await _get_game(db, game_id)
    _ensure_can_edit_description(game, organizer_id)
    return game


@_synchronized
async def update_game_description(
    db: Database,
    game_id: int,
    organizer_id: int,
    description: str | None,
) -> Game:
    normalized_description = _normalize_game_description(description)
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        _ensure_can_edit_description(game, organizer_id)
        await repo.set_game_description(db, game_id, normalized_description)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return replace(game, description=normalized_description)


@_synchronized
async def start_game(
    db: Database,
    game_id: int,
    organizer_id: int,
) -> StartResult:
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        if game.organizer_id != organizer_id:
            raise NotOrganizerError
        if game.status == GameStatus.ARCHIVED:
            raise GameArchivedError
        if game.status != GameStatus.COLLECTING:
            raise GameAlreadyStartedError
        participants = await repo.list_participants(db, game_id)
        if len(participants) < 2:
            raise NotEnoughParticipantsError
        pairs = make_derangement([participant.user_id for participant in participants])
        await repo.set_targets(db, game_id, pairs)
        await repo.set_game_status(db, game_id, GameStatus.STARTED)
        notifications = await repo.list_targets_for_game(db, game_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    started_game = replace(game, status=GameStatus.STARTED)
    return StartResult(
        started_game,
        tuple(TargetNotification(recipient, target) for recipient, target in notifications),
    )


@_synchronized
async def archive_game(
    db: Database,
    game_id: int,
    organizer_id: int,
) -> Game:
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        if game.organizer_id != organizer_id:
            raise NotOrganizerError
        if game.status == GameStatus.ARCHIVED:
            raise GameArchivedError
        await repo.set_game_status(db, game_id, GameStatus.ARCHIVED)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return replace(game, status=GameStatus.ARCHIVED)


@_synchronized
async def delete_archived_game(db: Database, game_id: int, organizer_id: int) -> None:
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        if game.organizer_id != organizer_id:
            raise NotOrganizerError
        if game.status != GameStatus.ARCHIVED:
            raise GameNotArchivedError
        await repo.delete_game(db, game_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def _get_participant_for_wishes_edit(
    db: Database,
    game_id: int,
    user_id: int,
) -> Participant:
    game = await _get_game(db, game_id)
    participant = await repo.get_participant(db, game_id, user_id)
    if participant is None:
        raise NotParticipantError
    if game.status == GameStatus.ARCHIVED:
        raise GameArchivedError
    return participant


@_synchronized
async def get_participant_for_wishes_edit(
    db: Database,
    game_id: int,
    user_id: int,
) -> Participant:
    return await _get_participant_for_wishes_edit(db, game_id, user_id)


@_synchronized
async def update_participant_wishes(
    db: Database,
    game_id: int,
    user_id: int,
    wishes: str | None,
) -> Participant:
    normalized_wishes = _normalize_wishes(wishes)
    await db.execute("BEGIN IMMEDIATE")
    try:
        participant = await _get_participant_for_wishes_edit(db, game_id, user_id)
        await repo.set_participant_wishes(db, game_id, user_id, normalized_wishes)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return replace(participant, wishes=normalized_wishes)


@_synchronized
async def get_participant_target(
    db: Database,
    game_id: int,
    user_id: int,
) -> TargetResult:
    game = await _get_game(db, game_id)
    participant = await repo.get_participant(db, game_id, user_id)
    if participant is None:
        raise NotParticipantError
    if game.status == GameStatus.COLLECTING or participant.target_user_id is None:
        raise GameNotStartedError
    target = await repo.get_target(db, game_id, user_id)
    if target is None:
        raise RuntimeError("Stored target is missing")
    return TargetResult(game, participant, target)


@_synchronized
async def mark_gift_ready(
    db: Database,
    game_id: int,
    user_id: int,
) -> GiftReadyResult:
    await db.execute("BEGIN IMMEDIATE")
    try:
        game = await _get_game(db, game_id)
        participant = await repo.get_participant(db, game_id, user_id)
        if participant is None:
            raise NotParticipantError
        if game.status == GameStatus.ARCHIVED:
            raise GameArchivedError
        if game.status != GameStatus.STARTED:
            raise GameNotStartedError
        changed = not participant.gift_ready
        if changed:
            await repo.set_gift_ready(db, game_id, user_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return GiftReadyResult(replace(participant, gift_ready=True), changed)
