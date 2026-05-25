# career-service — Detailed profession information

The **CareerService** microservice of the CareerGuide system (C4, table 4.2):
the **source of truth for professions**. It seeds the full **ESCO** occupation
catalogue, serves search / browse / details, lets an admin manage professions
(CRUD), and **publishes** `profession.upserted` / `profession.deleted` to the
`profession-events` Kafka topic so the worker and chat-service build everything
from the bus and never read the ESCO CSVs.

- **Port:** `8002`
- **Database:** `careerdb` (PostgreSQL 16, `pg_trgm` extension for search)
- **Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (async, asyncpg) ·
  Alembic · aiokafka · boto3 · redis · python-jose

## Functionality (FR9–FR15)

| Group | Endpoints |
|-------|-----------|
| Search / browse | `GET /api/professions?query=&page=&page_size=` |
| Details | `GET /api/professions/{id}` |
| Admin CRUD | `POST /api/professions`, `PUT /api/professions/{id}`, `DELETE /api/professions/{id}` |
| Admin photo | `GET /api/admin/professions/{id}/photo-upload-url` |
| Service | `GET /api/health` |

All endpoints live under the `/api` prefix. Interactive docs: `/docs`.
Search / details are public; the admin endpoints require `role == "admin"`.

Pagination: `page` (from 1), `page_size` (default 20, max 100); the response is
`{items, page, page_size, total}`.

## Kafka events

**Publishes** (topic `profession-events`):
- `profession.upserted` — on create / update; the `profession` payload carries
  the ESCO fields plus `knowledge_skill_uris` **and** `knowledge_skill_labels`
  (so consumers do not read ESCO CSVs);
- `profession.deleted` — `{profession_id}` on delete.

career-service **does not consume** any topic.

## Data model (`careerdb`)
- `professions` — ESCO fields (`esco_uri`, `esco_code`, `isco_group`,
  `preferred_label`, `description`, `alt_labels`) plus non-ESCO fields
  (`riasec_type`, `professional_values`, `work_style`, `education_level`,
  `avg_salary`, `vacancies_local`, `vacancies_international`, `responsibilities`,
  `photo_key`). **The non-ESCO fields are `NULL` after seeding** — an admin fills
  them in later.
- `skills` — the full ESCO skills reference (`skill_uri`, `label`, `description`,
  `skill_type`, `reuse_level`).
- `profession_skills` — **knowledge-type relations only** (`profession_id`,
  `skill_uri`, `relation_type` ∈ {`essential`, `optional`}).

## Authentication modes (`AUTH_MODE`)
- `local` (default for isolated dev) — validates the JWT with the shared `JWT_SECRET`;
- `gateway` (K8s/prod) — trusts the `X-User-Id` / `X-User-Role` headers from the API Gateway.

Tokens are issued **only** by user-service. The admin endpoints need an `access`
token whose `role == "admin"` (the seed admin lives in user-service).

---

## ESCO data files (required for seeding)

Place the three ESCO CSVs into `data/esco/` (they are git-ignored — added manually):

```
backend/career-service/data/esco/
├── occupations_en.csv
├── skills_en.csv
└── occupationSkillRelations_en.csv
```

The `0002_seed_esco` migration loads them: all `status == 'released'` occupations
(~3 000), the full skills dictionary, and the `skillType == 'knowledge'`
occupation↔skill relations. Seeding is idempotent (skipped if `professions` is
already populated).

---

## Running with Docker (recommended)

Prerequisite — the shared infra (PostgreSQL/Kafka/MinIO/Redis) and the `career-net` network are up:

```bash
cd ../../infra && docker compose up -d        # one-time; see infra/README.md for details
```

Then the service itself (brings up only `career-service`; migrations + ESCO
seeding run against `careerdb` in the shared Postgres). The CSVs in `data/esco`
are mounted read-only for the seeding step:

```bash
cd backend/career-service
docker compose --env-file ../../.env up -d --build
curl http://localhost:8002/api/health
```

## Local run (venv + uvicorn)

The service reaches the shared infra through the externally exposed ports
(Postgres `5432`, Kafka `29092`, MinIO `9000`, Redis `6379`) — the values in the
root `.env` already point at localhost.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head                 # schema + ESCO seeding (idempotent)
uvicorn app.main:app --reload --port 8002
```

The config reads the root `../../.env` (and, if present, the service's local
`.env`, which overrides the root one; the template is `.env.example`).

### Backfilling the bus
After the first `alembic upgrade head`, publish `profession.upserted` for every
profession so the worker and chat-service receive the whole catalogue:

```bash
python -m app.events.backfill_professions
```

Confirm the events were emitted:

```bash
cd ../../infra
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic profession-events --from-beginning --max-messages 3
```

---

## `curl` examples

```bash
B=http://localhost:8002

# 1) Search (public)
curl -s "$B/api/professions?query=developer&page=1&page_size=5"

# 2) Details (public) — includes photo_url, esco_uri and the full knowledge-skill list
curl -s "$B/api/professions/1"

# --- Admin (needs an access token with role=admin, issued by user-service) ---
ADMIN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@career-guide.local","password":"admin12345"}' | jq -r .access_token)

# 3) Update non-ESCO fields (triggers profession.upserted)
curl -s -X PUT "$B/api/professions/1" -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"avg_salary":4200,"education_level":"Bachelor","work_style":"hybrid",
       "responsibilities":["lead a team","plan delivery"]}'

# 4) Create a custom profession
curl -s -X POST "$B/api/professions" -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"preferred_label":"Prompt Engineer","description":"Designs LLM prompts",
       "alt_labels":["LLM engineer"]}'

# 5) Delete (triggers profession.deleted)
curl -s -X DELETE "$B/api/professions/1" -H "Authorization: Bearer $ADMIN"

# 6) Presigned PUT URL for a profession photo, then upload directly to MinIO
RESP=$(curl -s "$B/api/admin/professions/2/photo-upload-url?content_type=image/jpeg" \
  -H "Authorization: Bearer $ADMIN")
URL=$(echo "$RESP" | jq -r .url)
curl -s -X PUT "$URL" -H 'Content-Type: image/jpeg' --data-binary @photo.jpg
# → afterwards GET /api/professions/2 returns a presigned photo_url for it
```

### Uploading a photo straight via the MinIO client (alternative)
```bash
cd ../../infra
docker compose cp photo.jpg minio:/tmp/photo.jpg          # or use the web console at :9001
docker compose exec minio mc cp /tmp/photo.jpg local/career-guide/professions/2.jpg
```

---

## Cache
Profession details (`GET /api/professions/{id}`) are cached in Redis
(`career:profession:{id}`, TTL `PROFESSION_CACHE_TTL_SECONDS` ≈ 10 min) and
invalidated on update / delete / photo upload. Redis is best-effort — its
unavailability does not break requests. The cache TTL is shorter than the photo
presign TTL (≈ 1 h), so a cached `photo_url` stays valid for the cache lifetime.

## Photos (S3 / MinIO)
Layout: `professions/{id}.{jpg|png|webp}`; default `professions/_default.jpg`
(uploaded by the infra `minio-init`). The details endpoint always returns a
`photo_url` (presigned GET) — the profession's own photo if present, otherwise
the default.
