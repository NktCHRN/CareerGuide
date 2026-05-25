# recommendation-service / api

**RecommendationServiceAPI** (C4, table 4.2) — returns profession recommendations
for the authenticated user **synchronously**. It is a thin, **read-only** layer
over the shared `recommendationdb` (pgvector): it ranks the worker's precomputed
`profession_vectors` against `user_vectors[user_id]` by **cosine similarity** and
serves filtered, paginated results.

- **Port:** `8003`
- **Database:** `recommendationdb` (PostgreSQL 16 + **pgvector**), **shared with the
  worker** — the worker owns the migrations, the api only `SELECT`s. No Alembic here.
- **Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (async, asyncpg) ·
  pgvector · redis · python-jose

## Functionality (FR10, partly FR9)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/recommendations` | Ranked, filterable, paginated list for the current user (FR10) |
| `POST /api/recommendations/scores` | Map `profession_id → score` for given ids (FR9 — boost recommended results in search) |
| `GET /api/recommendations/status` | Whether the user's vector is ready (worker may not have computed it yet) |
| `GET /api/health` | Service health |

All endpoints live under `/api` and require an authenticated caller. Interactive
docs: `/docs`.

### `GET /api/recommendations`
Query parameters:

| Param | Default | Notes |
|-------|---------|-------|
| `sort` | `score` | `score` \| `vacancies_local` \| `vacancies_international` \| `avg_salary` |
| `order` | `desc` | `desc` \| `asc` |
| `education_level` | — | exact, case-insensitive match on the denormalized column |
| `min_vacancies` | — | keeps professions with `vacancies_local >= value` (NULLs dropped) |
| `min_avg_salary` | — | keeps professions with `avg_salary >= value` |
| `page` | `1` | from 1 |
| `page_size` | `20` | max 100 |

Response is the standard page `{items, page, page_size, total}`. Each item:

```json
{ "profession_id": 42, "score": 0.87, "preferred_label": "data scientist",
  "education_level": "Master", "avg_salary": 4200.0,
  "vacancies_local": 120, "vacancies_international": 5300 }
```

`score` is the cosine similarity of the L2-normalized vectors clamped to `[0, 1]`
(1 = closest). The frontend fetches the full details/photo from **career-service**
by `profession_id`.

If the worker has not computed the user's vector yet, the list is **empty**
(`total = 0`) — the frontend should call `/status` and show a "recommendations are
still being prepared" notice.

### `POST /api/recommendations/scores`
Body `{ "profession_ids": [1, 2, 3] }` → `{ "ready": true, "scores": {"1": 0.81, "3": 0.42} }`.
Ids without a stored vector are omitted; the list is de-duplicated and capped at
`MAX_SCORE_IDS` (default 200). When the user has no vector, `ready` is `false` and
`scores` is empty. Used to lift recommended professions to the top of search results.

### `GET /api/recommendations/status`
`{ "ready": true, "updated_at": "2026-05-25T10:00:00+00:00" }` — `ready` becomes
`true` once `user_vectors[user_id]` exists.

## How ranking works (pgvector)
- Score = `1 - (profession_vectors.vector <=> user_vectors.vector)` (cosine).
- Sorting by `score` orders by the cosine **distance** ascending, so the worker's
  **HNSW** index (`vector_cosine_ops`) can be used.
- Sorting by vacancies/salary uses the plain denormalized columns (the vector
  index is not engaged then — fine for the prototype). NULLs sort last.
- `preferred_label / education_level / avg_salary / vacancies_*` are denormalized
  into `profession_vectors` by the worker, so filtering/sorting needs **no** call
  to career-service.

## Authentication modes (`AUTH_MODE`)
- `local` (default for isolated dev) — validates the JWT with the shared `JWT_SECRET`;
  `user_id` is taken from the `sub` claim.
- `gateway` (K8s/prod) — trusts the `X-User-Id` / `X-User-Role` headers from the API Gateway.

Tokens are issued **only** by user-service.

## Cache
The **first page** of a user's recommendations is cached in Redis
(`reco:list:{user_id}:{filters_hash}`, TTL `RECO_CACHE_TTL_SECONDS` ≈ 5 min) and
invalidated by TTL only — simple and sufficient for the prototype. Redis is
best-effort: its unavailability does not break requests.

---

## Running with Docker (recommended)

Prerequisite — the shared infra (PostgreSQL/Kafka/MinIO/Redis) and the `career-net`
network are up, and the **worker** has created the `recommendationdb` tables
(`alembic upgrade head`, run automatically by the worker container):

```bash
cd ../../infra && docker compose up -d                 # one-time; see infra/README.md
```

Then bring up the recommendation-service stack (worker **and** api share one compose):

```bash
cd backend/recommendation-service
docker compose --env-file ../../.env up -d --build
curl http://localhost:8003/api/health
```

The api starts after the worker (which runs the migrations); it only reads, so it
is ready as soon as the tables exist — it does **not** wait for the worker to
finish loading its ML models.

## Local run (venv + uvicorn)

The service reaches the shared infra through the externally exposed ports
(Postgres `5432`, Redis `6379`) — the root `.env` already points at localhost.
The `recommendationdb` tables must already exist (run the worker's
`alembic upgrade head` once — see `../worker/README.md`).

```bash
cd backend/recommendation-service/api
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8003
```

The config reads the root `../../../.env` (and, if present, this directory's local
`.env`, which overrides the root one; the template is `.env.example`).

---

## Verifying it works

```bash
# Tables exist and the worker has populated some profession vectors:
psql "postgresql://career:career@localhost:5432/recommendationdb" \
  -c "select count(*) from profession_vectors;"
psql "postgresql://career:career@localhost:5432/recommendationdb" \
  -c "select user_id, updated_at from user_vectors;"
```

`status` is `ready:false` until the worker stores the user's vector (triggered by a
`user.profile.updated` event from user-service), then `ready:true`.

## `curl` examples

```bash
B=http://localhost:8003

# Log in via user-service to get an access token (local AUTH_MODE):
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@career-guide.local","password":"user12345"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# 1) Readiness — before the worker has computed the user's vector
curl -s "$B/api/recommendations/status" -H "$AUTH"
# {"ready":false,"updated_at":null}

# ... after user-service publishes user.profile.updated and the worker stores the vector:
curl -s "$B/api/recommendations/status" -H "$AUTH"
# {"ready":true,"updated_at":"2026-05-25T10:00:00+00:00"}

# 2) Top recommendations by score
curl -s "$B/api/recommendations?page=1&page_size=5" -H "$AUTH"

# 3) Filtered + sorted by local vacancies
curl -s "$B/api/recommendations?sort=vacancies_local&order=desc&min_avg_salary=3000&education_level=Bachelor" \
  -H "$AUTH"

# 4) Score specific professions (to boost them in search results)
curl -s -X POST "$B/api/recommendations/scores" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"profession_ids":[1,2,3,42]}'
# {"ready":true,"scores":{"1":0.71,"2":0.55,"42":0.83}}
```

> In `gateway` AUTH_MODE drop the bearer token and let the API Gateway inject
> `X-User-Id` / `X-User-Role` (e.g. `-H "X-User-Id: 2"` for a direct test).
