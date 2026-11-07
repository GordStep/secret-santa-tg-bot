### Improved Task for Kimi (English)

**Role:** You are a senior Python developer specializing in Telegram bots (aiogram 3.x) and clean architecture.

**Task:** Design and implement a Telegram bot for the "Secret Santa" game with support for multiple concurrent games.

**Important:** All user-facing bot messages, button labels, and command responses MUST be in Russian. Code, comments, variable names, and documentation may be in English.

**Stack:** Python 3.11+, aiogram 3.x, SQLite (via aiosqlite or SQLAlchemy Core), FSM for dialogs, inline keyboards for actions.

---

#### 1. Roles and Permissions

**Organizer** (game creator):
- Creates a game and sets its name.
- Receives a unique 8-character code (A-Z, 0-9).
- Sees the list of participants with their gift statuses.
- Can start the draw (only if participants ≥ 2).
- Can archive the game.
- Can view the code at any time via "My games".

**Participant**:
- Joins by code.
- Specifies gift wishes (text, optional).
- After the game starts, receives the name of their target and the target's wishes.
- Can mark "Gift is ready".
- Can re-view their own status and target name (no limit on re-viewing).

**Constraints:**
- One Telegram user (`user_id`) can join a given game only once.
- Cannot join a game that has already started or been archived.
- Cannot create a game if the user is already an organizer of an active game (optional: allow multiple — if so, state this explicitly in your answer).

---

#### 2. User Flows

**Create game:**
1. User taps "Create game".
2. Bot asks for the game name (FSM).
3. Bot generates a unique 8-character code, checks for collisions in DB.
4. Creates the game record, assigns the creator as organizer.
5. Sends a message: name, code, link to participant list.

**Join game:**
1. User taps "Join game".
2. Bot asks for the code (FSM).
3. Validates: code exists, game status is `collecting`, user is not already in the game.
4. Asks for wishes (skippable).
5. Adds the participant and confirms.

**Start game (organizer):**
1. Validate: participants ≥ 2.
2. Generate a random derangement (no fixed points — nobody gifts to themselves).
3. Save "giver → receiver" pairs in DB.
4. Set game status → `started`.
5. Send each participant a message with their target's name and wishes.

**Mark "Gift is ready":**
- Participant taps the button.
- Bot updates `gift_ready = true` for the "giver → receiver" pair.
- Organizer sees the updated status.

**Archive (organizer):**
- Status → `archived`.
- Blocked: new joins, gift-marking, re-start.

**View participant list (organizer):**
Output format (HTML parse_mode):
```
Игра: <b>{name}</b>
Код: <code>{code}</code>
Участники:
- <a href="tg://user?id={user_id}">{username}</a>: Подарок готов / не готов
```
Clickability is provided via `tg://user?id=` because username may be absent. If username is missing — display `first_name` as the link text using the ID.

---

#### 3. Data Schema (minimum)

**games**
| field | type | note |
|-------|------|------|
| id | INTEGER PK | |
| code | TEXT UNIQUE | 8 characters |
| name | TEXT | set by organizer |
| organizer_id | INTEGER | user_id |
| status | TEXT | `collecting` / `started` / `archived` |
| created_at | DATETIME | |

**participants**
| field | type | note |
|-------|------|------|
| id | INTEGER PK | |
| game_id | FK → games.id | |
| user_id | INTEGER | Telegram ID |
| username | TEXT | may be NULL |
| first_name | TEXT | for display |
| wishes | TEXT | NULL allowed |
| gift_ready | BOOLEAN | default false |
| target_user_id | INTEGER | filled after start, NULL before |

Unique index: `(game_id, user_id)`.

---

#### 4. Technical Requirements and Constraints

- **FSM:** use `aiogram.fsm` for the create-game and enter-code dialogs.
- **Error handling:** explicitly define the bot's responses to:
  - invalid code;
  - game already started / archived;
  - user already in the game;
  - organizer tries to start a game with < 2 participants;
  - user tries to mark a gift in an archived game.
- **Escaping:** when building HTML messages, use `html.quote()` for user-provided strings (game name, wishes) to avoid `can't parse entities` errors.
- **Derangement:** implement `make_derangement(participants)` — a random permutation with no fixed points. For 2 participants, a simple swap suffices.
- **State after start:** a participant must not see their own `target_user_id` directly from DB — only via the bot's message. Do not expose targets in the organizer's participant list.
- **Re-viewing target:** a command/button "My target" returns the same pair from DB, does not re-roll.


**Reminder:** all bot strings shown to users (messages, buttons, errors) must be in Russian.

