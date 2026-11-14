from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class CreateGameState(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()


class JoinGameState(StatesGroup):
    waiting_for_code = State()
    waiting_for_wishes = State()


class EditGameDescriptionState(StatesGroup):
    waiting_for_description = State()
