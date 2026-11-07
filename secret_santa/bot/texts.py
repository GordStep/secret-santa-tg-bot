from __future__ import annotations

import html
from collections.abc import Sequence

from secret_santa.bot.db.models import Game, GameStatus, Participant, Target

START_MESSAGE = (
    "Привет! Это бот для игры «Тайный Санта».\n"
    "Создайте игру или присоединитесь к существующей по коду."
)
ABOUT_BOT = (
    "Бот разработан для проведения игры «Тайный Санта» в DRE Lab.\n"
    "Код представлен на GitHub: [ссылка — заглушка]."
)
CREATE_GAME_BUTTON = "Создать игру"
JOIN_GAME_BUTTON = "Присоединиться к игре"
MY_GAMES_BUTTON = "Мои игры"
ABOUT_BOT_BUTTON = "О боте"
MAIN_MENU_BUTTON = "Главное меню"
CANCEL_BUTTON = "Отмена"
SKIP_WISHES_BUTTON = "Пропустить пожелания"
OPEN_GAME_BUTTON = "Открыть игру"
REFRESH_BUTTON = "Обновить список"
START_DRAW_BUTTON = "Провести жеребьёвку"
ARCHIVE_BUTTON = "Архивировать игру"
CONFIRM_ARCHIVE_BUTTON = "Подтвердить архивирование"
MY_TARGET_BUTTON = "Мой получатель"
GIFT_READY_BUTTON = "Подарок готов"
BACK_TO_GAMES_BUTTON = "К списку игр"

COMMAND_START = "Открыть главное меню"
COMMAND_MY_GAMES = "Показать мои игры"
COMMAND_CANCEL = "Отменить текущее действие"

ASK_GAME_NAME = "Введите название игры (не более 100 символов):"
ASK_CODE = "Введите код игры из 8 латинских букв и цифр:"
ASK_WISHES = (
    "Напишите пожелания для подарка (не более 2000 символов) "
    "или пропустите этот шаг."
)
TEXT_REQUIRED = "Пожалуйста, отправьте текстовое сообщение."
CANCELLED = "Действие отменено."
JOIN_SESSION_EXPIRED = "Время вступления истекло. Введите код игры ещё раз."

CODE_NOT_FOUND = "Игра с таким кодом не найдена. Проверьте код и попробуйте ещё раз."
GAME_NOT_FOUND = "Игра не найдена."
JOIN_ALREADY_STARTED = "Нельзя присоединиться: жеребьёвка уже проведена."
GAME_ARCHIVED = "Игра архивирована. Это действие недоступно."
ALREADY_JOINED = "Вы уже участвуете в этой игре."
NEED_MORE_PLAYERS = "Для жеребьёвки нужны хотя бы два участника."
ALREADY_STARTED = "Жеребьёвка уже проведена, повторный запуск невозможен."
GAME_NOT_STARTED = "Жеребьёвка ещё не проведена, получатель пока не назначен."
INVALID_GAME_NAME = "Название должно содержать от 1 до 100 символов."
INVALID_WISHES = "Пожелания должны содержать не более 2000 символов."
NO_ACCESS = "У вас нет доступа к этой игре."
NOT_ORGANIZER = "Это действие доступно только организатору игры."
NOT_PARTICIPANT = "Вы не участвуете в этой игре."
INTERNAL_ERROR = "Что-то пошло не так. Попробуйте ещё раз немного позже."

NO_GAMES = "У вас пока нет игр. Создайте новую или присоединитесь по коду."
MY_GAMES_HEADER = "Выберите игру:"
NO_PARTICIPANTS = "Пока нет участников."
GIFT_READY = "Подарок готов"
GIFT_NOT_READY = "Подарок не готов"
WISHES_NOT_PROVIDED = "Пожелания не указаны."
ARCHIVE_CONFIRMATION = (
    "После архивирования нельзя будет вступить в игру, изменить статус подарка "
    "или повторно провести жеребьёвку. Продолжить?"
)
ARCHIVED_SUCCESS = "Игра архивирована."
GIFT_READY_SUCCESS = "Отлично! Подарок отмечен как готовый."
GIFT_ALREADY_READY = "Подарок уже отмечен как готовый."
TARGET_SENT = "Получатель отправлен в личное сообщение."
TARGET_DELIVERY_FAILED = (
    "Не удалось отправить личное сообщение. Начните диалог с ботом и попробуйте снова."
)


def status_text(status: GameStatus) -> str:
    if status == GameStatus.COLLECTING:
        return "сбор участников"
    if status == GameStatus.STARTED:
        return "жеребьёвка проведена"
    return "в архиве"


def display_name(username: str | None, first_name: str) -> str:
    return f"@{username}" if username else first_name


def game_list_button(game: Game, user_id: int) -> str:
    role = "организатор" if game.organizer_id == user_id else "участник"
    return f"{game.name} · {role} · {status_text(game.status)}"


def game_created(game: Game, bot_username: str) -> str:
    name = html.escape(game.name)
    code = html.escape(game.code)
    invite_link = html.escape(f"https://t.me/{bot_username}?start={game.code}")
    return (
        f"Игра <b>{name}</b> создана!\n"
        f"Код для участников: <code>{code}</code>\n"
        f"Пригласительная ссылка: {invite_link}\n\n"
        "Откройте игру, чтобы посмотреть участников или провести жеребьёвку."
    )


def joined_game(game_name: str) -> str:
    return (
        f"Вы присоединились к игре <b>{html.escape(game_name)}</b>!\n"
        "Получатель появится после жеребьёвки."
    )


def organizer_participant_joined(game_name: str, user_id: int) -> str:
    return f"К игре: {html.escape(game_name)} присоединился {user_id}"


def organizer_list(game: Game, participants: Sequence[Participant]) -> str:
    lines = [
        f"Игра: <b>{html.escape(game.name)}</b>",
        f"Код: <code>{html.escape(game.code)}</code>",
        "Участники:",
    ]
    if not participants:
        lines.append(NO_PARTICIPANTS)
        return "\n".join(lines)
    for participant in participants:
        name = display_name(participant.username, participant.first_name)
        gift_status = GIFT_READY if participant.gift_ready else GIFT_NOT_READY
        lines.append(
            f'- <a href="tg://user?id={participant.user_id}">'
            f"{html.escape(name)}</a>: {gift_status}"
        )
    return "\n".join(lines)


def participant_game(game: Game, participant: Participant) -> str:
    gift_status = GIFT_READY if participant.gift_ready else GIFT_NOT_READY
    return (
        f"Игра: <b>{html.escape(game.name)}</b>\n"
        f"Статус игры: {status_text(game.status)}\n"
        f"Ваш статус: {gift_status}"
    )


def target_assignment(game_name: str, target: Target, gift_ready: bool) -> str:
    name = display_name(target.username, target.first_name)
    target_link = f'<a href="tg://user?id={target.user_id}">{html.escape(name)}</a>'
    wishes = (
        html.escape(target.wishes)
        if target.wishes is not None
        else WISHES_NOT_PROVIDED
    )
    gift_status = GIFT_READY if gift_ready else GIFT_NOT_READY
    return (
        f"Игра: <b>{html.escape(game_name)}</b>\n"
        f"Ваш получатель: {target_link}\n"
        f"Пожелания:\n{wishes}\n"
        f"Ваш статус: {gift_status}"
    )


def start_result(failed_deliveries: int) -> str:
    if failed_deliveries == 0:
        return "Жеребьёвка проведена! Все участники получили сообщения с получателями."
    return (
        "Жеребьёвка проведена, но не удалось отправить личные сообщения "
        f"участникам: {failed_deliveries}. Они смогут открыть «Мой получатель» "
        "после запуска диалога с ботом."
    )
