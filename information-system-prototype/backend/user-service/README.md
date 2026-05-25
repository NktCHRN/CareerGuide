# user-service — User account management

The **UserService** microservice of the CareerGuide system (C4, table 4.2):
authentication (the sole JWT issuer), user profile, and resumes. It stores
resumes in S3 and sends emails (SES, behind a feature flag), but **does NOT parse
resumes** — parsing is done by the recommendation-worker, and the result is
returned back over the Kafka bus.

- **Port:** `8001`
- **Database:** `userdb` (PostgreSQL 16)
- **Stack:** Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (async, asyncpg) ·
  Alembic · aiokafka · boto3 · redis · passlib[bcrypt] · python-jose

## Functionality (FR1–FR8)

| Group | Endpoints |
|-------|-----------|
| Authentication | `register`, `login`, `refresh`, `verify-email`, `request-password-reset`, `reset-password`, `change-password` |
| Profile | `GET/PUT /api/profile/me`, `PATCH /api/profile/me/criteria` |
| Resumes | `POST /api/profile/me/resume`, `GET /api/profile/me/resumes` |
| Reference data | `GET /api/industries`, `GET /api/recommendation-criteria` |
| Service | `GET /api/health` |

All endpoints live under the `/api` prefix. Interactive docs: `/docs`.

## Kafka events

**Publishes** (topic `user-events`):
- `user.profile.updated` — on changes to `summary` / `skills` / `experiences` or
  `recommendation_criteria` (triggers vector computation and skill mapping in the worker);
- `user.resume.uploaded` — `{user_id, s3_key}` after a PDF is uploaded (picked up by the worker);
- `user.deleted` — when an account is deleted.

**Consumes** (topic `resume-results`, group `user-resume-results`, idempotently):
- `user.profile.parsed` — merges the parsed resume into the profile → saves it and
  **publishes** `user.profile.updated`;
- `user.esco_skills.mapped` — saves the mapped ESCO skills into the `esco_skills` field;
  does **NOT** publish `user.profile.updated` (otherwise it would loop forever).

## Authentication modes (`AUTH_MODE`)
- `local` (default for isolated dev) — the service validates JWTs itself with the same `JWT_SECRET`;
- `gateway` (K8s/prod) — trusts the `X-User-Id` / `X-User-Role` headers from the API Gateway.

JWT — HS256. Access payload: `{sub, role, email, type:"access", exp}`. Only **this**
service issues tokens (access ~30 min, refresh ~30 days).

---

## Running with Docker (recommended)

Prerequisite — the shared infra (PostgreSQL/Kafka/MinIO/Redis) and the `career-net` network are up:

```bash
cd ../../infra && docker compose up -d        # one-time; see infra/README.md for details
```

Then the service itself (brings up only `user-service`; migrations+seeding run against `userdb` in the shared Postgres):

```bash
cd backend/user-service
docker compose --env-file ../../.env up -d --build
curl http://localhost:8001/api/health
```

## Local run (venv + uvicorn)

The service reaches the shared infra through the externally exposed ports (Postgres `5432`,
Kafka `29092`, MinIO `9000`, Redis `6379`) — the values in the root `.env` already point at localhost.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# DB for the local run: the shared Postgres from infra already exposes localhost:5432
# (its userdb database) — exactly the DSN in config.py defaults.

alembic upgrade head                 # schema + idempotent seed (admin, demo user)
uvicorn app.main:app --reload --port 8001
```

The config reads the root `../../.env` (and, if present, the service's local `.env`,
which overrides the root one; the template is `.env.example`).

### Seed accounts (from `.env`, `SEED_*`)
| Role | Email | Password |
|------|-------|--------|
| admin | `admin@career-guide.local` | `admin12345` |
| user  | `user@career-guide.local`  | `user12345` (with a demo profile) |

### Backfilling vectors
After the first run — publish `user.profile.updated` for all profiles so the
worker computes the vectors:

```bash
python -m app.events.backfill_users
```

---

## `curl` examples

```bash
B=http://localhost:8001

# 1) Registration (with a profile). In dev the email_verification_token is returned.
curl -s -X POST $B/api/auth/register -H 'Content-Type: application/json' -d '{
  "email":"alice@example.com","password":"supersecret1",
  "profile":{"name":"Alice","summary":"Backend developer",
    "skills":["Python","FastAPI","SQL"],
    "experiences":[{"title":"Backend Developer","industry":"INFORMATION-TECHNOLOGY",
                    "start":"5/2019","end":"current"}]}}'

# 2) Login → access/refresh
ACCESS=$(curl -s -X POST $B/api/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"supersecret1"}' | jq -r .access_token)

# 3) Profile
curl -s $B/api/profile/me -H "Authorization: Bearer $ACCESS"

# 4) Profile update (triggers the user.profile.updated event)
curl -s -X PUT $B/api/profile/me -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' \
  -d '{"summary":"Data engineer","skills":["python","sql"]}'

# 5) Recommendation criteria (triggers user.profile.updated)
curl -s -X PATCH $B/api/profile/me/criteria -H "Authorization: Bearer $ACCESS" \
  -H 'Content-Type: application/json' -d '{"recommendation_criteria":["experience","hobbies"]}'

# 6) Resume upload → S3 + user.resume.uploaded event
curl -s -X POST $B/api/profile/me/resume -H "Authorization: Bearer $ACCESS" \
  -F "file=@cv.pdf;type=application/pdf"
curl -s $B/api/profile/me/resumes -H "Authorization: Bearer $ACCESS"
```

Confirm the event was emitted:

```bash
cd ../../infra
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic user-events --from-beginning
# → you will see user.profile.updated and user.resume.uploaded
```

---

## Data model (`userdb`)
`users` · `profiles` · `profile_experiences` · `esco_skills` · `email_tokens` · `resumes`.

- `experiences[].industry` — an `industry_to_id` key in UPPERCASE (e.g.
  `INFORMATION-TECHNOLOGY`) or `null`; this is exactly what the worker model
  expects. The list of keys with labels for a dropdown is `GET /api/industries`.
- `experiences[].start` — `"M/YYYY"`; `end` — `"M/YYYY"` | `"current"` | `null`;
  `months_of_experience` is computed automatically if not provided.
- `recommendation_criteria` ⊆ `{experience, psychological, hobbies, competencies}`,
  default `{experience}`. **In the prototype only `experience` actually works**; the
  other criteria are accepted and stored as a task for the future.

## Email feature flag (SES)
`FEATURE_EMAIL_ENABLED` (default `false`). When `false`, emails are not sent
(logged instead), and in `APP_ENV=dev` the endpoints return the token in the
response (`email_verification_token`, `dev_token`). When `true`, the email goes
through AWS SES and the tokens are not returned in the response.

## Cache
The assembled profile (`GET /api/profile/me`) is cached in Redis
(`user:profile:{id}`, TTL `PROFILE_CACHE_TTL_SECONDS`) and invalidated on any
profile change. Redis is best-effort: its unavailability does not break requests.
