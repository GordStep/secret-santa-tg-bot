from __future__ import annotations

import html
from collections.abc import Sequence

from secret_santa.bot.db.models import Game, GameStatus, Participant, Target
from secret_santa.bot.i18n import translate as t

__all__ = [
    "description_message",
    "display_name",
    "game_created",
    "game_description",
    "game_list_button",
    "join_game_info",
    "joined_game",
    "organizer_list",
    "organizer_participant_joined",
    "participant_game",
    "start_result",
    "status_text",
    "t",
    "target_assignment",
]


def status_text(language: str, status: GameStatus) -> str:
    key = {
        GameStatus.COLLECTING: "status_collecting",
        GameStatus.STARTED: "status_started",
        GameStatus.ARCHIVED: "status_archived",
    }[status]
    return t(language, key)


def display_name(username: str | None, first_name: str) -> str:
    return f"@{username}" if username else first_name


def game_description(language: str, description: str | None) -> str:
    if description is None:
        return t(language, "description_not_provided")
    return html.escape(description)


def description_message(language: str, description: str) -> str:
    return t(language, "description_message", description=description)


def game_list_button(language: str, game: Game, user_id: int) -> str:
    role_key = "role_organizer" if game.organizer_id == user_id else "role_participant"
    return t(
        language,
        "game_list_button",
        name=game.name,
        role=t(language, role_key),
        status=status_text(language, game.status),
    )


def game_created(language: str, game: Game, bot_username: str) -> str:
    return t(
        language,
        "game_created",
        name=html.escape(game.name),
        code=html.escape(game.code),
        invite_link=html.escape(f"https://t.me/{bot_username}?start={game.code}"),
    )


def joined_game(language: str, game_name: str) -> str:
    return t(language, "joined_game", name=html.escape(game_name))


def join_game_info(
    language: str,
    game: Game,
    include_description: bool = True,
) -> str:
    key = "join_game_info" if include_description else "join_game_info_brief"
    return t(
        language,
        key,
        name=html.escape(game.name),
        description=game_description(language, game.description),
    )


def organizer_participant_joined(
    language: str,
    game_name: str,
    username: str | None,
    first_name: str,
) -> str:
    return t(
        language,
        "organizer_participant_joined",
        game_name=html.escape(game_name),
        name=html.escape(display_name(username, first_name)),
    )


def organizer_list(
    language: str,
    game: Game,
    participants: Sequence[Participant],
    include_description: bool = True,
) -> str:
    key = "organizer_list_header" if include_description else "organizer_list_header_brief"
    lines = [
        t(
            language,
            key,
            name=html.escape(game.name),
            description=game_description(language, game.description),
            code=html.escape(game.code),
        ),
    ]
    if not participants:
        lines.append(t(language, "no_participants"))
        return "\n".join(lines)
    for participant in participants:
        name = display_name(participant.username, participant.first_name)
        gift_status = t(
            language,
            "gift_ready" if participant.gift_ready else "gift_not_ready",
        )
        lines.append(
            t(
                language,
                "organizer_list_participant",
                user_id=participant.user_id,
                name=html.escape(name),
                gift_status=gift_status,
            )
        )
    return "\n".join(lines)


def participant_game(
    language: str,
    game: Game,
    participant: Participant,
    include_description: bool = True,
) -> str:
    gift_status = t(
        language,
        "gift_ready" if participant.gift_ready else "gift_not_ready",
    )
    key = "participant_game" if include_description else "participant_game_brief"
    return t(
        language,
        key,
        name=html.escape(game.name),
        description=game_description(language, game.description),
        status=status_text(language, game.status),
        gift_status=gift_status,
    )


def target_assignment(
    language: str,
    game_name: str,
    target: Target,
    gift_ready: bool,
) -> str:
    name = display_name(target.username, target.first_name)
    target_link = f'<a href="tg://user?id={target.user_id}">{html.escape(name)}</a>'
    wishes = (
        html.escape(target.wishes)
        if target.wishes is not None
        else t(language, "wishes_not_provided")
    )
    gift_status = t(language, "gift_ready" if gift_ready else "gift_not_ready")
    return t(
        language,
        "target_assignment",
        game_name=html.escape(game_name),
        target_link=target_link,
        wishes=wishes,
        gift_status=gift_status,
    )


def start_result(language: str, failed_deliveries: int) -> str:
    if failed_deliveries == 0:
        return t(language, "start_result_ok")
    return t(
        language,
        "start_result_failed",
        failed_deliveries=failed_deliveries,
        my_target_button=t(language, "my_target_button"),
    )
