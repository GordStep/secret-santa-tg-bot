from __future__ import annotations

import random
import string
from collections.abc import Callable

from secret_santa.bot.db import repo
from secret_santa.bot.db.database import Database

CODE_LENGTH = 8
CODE_ALPHABET = string.ascii_uppercase + string.digits


def generate_code(
    is_allowed: Callable[[str], bool] | None = None,
    *,
    rng: random.Random | None = None,
) -> str:
    chooser = rng if rng is not None else random
    while True:
        code = "".join(chooser.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if is_allowed is None or is_allowed(code):
            return code


async def generate_unique_code(db: Database) -> str:
    while True:
        code = generate_code()
        if not await repo.code_exists(db, code):
            return code
