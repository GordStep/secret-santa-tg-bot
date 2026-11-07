## 1. Project Overview

Telegram bot for playing "Secret Santa" (Тайный Санта) with support for
multiple concurrent games, organizer/member roles, invitation codes,
derangement-based gift assignment, and gift-readiness tracking.

- **Language of bot UI:** Russian (all user-facing strings).
- **Language of code/comments/docs:** English.
- **Stack:** Python 3.11+, aiogram 3.x, SQLite (aiosqlite or SQLAlchemy Core),
  aiogram FSM, inline keyboards.

---

## 2. Non-Negotiable Rules

1. **All bot-facing strings are Russian.** No English leaks into messages,
   button labels, or error texts. Keep them in a single `texts.py` module.
2. **No fixed points in the derangement.** A user never gifts to themselves.
3. **`(game_id, user_id)` is unique.** A user joins a given game at most once.
4. **Target secrecy.** A participant's target is delivered only via the bot's
   private message. Never expose targets in the organizer's participant list.
5. **Re-viewing the target must not re-roll.** Read the stored pair from DB.
6. **HTML safety.** Escape all user-provided strings with `html.quote()`
   before inserting into `parse_mode="HTML"` messages.
7. **Status transitions are one-way:** `collecting → started → archived`.
   No backwards transitions, no re-start.
8. **Codes are unique.** 8 chars, `[A-Z0-9]`, retry on collision.

---

## 3. Project Structure

```
secret_santa/
├── bot/
│   ├── __init__.py
│   ├── main.py              # entrypoint, dispatcher setup
│   ├── config.py            # env vars, settings
│   ├── texts.py             # ALL Russian user-facing strings
│   ├── keyboards.py         # inline keyboards
│   ├── states.py            # FSM states
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── common.py        # /start, main menu
│   │   ├── create_game.py
│   │   ├── join_game.py
│   │   ├── organizer.py     # start, list, archive
│   │   └── participant.py   # my target, mark gift ready
│   ├── services/
│   │   ├── __init__.py
│   │   ├── games.py         # create/join/start/archive logic
│   │   ├── codes.py         # code generation + collision check
│   │   └── derangement.py   # make_derangement()
│   └── db/
│       ├── __init__.py
│       ├── models.py        # schema (SQLAlchemy Core or raw SQL)
│       └── repo.py          # data access functions
├── migrations/              # optional, for schema evolution
├── tests/
│   ├── test_derangement.py
│   ├── test_codes.py
│   └── test_games.py
├── .env.example
├── requirements.txt
├── README.md
└── AGENT.md
```

Rules:
- Handlers contain **no business logic** — they only parse input, call
  services, and format replies.
- Services contain **no aiogram imports** — pure Python, testable.
- DB layer exposes **functions**, not ORM objects, to handlers.
- All Russian strings live in `texts.py`. No inline literals in handlers.

---

## 4. Data Model

### games
| field | type | notes |
|---|---|---|
| id | INTEGER PK | |
| code | TEXT UNIQUE NOT NULL | 8 chars, A-Z0-9 |
| name | TEXT NOT NULL | set by organizer |
| organizer_id | INTEGER NOT NULL | Telegram user_id |
| status | TEXT NOT NULL | `collecting` / `started` / `archived` |
| created_at | DATETIME NOT NULL | |

### participants
| field | type | notes |
|---|---|---|
| id | INTEGER PK | |
| game_id | INTEGER FK → games.id | |
| user_id | INTEGER NOT NULL | Telegram user_id |
| username | TEXT NULL | may be absent |
| first_name | TEXT NOT NULL | display fallback |
| wishes | TEXT NULL | optional |
| gift_ready | BOOLEAN NOT NULL DEFAULT 0 | |
| target_user_id | INTEGER NULL | set on start |

Constraints:
- `UNIQUE(game_id, user_id)`
- `UNIQUE(code)` on games
- `target_user_id` is NULL until status = `started`

---

## 5. Core Algorithms

### make_derangement(user_ids: list[int]) -> dict[int, int]
- Returns a mapping `giver_id → receiver_id`.
- No element maps to itself.
- Uses `random.shuffle` + retry loop (or Sattolo's algorithm).
- Raises `ValueError` if `len(user_ids) < 2`.
- Covered by unit tests: no fixed points, bijection, works for n=2.

### generate_code() -> str
- Returns 8 random chars from `[A-Z0-9]`.
- Retries until unique in `games.code`.
- Covered by unit test: length, charset, uniqueness retry path.

---

## 6. Error Handling Contract

Every user-visible error must be a Russian message from `texts.py`.
No raw exceptions, no tracebacks, no silent failures.

Required cases:
| Case | Behavior |
|---|---|
| Invalid code | Russian message: code not found |
| Game already started | Russian message: cannot join |
| Game archived | Russian message: cannot join / mark |
| User already in game | Russian message: already joined |
| Organizer with < 2 participants | Russian message: need more players |
| Mark gift in archived game | Russian message: game archived |
| Start already started game | Russian message: already started |
| User has no target yet | Russian message: game not started |

---

## 7. Output Format — Organizer List

```
Игра: <b>{name}</b>
Код: <code>{code}</code>
Участники:
- <a href="tg://user?id={user_id}">{display_name}</a>: Подарок готов
- <a href="tg://user?id={user_id}">{display_name}</a>: Подарок не готов
```

- `display_name` = `@{username}` if present, else `first_name`.
- `name` escaped with `html.quote()`.
- `code` in `<code>` tags.
- Links use `tg://user?id=`, not `@username`, for clickability without username.

---

## 8. What the Agent MUST Deliver

When asked to implement a feature or the whole project, return:

1. **File tree** — what was added/changed.
2. **Full file contents** — no placeholders like `# TODO`.
3. **Tests** for `make_derangement`, `generate_code`, and at least one
   service-level game flow.
4. **Run instructions** — env vars, install, launch.
5. **Short summary** of design decisions (3–5 bullets).

Do NOT:
- Invent dependencies not in `requirements.txt` without stating them.
- Put Russian strings outside `texts.py`.
- Put aiogram imports inside `services/`.
- Skip error cases from §6.

---

## 9. Coding Style

- Type hints everywhere (`from __future__ import annotations`).
- `async`/`await` for all DB and handler code.
- No global mutable state; pass `db` and `config` explicitly.
- Functions ≤ 40 lines where reasonable; extract helpers.
- Use `logging`, not `print`.
- No bare `except:`; catch specific exceptions.
- Follow PEP 8; line length ≤ 100.

---

## 10. Testing

- Framework: `pytest` + `pytest-asyncio`.
- `make_derangement`: fixed-point-free, bijection, n=2, n=3, n=10, n=100.
- `generate_code`: charset, length, collision retry (mock RNG).
- Service flow: create → join → start → mark → archive (in-memory SQLite).
- No network calls in tests; mock Telegram where needed.

---

## 11. Security & Privacy

- Never log `user_id` together with `target_user_id`.
- Never send targets to anyone except the giver.
- Never expose codes of archived games via public commands.
- Escape all user input before HTML rendering.
- Do not store message text of user conversations beyond `wishes`.

---

## 12. Definition of Done

A feature is done when:
- [ ] Code compiles, `pytest` passes.
- [ ] All user-facing strings are in `texts.py` and in Russian.
- [ ] All error cases from §6 handled.
- [ ] No aiogram imports in `services/`.
- [ ] No fixed points in derangement (covered by tests).
- [ ] `README.md` updated if run steps changed.
```
