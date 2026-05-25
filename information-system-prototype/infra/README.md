# infra — CareerGuide shared infrastructure

Brings up the shared PostgreSQL database, event broker, object storage and cache
used by all services, and also creates the Docker network `career-net`, which the
per-service compose files later attach to.

| Component | Image | Ports (host) | Purpose |
|-----------|-------|--------------|-------------|
| **postgres** | `pgvector/pgvector:pg16` | `5432` | Shared PostgreSQL: `userdb`, `careerdb`, `chatdb`, `recommendationdb` (pgvector) |
| **kafka** | `bitnami/kafka:3.7` (KRaft) | `29092` | Message Bus (`user-events`, `profession-events`, `resume-results`) |
| **minio** | `minio/minio` | `9000` (S3), `9001` (console) | S3-compatible storage (resumes, profession photos) |
| **minio-init** | `minio/mc` | — | creates the bucket and uploads the default photo, then exits |
| **redis** | `redis:7-alpine` | `6379` | in-memory cache (TTL) |

> One **shared** PostgreSQL instance holds a logical database per service
> (`userdb`, `careerdb`, `chatdb`, `recommendationdb`) — database-per-service at
> the schema level. Services connect to `postgres:5432`; they no longer run their
> own Postgres.

## Prerequisites
- Docker + Docker Compose v2.
- A root `.env` (optional for the infra, but needed by the services):
  ```bash
  cp ../.env.example ../.env
  ```

## Running

```bash
cd infra
docker compose up -d
```

It works out of the box with the default MinIO credentials (`minioadmin` / `minioadmin`).
To take the credentials from the root `.env` (they must match the values used by
the services):

```bash
docker compose --env-file ../.env up -d
```

Check the status and wait for `healthy`:

```bash
docker compose ps
```

Stop (data is kept in volumes) / tear down together with the data:

```bash
docker compose down
docker compose down -v        # also remove the postgres/kafka/minio/redis volumes
```

## PostgreSQL

One shared instance with a logical database per service. The init scripts in
`postgres/init/` run on first startup (when the `pgdata` volume is empty) and
create `userdb`, `careerdb`, `chatdb`, `recommendationdb`, enabling the `vector`
extension in `recommendationdb`.

```bash
# the 4 databases exist ($POSTGRES_USER defaults to `career`):
docker compose exec postgres psql -U "$POSTGRES_USER" -c "\l"
# pgvector is enabled in recommendationdb:
docker compose exec postgres psql -U "$POSTGRES_USER" -d recommendationdb -c "\dx"
```

Addressing:
- from **Docker** containers (services on `career-net`): `postgres:5432`;
- from a **local** process (uvicorn on the host): `localhost:5432`.

> The databases are created only on the **first** start. If you change the init
> scripts, re-create the volume: `docker compose down -v && docker compose up -d`.

## MinIO

- Console: <http://localhost:9001> (login/password — `S3_ACCESS_KEY` / `S3_SECRET_KEY`,
  default `minioadmin` / `minioadmin`).
- S3 API: <http://localhost:9000>.
- The `career-guide` bucket is created automatically (`minio-init`).

Object layout:
- profession photos — `professions/{profession_id}.{jpg|png|webp}`, default `professions/_default.jpg`;
- resumes — `resumes/{user_id}/{uuid}.pdf`.

### Upload a profession photo manually
Put the default photo into `infra/assets/profession-default.jpg` (it will be uploaded by
`minio-init` as `_default.jpg`), or upload a photo for a specific profession via `mc`:

```bash
mc alias set local http://localhost:9000 minioadmin minioadmin
mc cp photo.jpg local/career-guide/professions/42.jpg
mc ls local/career-guide/professions/
```

## Kafka

Verify that the broker is alive and list the topics:

```bash
docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```

Topics are created automatically on first publish (`AUTO_CREATE_TOPICS_ENABLE=true`,
`partition=1`): `user-events`, `profession-events`, `resume-results`.

Create a topic explicitly / view messages:

```bash
docker compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 \
  --create --if-not-exists --topic user-events --partitions 1 --replication-factor 1

docker compose exec kafka kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic user-events --from-beginning
```

Broker addressing:
- from **Docker** containers (services on the `career-net` network): `kafka:9092`;
- from a **local** process (uvicorn on the host): `localhost:29092`.

## Redis

```bash
docker compose exec redis redis-cli ping        # -> PONG
```

- from Docker: `redis://redis:6379/0`;
- locally: `redis://localhost:6379/0`.

## The `career-net` network

This compose creates an external network with the fixed name `career-net`. Each
per-service `docker-compose.yml` connects to it as external:

```yaml
networks:
  career-net:
    external: true
```

Check it:

```bash
docker network inspect career-net
```

## What's next

1. Bring up the infra (this directory).
2. Bring up the services you need with their own compose files — each one attaches to
   `career-net` so it can see `postgres` / `kafka` / `minio` / `redis` by their internal
   names (no service runs its own Postgres). Reference example: `backend/user-service/docker-compose.yml`:
   ```bash
   cd backend/user-service
   docker compose --env-file ../../.env up -d --build
   ```
3. To run the whole backend together — Kubernetes manifests are in `k8s/`.
