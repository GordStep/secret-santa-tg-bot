from __future__ import annotations


class GameError(Exception):
    """Base class for expected game-flow errors."""


class InvalidGameNameError(GameError):
    pass


class InvalidWishesError(GameError):
    pass


class InvalidCodeError(GameError):
    pass


class GameNotFoundError(GameError):
    pass


class GameNotCollectingError(GameError):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


class AlreadyJoinedError(GameError):
    pass


class NotEnoughParticipantsError(GameError):
    pass


class GameAlreadyStartedError(GameError):
    pass


class GameArchivedError(GameError):
    pass


class GameNotStartedError(GameError):
    pass


class GameAccessDeniedError(GameError):
    pass


class NotOrganizerError(GameError):
    pass


class NotParticipantError(GameError):
    pass
