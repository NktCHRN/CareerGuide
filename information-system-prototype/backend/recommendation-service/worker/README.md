# recommendation-service / worker

**RecommendationServiceWorker** (C4, table 4.2) — an asynchronous Kafka consumer
with no public REST API beyond `GET /api/health` (port **8005**). It computes the
semantic vectors that recommendation-api ranks against, maps free-text user
skills to ESCO, and parses uploaded resumes via an LLM.

It owns the **`recommendationdb`** schema (pgvector); recommendation-api only
reads it.

## Responsibilities

1. **Profession vectors** — consumes `profession.upserted` / `profession.deleted`
   (`profession-events`). The profession's semantic vector is the **career-SBERT**
   embedding of its ESCO text
   (`esco role: … \n alt labels: … \n description: …`), L2-normalized, stored in
   `profession_vectors` with denormalized filter fields.
2. **User vectors** — consumes `user.profile.updated` (`user-events`). Builds the
   CareerRNN input from the user's experience (skill feature = the **raw** user
   skills), runs the **GRU-attention model**, L2-normalizes the 768-d output into
   `user_vectors`.
3. **ESCO skill mapping** — in the same `user.profile.updated` handler, maps the
   user's free-text `skills` to ESCO `skill_uri`s via the adaptive-hybrid v3
   pipeline (**EmbeddingGemma**) and publishes
   `user.esco_skills.mapped {user_id, esco_skills}` to `resume-results`
   (user-service stores it; it does **not** feed the model vector).
4. **Resume parsing** — consumes `user.resume.uploaded`. Downloads the PDF from
   S3, extracts text (`pypdf`), parses it into a structured profile with OpenAI,
   and publishes `user.profile.parsed` to `resume-results` (user-service merges
   it and re-publishes `user.profile.updated`, which triggers #2 and #3).

> Two embedding models, two purposes: **career-SBERT** (`SBERT_MODEL`, 768-d) for
> the vectors fed to CareerRNN; **EmbeddingGemma** (`ESCO_SKILL_EMBED_MODEL`) only
> for skill→ESCO mapping. The worker does **not** read ESCO CSVs for professions
> (it builds them from events) — the only ESCO CSV it reads is the full
> `skills_en.csv` catalogue, for skill mapping.

## Required artifacts (placed manually, mounted at runtime)

| Path | Env var | Notes |
|------|---------|-------|
| `models/gru-attn-bidirectional-final_seed4.pth` | `MODEL_CKPT_PATH` | CareerRNN checkpoint |
| `models/industry_to_id.json` | `INDUSTRY_VOCAB_PATH` | industry → id vocab; **must contain `<unk>`** and must not be regenerated (fixed `industry_emb` size) |
| `data/livecareer_resume_categories.csv` | `LIVECAREER_CATEGORIES_PATH` | UPPERCASE industry keys + human-readable hints for the LLM prompt |
| `data/skills_en.csv` | `ESCO_SKILLS_CSV` | full ESCO skill catalogue (≈104k rows) for skill mapping |

These files are present in the repo for the prototype.

## Environment variables

See [`.env.example`](.env.example). The worker also reads the monorepo root
`.env`. Key ones:

- `DATABASE_URL` — `recommendationdb` (e.g. `postgresql+asyncpg://career:career@localhost:5432/recommendationdb`)
- `KAFKA_BOOTSTRAP_SERVERS` — `localhost:29092` locally, `kafka:9092` in Docker
- `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- `OPENAI_API_KEY`, `OPENAI_MODEL` — resume parsing
- `SBERT_MODEL`, `MODEL_CKPT_PATH`, `INDUSTRY_VOCAB_PATH`, `LIVECAREER_CATEGORIES_PATH`
- `ESCO_SKILLS_CSV`, `ESCO_SKILL_EMBED_MODEL`, **`HF_TOKEN`** (EmbeddingGemma is gated)
- `DEVICE` — `auto` | `cpu` | `cuda`

## Run locally (venv)

```bash
cd backend/recommendation-service/worker
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then fill OPENAI_API_KEY and HF_TOKEN

# Shared infra (Postgres + Kafka + MinIO) must be up — see infra/README.md.
alembic upgrade head               # creates the pgvector tables + HNSW indexes
uvicorn app.main:app --reload --port 8005
```

On the first start the worker loads career-SBERT and the CareerRNN checkpoint and
**builds the EmbeddingGemma ESCO skill index over the full catalogue** — the slow
step (minutes on CPU). `GET /api/health` returns `{"status":"ok","ready":false}`
until that finishes; the consumers start only once `ready` is `true`.

## Run with Docker

```bash
# from backend/recommendation-service
docker compose --env-file ../../.env up -d --build
```

`models/` and `data/` are mounted into the container; HF downloads are cached in
the `hf-cache` volume. The container runs `alembic upgrade head` then the worker.
The image installs the **CPU** torch wheel (see the Dockerfile / compose header
for the GPU route).

## Health check

```bash
curl http://localhost:8005/api/health
# {"status":"ok","ready":true}
```

## Verifying it works

- **Professions** — after career-service publishes `profession.upserted` (or its
  backfill `python -m app.events.backfill_professions`), rows appear in
  `recommendationdb.profession_vectors`:
  ```bash
  psql "postgresql://career:career@localhost:5432/recommendationdb" \
    -c "select count(*), max(updated_at) from profession_vectors;"
  ```
- **Users** — when user-service publishes `user.profile.updated`, a row appears in
  `user_vectors`, and a `user.esco_skills.mapped` event is published to
  `resume-results`:
  ```bash
  # observe published skill-mapping events
  docker exec career-kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 --topic resume-results --from-beginning
  ```
- **Resume** — when user-service uploads a PDF and publishes
  `user.resume.uploaded`, the worker publishes `user.profile.parsed` to
  `resume-results`.

## Troubleshooting

- **`load_state_dict` size mismatch (`industry_emb`)** — `industry_to_id.json`
  was changed/regenerated, so `n_industries` no longer matches the checkpoint.
  Restore the original vocab (keep `<unk>`).
- **Profession vectors look wrong / inconsistent** — the profession text format
  must match training exactly: `esco role: … \n alt labels: … \n description: …`.
- **`resume-results` events never reach user-service** — check user-service is
  consuming the topic (group `user-resume-results`) and that the broker host
  matches (`localhost:29092` vs `kafka:9092`).
- **EmbeddingGemma download fails (401/403)** — it is gated; accept the license at
  https://huggingface.co/google/embeddinggemma-300m and set `HF_TOKEN`.
- **`skills_en.csv` missing** — required for skill mapping; place it in `data/`.
- **Startup blocks ~tens of seconds with infra down** — the producer/consumers
  retry Kafka a few times then degrade; bring up `infra/` first.
- **OpenAI errors / empty parse** — set `OPENAI_API_KEY`; the parser retries once
  on invalid JSON, then logs and skips.
