# Project Guidance

- Keep all bot-facing Russian strings in `bot/texts.py`.
- Keep aiogram imports out of `bot/services/` and business rules out of handlers.
- Preserve unique `(game_id, user_id)` pairs and unique eight-character game codes.
- Never reveal assignments in organizer views or log giver/target pairs.
- Store assignments during the draw and read them again for later target views.
- Preserve the one-way lifecycle: collecting, started, archived.
- Escape user-provided values before HTML rendering.
- Run `python -m pytest secret_santa/tests` from the repository root after changes.
