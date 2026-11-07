from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from secret_santa.bot.db.database import Database
from secret_santa.bot.db.models import Game, GameStatus, Participant, Target


def _to_game(row: sqlite3.Row) -> Game:
    return Game(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        organizer_id=row["organizer_id"],
        status=GameStatus(row["status"]),
        created_at=row["created_at"],
    )


def _to_participant(row: sqlite3.Row) -> Participant:
    return Participant(
        id=row["id"],
        game_id=row["game_id"],
        user_id=row["user_id"],
        username=row["username"],
        first_name=row["first_name"],
        wishes=row["wishes"],
        gift_ready=bool(row["gift_ready"]),
        target_user_id=row["target_user_id"],
    )


async def code_exists(db: Database, code: str) -> bool:
    async with db.execute("SELECT 1 FROM games WHERE code = ?", (code,)) as cursor:
        return await cursor.fetchone() is not None


async def get_game_by_id(db: Database, game_id: int) -> Game | None:
    async with db.execute("SELECT * FROM games WHERE id = ?", (game_id,)) as cursor:
        row = await cursor.fetchone()
    return _to_game(row) if row is not None else None


async def get_game_by_code(db: Database, code: str) -> Game | None:
    async with db.execute("SELECT * FROM games WHERE code = ?", (code,)) as cursor:
        row = await cursor.fetchone()
    return _to_game(row) if row is not None else None


async def list_user_games(db: Database, user_id: int) -> list[Game]:
    query = """
        SELECT DISTINCT g.*
        FROM games AS g
        LEFT JOIN participants AS p ON p.game_id = g.id
        WHERE g.organizer_id = ? OR p.user_id = ?
        ORDER BY g.created_at DESC, g.id DESC
    """
    async with db.execute(query, (user_id, user_id)) as cursor:
        rows = await cursor.fetchall()
    return [_to_game(row) for row in rows]


async def insert_game(
    db: Database,
    code: str,
    name: str,
    organizer_id: int,
    created_at: str,
) -> Game:
    query = """
        INSERT INTO games (code, name, organizer_id, status, created_at)
        VALUES (?, ?, ?, ?, ?)
    """
    cursor = await db.execute(
        query,
        (code, name, organizer_id, GameStatus.COLLECTING, created_at),
    )
    game_id = cursor.lastrowid
    await cursor.close()
    if game_id is None:
        raise RuntimeError("SQLite did not return a game ID")
    return Game(game_id, code, name, organizer_id, GameStatus.COLLECTING, created_at)


async def get_participant(
    db: Database,
    game_id: int,
    user_id: int,
) -> Participant | None:
    query = "SELECT * FROM participants WHERE game_id = ? AND user_id = ?"
    async with db.execute(query, (game_id, user_id)) as cursor:
        row = await cursor.fetchone()
    return _to_participant(row) if row is not None else None


async def list_participants(
    db: Database,
    game_id: int,
) -> list[Participant]:
    query = "SELECT * FROM participants WHERE game_id = ? ORDER BY id"
    async with db.execute(query, (game_id,)) as cursor:
        rows = await cursor.fetchall()
    return [_to_participant(row) for row in rows]


async def insert_participant(
    db: Database,
    game_id: int,
    user_id: int,
    username: str | None,
    first_name: str,
    wishes: str | None,
) -> Participant:
    query = """
        INSERT INTO participants (game_id, user_id, username, first_name, wishes)
        VALUES (?, ?, ?, ?, ?)
    """
    cursor = await db.execute(query, (game_id, user_id, username, first_name, wishes))
    participant_id = cursor.lastrowid
    await cursor.close()
    if participant_id is None:
        raise RuntimeError("SQLite did not return a participant ID")
    return Participant(
        participant_id,
        game_id,
        user_id,
        username,
        first_name,
        wishes,
        False,
        None,
    )


async def set_game_status(
    db: Database,
    game_id: int,
    status: GameStatus,
) -> None:
    cursor = await db.execute(
        "UPDATE games SET status = ? WHERE id = ?",
        (status, game_id),
    )
    await cursor.close()


async def delete_game(db: Database, game_id: int) -> None:
    cursor = await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
    await cursor.close()


async def set_targets(
    db: Database,
    game_id: int,
    pairs: Mapping[int, int],
) -> None:
    values = [(receiver, game_id, giver) for giver, receiver in pairs.items()]
    cursor = await db.executemany(
        """
        UPDATE participants
        SET target_user_id = ?
        WHERE game_id = ? AND user_id = ?
        """,
        values,
    )
    await cursor.close()


async def set_gift_ready(
    db: Database,
    game_id: int,
    user_id: int,
) -> None:
    cursor = await db.execute(
        """
        UPDATE participants
        SET gift_ready = 1
        WHERE game_id = ? AND user_id = ?
        """,
        (game_id, user_id),
    )
    await cursor.close()


async def get_target(
    db: Database,
    game_id: int,
    giver_id: int,
) -> Target | None:
    query = """
        SELECT target.user_id, target.username, target.first_name, target.wishes
        FROM participants AS giver
        JOIN participants AS target
            ON target.game_id = giver.game_id
            AND target.user_id = giver.target_user_id
        WHERE giver.game_id = ? AND giver.user_id = ?
    """
    async with db.execute(query, (game_id, giver_id)) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    return Target(row["user_id"], row["username"], row["first_name"], row["wishes"])


async def list_targets_for_game(
    db: Database,
    game_id: int,
) -> list[tuple[int, Target]]:
    query = """
        SELECT
            giver.user_id AS recipient_user_id,
            target.user_id AS target_user_id,
            target.username AS target_username,
            target.first_name AS target_first_name,
            target.wishes AS target_wishes
        FROM participants AS giver
        JOIN participants AS target
            ON target.game_id = giver.game_id
            AND target.user_id = giver.target_user_id
        WHERE giver.game_id = ?
        ORDER BY giver.id
    """
    async with db.execute(query, (game_id,)) as cursor:
        rows = await cursor.fetchall()
    return [
        (
            row["recipient_user_id"],
            Target(
                row["target_user_id"],
                row["target_username"],
                row["target_first_name"],
                row["target_wishes"],
            ),
        )
        for row in rows
    ]
