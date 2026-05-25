# api-gateway — Single entry point

The **ApiGateway** of the CareerGuide system (C4, table 4.2): the single entry
point for all client traffic. It **validates** the JWT, **authorises** the route
and **reverse-proxies** the request to the right service, forwarding the caller's
identity as `X-User-Id` / `X-User-Role`. It is **stateless** — no database, no
Kafka, no migrations.

- **Port:** `8000` — the only backend port published to the host. Clients and the
  frontend talk to the gateway, never to the services directly.
- **Stack:** Python 3.12 · FastAPI · Pydantic v2 · `httpx` (async reverse-proxy) ·
  python-jose (JWT validation).

## Routing

The public API namespaces each service under `/api/<service-key>/…`. Every
downstream service exposes its endpoints under its **own** `/api/…` prefix, so
the gateway strips the service key and forwards the rest under `/api/`:

| Public path (via gateway)        | Forwarded to                              |
|----------------------------------|-------------------------------------------|
| `/api/users/*`  → `/api/*`       | user-service (`USER_SERVICE_URL`)         |
| `/api/career/*` → `/api/*`       | career-service (`CAREER_SERVICE_URL`)     |
| `/api/reco/*`   → `/api/*`       | recommendation-api (`RECO_API_URL`)       |
| `/api/chat/*`   → `/api/*`       | chat-service (`CHAT_SERVICE_URL`)         |

Examples: `POST /api/users/auth/login` → user-service `POST /api/auth/login`;
`GET /api/career/professions` → career-service `GET /api/professions`;
`GET /api/reco/recommendations` → recommendation-api `GET /api/recommendations`;
`POST /api/chat/chats` → chat-service `POST /api/chats`.

The gateway's own endpoints (not proxied): `GET /api/health` and
`GET /api/health/all` (pings every downstream `/api/health`). Interactive docs at
`/docs`.

It is a transparent async proxy: it streams the request/response body, forwards
the method, path, query and headers (minus hop-by-hop ones), and maps transport
failures to `502` (unreachable / connection error) or `504` (timeout). Idempotent
`GET`/`HEAD` requests are retried once on connection errors (`PROXY_RETRIES`).

## Authentication & authorisation

- **JWT** (HS256, shared `JWT_SECRET`) is validated on every protected route.
  Tokens are issued **only** by user-service. Access payload:
  `{ sub, role, email, exp, type:"access" }`.
- The gateway forwards the validated identity downstream as `X-User-Id` /
  `X-User-Role`. **Client-supplied `X-User-*` headers are stripped** before
  proxying (anti-spoofing) — the gateway sets them itself.
- **Downstream services must run with `AUTH_MODE=gateway`** so they trust those
  headers instead of re-validating the token (see below).

### Public routes (no token required)
- `POST /api/users/auth/register`, `POST /api/users/auth/login`,
  `POST /api/users/auth/refresh`
- `GET /api/users/auth/verify-email`,
  `POST /api/users/auth/request-password-reset`,
  `POST /api/users/auth/reset-password`
- `GET /api/users/industries`, `GET /api/users/recommendation-criteria`
  (reference data for the registration / profile forms)
- `GET /api/career/professions`, `GET /api/career/professions/{id}`
  (anonymous browsing of the catalogue)
- `GET /api/health`

### Admin-only routes (`role=admin`)
Enforced at the gateway (in addition to the check inside career-service):
- any `POST` / `PUT` / `PATCH` / `DELETE` on `/api/career/professions…`
- anything under `/api/career/admin/…` (e.g. the photo-upload URL)

A missing/invalid token on a protected route → `401`; a valid non-admin token on
an admin route → `403`. Errors use the shared `{ "detail": "…" }` shape.

### Optional: verify via user-service
With `GATEWAY_VERIFY_VIA_USER_SERVICE=true`, after the local JWT check the gateway
additionally calls `GET {USER_SERVICE_URL}/api/profile/me` to confirm the user
still exists / is active (catches revoked or deleted accounts whose token has not
yet expired). Default **false** — local validation is enough for the prototype.

---

## Running with Docker (recommended)

Prerequisites: the shared infra (`career-net` network) and **all four downstream
services** are up — each via its own compose file (and each with
`AUTH_MODE=gateway`, see below):

```bash
cd ../../infra && docker compose up -d                       # one-time; see infra/README.md
cd ../backend/user-service          && docker compose --env-file ../../.env up -d --build
cd ../career-service                && docker compose --env-file ../../.env up -d --build
cd ../recommendation-service        && docker compose --env-file ../../.env up -d --build
cd ../chat-service                  && docker compose --env-file ../../.env up -d --build
```

Then the gateway (reaches the services by their container names on `career-net`).
`JWT_SECRET` is read from the root `.env` and **must match** user-service's:

```bash
cd backend/api-gateway
docker compose --env-file ../../.env up -d --build
curl http://localhost:8000/api/health
curl http://localhost:8000/api/health/all      # aggregated downstream probe
```

## Local run (venv + uvicorn)

The gateway reaches the services on their externally exposed localhost ports
(8001–8004) — the defaults in the root `.env` already point at localhost.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The config reads the root `../../.env` (and, if present, the service's local
`.env`, which overrides the root one; the template is `.env.example`).

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `JWT_SECRET` | `change-me-…` | HS256 secret; **must match user-service** |
| `CORS_ORIGINS` | `http://localhost:3000` | allowed frontend origin(s) |
| `USER_SERVICE_URL` | `http://localhost:8001` | downstream user-service |
| `CAREER_SERVICE_URL` | `http://localhost:8002` | downstream career-service |
| `RECO_API_URL` | `http://localhost:8003` | downstream recommendation-api |
| `CHAT_SERVICE_URL` | `http://localhost:8004` | downstream chat-service |
| `PROXY_CONNECT_TIMEOUT_SECONDS` | `5.0` | connect timeout (fail fast → 502) |
| `PROXY_TIMEOUT_SECONDS` | `60.0` | read/write timeout (LLM calls are slow) |
| `PROXY_RETRIES` | `1` | retries for idempotent GET/HEAD on connect errors |
| `GATEWAY_VERIFY_VIA_USER_SERVICE` | `false` | optional extra user check |

## Switching the services to `AUTH_MODE=gateway`

Behind the gateway, each service must **trust** the `X-User-*` headers instead of
validating the JWT itself. Set `AUTH_MODE=gateway` for each downstream service —
either in the root `.env` (shared) or by uncommenting the `AUTH_MODE: gateway`
line in each service's `docker-compose.yml`. (For isolated single-service dev,
keep `AUTH_MODE=local` and hit the service's own port directly, bypassing the
gateway.)

---

## `curl` examples — through the gateway

```bash
G=http://localhost:8000

# 1) Public: log in (no token needed) — note the /api/users/ prefix
TOKEN=$(curl -s -X POST "$G/api/users/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@career-guide.local","password":"user12345"}' | jq -r .access_token)
AUTH="Authorization: Bearer $TOKEN"

# 2) Public: browse the catalogue (works without a token)
curl -s "$G/api/career/professions?page=1&page_size=5" | jq

# 3) Protected: my profile (401 without a valid token)
curl -s "$G/api/users/profile/me" -H "$AUTH" | jq

# 4) Protected: my recommendations
curl -s "$G/api/reco/recommendations?page=1&page_size=10" -H "$AUTH" | jq

# 5) Chat: create a chat and send a message
CHAT_ID=$(curl -s -X POST "$G/api/chat/chats" -H "$AUTH" \
  -H 'Content-Type: application/json' -d '{"profession_id":1}' | jq -r .id)
curl -s -X POST "$G/api/chat/chats/$CHAT_ID/messages" -H "$AUTH" \
  -H 'Content-Type: application/json' \
  -d '{"content":"What does this profession do?"}' | jq

# 6) Admin only: a regular user gets 403, an admin succeeds
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "$G/api/career/professions/1" -H "$AUTH"   # 403

ADMIN=$(curl -s -X POST "$G/api/users/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@career-guide.local","password":"admin12345"}' | jq -r .access_token)
curl -s -X POST "$G/api/career/professions" -H "Authorization: Bearer $ADMIN" \
  -H 'Content-Type: application/json' \
  -d '{"esco_uri":"http://example/esco/1","preferred_label":"example role"}' | jq
```
