# chat-service — Embedded profession chatbot

The **ChatService** microservice of the CareerGuide system (C4, table 4.2):
a built-in assistant that talks about professions. It owns the user's chats and
messages, calls the **OpenAI** LLM to generate replies, and keeps **local
denormalised copies** of professions and user profiles — fed from the Kafka bus —
so every answer is grounded in **ESCO** data without any synchronous call to
career-service or user-service.

- **Port:** `8004`
- **Database:** `chatdb` (PostgreSQL 16)
- **Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (async, asyncpg) ·
  Alembic · aiokafka · python-jose · openai

## Functionality (FR12, FR16–FR19)

| Group | Endpoint |
|-------|----------|
| List chats (FR16) | `GET /api/chats?page=&page_size=` |
| Create chat (FR17) | `POST /api/chats` — `{ title?, profession_id? }` |
| Chat with messages (FR16) | `GET /api/chats/{id}` |
| Send a message (FR18) | `POST /api/chats/{id}/messages` — `{ content }` |
| Delete chat (FR19) | `DELETE /api/chats/{id}` |
| Service | `GET /api/health` |

All endpoints live under the `/api` prefix. Interactive docs: `/docs`.

A chat is either **free** or **bound to a profession** (`profession_id`) — the
"profession details" context (FR12). Sending a message generates an assistant
reply from the ESCO/profile context, **persists both turns** (user + assistant)
and returns them.

Pagination: `page` (from 1), `page_size` (default 20, max 100); the response is
`{items, page, page_size, total}`.

A message can be about any of the assistant's topics — profession details, ESCO
recommendations for the user's profile, a learning plan for a chosen profession,
or drafting a resume for it. The system prompt steers the model to use the
provided ESCO context and not to invent professions outside ESCO.

## Authentication (`AUTH_MODE`)
- `local` (default for isolated dev) — validates the JWT with the shared `JWT_SECRET`;
- `gateway` (K8s/prod) — trusts the `X-User-Id` / `X-User-Role` headers from the API Gateway.

Tokens are issued **only** by user-service. The caller's `user_id` comes from the
token (or the gateway header); **every endpoint is scoped to the owner** — a
foreign or missing chat returns `404`.

## Kafka — consumes (does not publish)

chat-service is a pure consumer with two independent consumer groups
(idempotent, `auto_offset_reset=earliest` so a backfill replay is picked up):

- **`profession-events`** (group `chat-prof`):
  - `profession.upserted` → upsert `cached_professions`. `knowledge_skill_labels`
    is taken **straight from the event payload** (career-service includes it), so
    chat-service never reads the ESCO CSVs.
  - `profession.deleted` → delete the local copy.
- **`user-events`** (group `chat-user`):
  - `user.profile.updated` → upsert `cached_users` (summary / skills / experiences);
  - `user.resume.uploaded` → **ignored** (it is the worker's job);
  - `user.deleted` → delete the cached profile **and** the user's chats.

## Data model (`chatdb`)
- `chats(id, user_id, title, profession_id?, created_at, updated_at)`.
- `messages(id, chat_id, role ∈ {user, assistant, system}, content, created_at)`
  — `ON DELETE CASCADE` from `chats`.
- `cached_professions(profession_id pk, esco_uri, preferred_label, description,
  knowledge_skill_labels jsonb, education_level, updated_at)` — synced from
  `profession-events`.
- `cached_users(user_id pk, name, summary, skills jsonb, experiences jsonb,
  updated_at)` — synced from `user-events`.

> The system prompt is rebuilt from the **current** local copies on every turn,
> so it always reflects the latest profession/profile data; system messages are
> not persisted in `messages`.

---

## Running with Docker (recommended)

Prerequisite — the shared infra (PostgreSQL/Kafka/MinIO/Redis) and the `career-net`
network are up:

```bash
cd ../../infra && docker compose up -d        # one-time; see infra/README.md
```

Then the service itself (brings up only `chat-service`; migrations run against
`chatdb` in the shared Postgres). `OPENAI_API_KEY` is read from the root `.env`:

```bash
cd backend/chat-service
docker compose --env-file ../../.env up -d --build
curl http://localhost:8004/api/health
```

## Local run (venv + uvicorn)

The service reaches the shared infra through the externally exposed ports
(Postgres `5432`, Kafka `29092`) — the values in the root `.env` already point at
localhost.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head                 # schema (chats / messages / cached_* )
uvicorn app.main:app --reload --port 8004
```

The config reads the root `../../.env` (and, if present, the service's local
`.env`, which overrides the root one; the template is `.env.example`).
**`OPENAI_API_KEY` is required for real replies** — without it the assistant
returns a fallback message (everything else still works).

---

## Checking that the local copies fill from Kafka

The copies are populated by the producers (career-service / user-service). The
easiest way to seed them is to run those services' **backfill** scripts so the
whole catalogue and the existing profiles are replayed onto the bus:

```bash
# professions → profession-events  (from backend/career-service, venv active)
python -m app.events.backfill_professions

# users → user-events              (from backend/user-service, venv active)
python -m app.events.backfill_users
```

chat-service consumes from the earliest offset, so it picks these up. Confirm the
copies landed in `chatdb`:

```bash
cd ../../infra
docker compose exec postgres psql -U career -d chatdb \
  -c "select count(*) from cached_professions; select count(*) from cached_users;"
```

You can also watch the consumer logs (`docker compose logs -f chat-service`, or
the uvicorn output) for `cached_professions upserted` / `cached_users upserted`.

---

## `curl` examples — create a chat about a profession, then ask a question

```bash
B=http://localhost:8004

# 0) Get an access token from user-service (port 8001)
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@career-guide.local","password":"user12345"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# 1) Create a chat bound to profession #1 (must already be in cached_professions)
CHAT=$(curl -s -X POST "$B/api/chats" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"profession_id":1}')
CHAT_ID=$(echo "$CHAT" | jq -r .id)

# 2) Ask about the profession details (FR12 / FR18)
curl -s -X POST "$B/api/chats/$CHAT_ID/messages" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"content":"What does this profession do and which ESCO skills matter most?"}' | jq

# 3) Ask for a learning plan / a tailored resume
curl -s -X POST "$B/api/chats/$CHAT_ID/messages" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Build me a learning plan to grow into this role based on my profile."}' | jq

# 4) A free chat (no profession) asking for ESCO recommendations by profile
FREE=$(curl -s -X POST "$B/api/chats" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"title":"Which professions fit me?"}')
curl -s -X POST "$B/api/chats/$(echo "$FREE" | jq -r .id)/messages" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"content":"Recommend ESCO professions that match my skills and experience."}' | jq

# 5) List chats / open one / delete one
curl -s "$B/api/chats?page=1&page_size=20" -H "$AUTH" | jq
curl -s "$B/api/chats/$CHAT_ID" -H "$AUTH" | jq
curl -s -X DELETE "$B/api/chats/$CHAT_ID" -H "$AUTH" | jq
```

> Binding a chat to a `profession_id` that is **not yet** in `cached_professions`
> returns `404` — run the career-service backfill first (see above) so the
> profession is present locally and the assistant can ground its answers in ESCO.
