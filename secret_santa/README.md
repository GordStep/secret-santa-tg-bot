# Secret Santa Telegram Bot

A multi-game Secret Santa bot built with Python 3.11+, aiogram 3, and SQLite.
The bot UI is available in Russian and English. The language is auto-detected from
the Telegram `language_code` and can be changed in the bot's Settings menu. A user
may organize multiple active games and may also join games as a participant,
including their own games.

## Features

- Game creation with unique eight-character invitation codes and Telegram invite links.
- Optional game description of up to 3000 characters, shown when joining and when opening a game from "My games"; organizers can edit it until the game is archived.
- Joining through `/start <code>` deep links with the usual gift-wishes step.
- Optional gift wishes and one participation per user per game; participants can view their wishes at any time and edit them until the game is archived.
- Atomic draw using a derangement, so nobody gifts to themselves.
- Private target delivery and repeatable target viewing without re-rolling.
- Organizer participant list with gift-readiness status.
- One-way game lifecycle: collecting, started, archived.
- Organizer-only deletion of archived games with confirmation.
- Russian/English localization with per-user language stored in SQLite.
- Language auto-detection from Telegram metadata plus a Settings menu to switch.

## Setup

Run commands from the repository root. Python 3.11 or newer is required.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r secret_santa/requirements.txt
```

Set the environment variables. The easiest way is to create a `.env` file in the
repository root (see `secret_santa/.env.example` for the variable names):

```bash
cp secret_santa/.env.example .env
```

```dotenv
BOT_TOKEN=your_token_from_BotFather
DATABASE_PATH=secret_santa.db
```

The application loads this `.env` file automatically on startup via
`python-dotenv`. Variables already present in the process environment take
precedence over values from the file, so you can also set them directly:

```bash
export BOT_TOKEN="your_token_from_BotFather"
export DATABASE_PATH="secret_santa.db"
```

`BOT_TOKEN` is required. `DATABASE_PATH` is optional and defaults to
`secret_santa.db` in the current working directory.

## Launch

```bash
python -m secret_santa.bot.main
```

Open a private chat with the bot and use `/start`. The reply keyboard supports game
creation, joining, listing games, and viewing bot information. Inline keyboards provide
game management, target viewing, and gift-readiness updates. `/my_games` lists all games
organized or joined by the current user; `/cancel` cancels the current dialog.

## Tests

No Telegram network calls are made by the tests. They use in-memory SQLite.

```bash
python -m pytest secret_santa/tests
```

## Design

- Handlers contain Telegram and FSM integration only; game rules live in
  framework-independent services.
- `aiosqlite` repository functions expose typed dataclasses rather than ORM
  objects. Service functions own transaction boundaries, while a per-connection
  `asyncio.Lock` prevents concurrent updates from interleaving transactions.
- Starting a game stores all assignments and the new status in one transaction.
  Notification failures do not undo the draw; participants can view the stored
  target later.
- All translatable UI strings live in JSON files under `bot/locales/` (one per
  language). `bot/i18n.py` loads them and `bot/texts.py` composes the localized
  HTML messages; user input is escaped before being inserted into HTML messages.
- Game codes are checked against SQLite before insertion, while the database
  unique constraint remains the final collision guard.
