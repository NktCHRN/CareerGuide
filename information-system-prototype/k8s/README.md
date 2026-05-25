# CareerGuide on Kubernetes (`k8s/`)

Deploys the **entire backend + frontend + infrastructure** of CareerGuide into one
Kubernetes cluster, using **Kustomize** (`base/` + `overlays/local/`).

This is different from the per-service `docker-compose.yml` files: those bring up a
single service against the shared `infra/` stack for **isolated development**. This
folder brings up **everything together** (microservices, frontend, databases, Kafka,
MinIO, Redis, migrations/seeding, and the Kafka backfill) the way it runs in a real
cluster.

```
k8s/
├── base/
│   ├── namespace.yaml                 # ns: career-guide
│   ├── config/                        # app-config (ConfigMap) + app-secrets (Secret)
│   ├── infra/                         # kafka (KRaft), redis, minio (+ minio-init Job)
│   ├── databases/                     # one Postgres StatefulSet per service (DB-per-service)
│   ├── services/                      # Deployment + Service per microservice + frontend
│   ├── jobs/                          # migrations + seeding + Kafka backfill
│   ├── ingress.yaml                   # /api → api-gateway, / → frontend
│   └── kustomization.yaml
├── overlays/local/                    # images + namespace for a local cluster
│   └── kustomization.yaml
└── data-loader/Dockerfile             # tiny image that ships the ML artifacts + ESCO CSVs
```

## Architecture mapping (C4 → k8s)

| C4 component               | k8s object                                  | Port | Exposed       |
|----------------------------|---------------------------------------------|------|---------------|
| API Gateway                | `Deployment/Service api-gateway`            | 8000 | Ingress `/api`|
| User service               | `Deployment/Service user-service`           | 8001 | ClusterIP     |
| Career service             | `Deployment/Service career-service`         | 8002 | ClusterIP     |
| Recommendation API         | `Deployment/Service recommendation-api`     | 8003 | ClusterIP     |
| Chat service               | `Deployment/Service chat-service`           | 8004 | ClusterIP     |
| Recommendation worker      | `Deployment/Service recommendation-worker`  | 8005 | ClusterIP (health) |
| Frontend (Next.js SSR)     | `Deployment/Service frontend`               | 3000 | Ingress `/`   |
| PostgreSQL ×4 (DB-per-svc) | `StatefulSet userdb/careerdb/chatdb/recommendationdb` | 5432 | ClusterIP (headless) |
| Kafka (Message Bus, KRaft) | `StatefulSet/Service kafka`                 | 9092 | ClusterIP (headless) |
| MinIO (S3)                 | `Deployment/Service minio` (+ `Job minio-init`) | 9000/9001 | ClusterIP |
| Redis (cache)              | `Deployment/Service redis`                  | 6379 | ClusterIP     |

`AUTH_MODE=gateway`: the gateway validates JWTs and forwards `X-User-Id` / `X-User-Role`;
the worker never calls the services over HTTP — everything flows through Kafka.

---

## Prerequisites

1. A local cluster — **kind**, **minikube**, or Docker Desktop Kubernetes.
2. `kubectl` (v1.27+; it has `kubectl kustomize` built in) — or standalone `kustomize`.
3. An **ingress-nginx** controller (see below).
4. The large artifacts/data placed on disk (they are git-ignored and mounted, not baked
   into the service images — see the root `.env.example` and the service READMEs):
   - `backend/career-service/data/esco/{occupations_en.csv,skills_en.csv,occupationSkillRelations_en.csv}`
   - `backend/recommendation-service/worker/models/{gru-attn-bidirectional-final_seed4.pth,industry_to_id.json}`
   - `backend/recommendation-service/worker/data/{skills_en.csv,livecareer_resume_categories.csv}`
5. Secrets you must set in `base/config/secret.yaml` before/after first apply:
   - `HF_TOKEN` — **required**: the worker pulls the gated `google/embeddinggemma-300m`.
   - `OPENAI_API_KEY` — needed for resume parsing (worker) and the chat assistant.
   - The rest have working dev defaults (DB password, JWT, MinIO creds, seeded accounts).

> All commands below assume the working directory is the project root
> (`information-system-prototype/`, the folder that contains `backend/`, `frontend/`, `k8s/`).

---

## 1. Build the images

Eight images: seven applications + one `data-loader` (ships the ML artifacts/CSVs that
initContainers copy onto pod volumes).

```bash
docker build -t careerguide/api-gateway:local            backend/api-gateway
docker build -t careerguide/user-service:local           backend/user-service
docker build -t careerguide/career-service:local         backend/career-service
docker build -t careerguide/chat-service:local           backend/chat-service
docker build -t careerguide/recommendation-api:local     backend/recommendation-service/api
docker build -t careerguide/recommendation-worker:local  backend/recommendation-service/worker
docker build -t careerguide/frontend:local               frontend

# data-loader: build context is the project root (it COPYies the artifacts from backend/*)
docker build -f k8s/data-loader/Dockerfile -t careerguide/data-loader:local .
```

The worker image installs the **CPU** torch wheel. For GPU, rebuild it on an
`nvidia/cuda` base with a matching CUDA torch wheel (see its Dockerfile), set
`DEVICE=cuda` in `base/config/configmap.yaml`, and uncomment the GPU limit in
`base/services/recommendation-worker.yaml`.

## 2. Load the images into the cluster

**kind:**
```bash
for img in api-gateway user-service career-service chat-service \
           recommendation-api recommendation-worker frontend data-loader; do
  kind load docker-image careerguide/$img:local --name <your-kind-cluster>
done
```

**minikube:**
```bash
for img in api-gateway user-service career-service chat-service \
           recommendation-api recommendation-worker frontend data-loader; do
  minikube image load careerguide/$img:local
done
```

(All manifests use `imagePullPolicy: IfNotPresent`, so no registry is needed.)

## 3. Install ingress-nginx

**kind** (the cluster must publish host ports 80/443 — create it with
`extraPortMappings` for 80→80 and 443→443, then):
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --namespace ingress-nginx --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller --timeout=180s
```

**minikube:**
```bash
minikube addons enable ingress
```

## 4. Set the required secrets

Edit `base/config/secret.yaml` and fill in `HF_TOKEN` and `OPENAI_API_KEY` (and rotate the
dev defaults for anything beyond local use). Alternatively patch them after applying:
```bash
kubectl -n career-guide create secret generic app-secrets \
  --from-literal=HF_TOKEN=hf_xxx --from-literal=OPENAI_API_KEY=sk-xxx \
  --dry-run=client -o yaml | kubectl apply -f -   # (merge by re-supplying all keys, or use `kubectl edit secret`)
```

## 5. Deploy

```bash
kubectl apply -k k8s/overlays/local
```

That applies all 43 objects at once. **You do not need to order things manually** — every
Deployment/Job has initContainers that block on their dependencies:

- services & migration Jobs wait for their Postgres (`pg_isready`) and for Kafka (`nc`);
- `career-backfill` additionally waits until `career-migrate` has seeded the `professions`
  table (polls the row count), so it never publishes an empty catalogue;
- the worker & `career-migrate` first run a `data-loader` initContainer that copies the
  artifacts/CSVs onto their volumes.

The logical order it converges through:

```
infra (kafka, minio, redis)  +  databases (4× postgres)
        │
        ├─ minio-init            → create the S3 bucket
        ├─ user-migrate          → userdb tables + seed admin/test user
        ├─ career-migrate        → careerdb tables + seed ~3043 ESCO professions
        ├─ recommendation-migrate→ recommendationdb pgvector tables
        └─ chat-migrate          → chatdb tables
        │
        ├─ services come ready (api-gateway, user/career/chat, reco-api, worker, frontend)
        │
        ├─ career-backfill       → publish all professions → worker builds vectors, chat copies
        └─ user-backfill (opt.)  → publish user profiles → worker builds user vectors
```

> If you prefer an explicit phased rollout, apply in waves and `kubectl wait` between them
> (e.g. `kubectl -n career-guide apply -k ...` then
> `kubectl -n career-guide wait --for=condition=complete job/career-migrate --timeout=600s`).

## 6. Access the app

Map the ingress host to the controller (kind with 80/443 published, or `minikube ip`):
```bash
echo "127.0.0.1 career-guide.local" | sudo tee -a /etc/hosts      # kind
# minikube: use "$(minikube ip) career-guide.local" instead
```
Then open **http://career-guide.local** (frontend) — API calls go to
`http://career-guide.local/api/...` (gateway).

No ingress? Port-forward instead:
```bash
kubectl -n career-guide port-forward svc/frontend 3000:3000
kubectl -n career-guide port-forward svc/api-gateway 8000:8000
```

Seeded accounts (from `app-secrets`): `admin@career-guide.local / admin12345`,
`user@career-guide.local / user12345`.

---

## Verifying it works

```bash
# Everything up?
kubectl -n career-guide get pods

# Jobs finished?
kubectl -n career-guide get jobs

# Worker logs (model loading, event consumption):
kubectl -n career-guide logs deploy/recommendation-worker -f

# Are profession vectors being computed (after career-backfill)?
kubectl -n career-guide exec -it statefulset/recommendationdb -- \
  psql -U career -d recommendationdb -c "select count(*) from profession_vectors;"

# Professions seeded?
kubectl -n career-guide exec -it statefulset/careerdb -- \
  psql -U career -d careerdb -c "select count(*) from professions;"
```

The worker reports `ready=false` on `GET /api/health` while it downloads/loads the two
embedding models (career-SBERT + EmbeddingGemma) — first start is slow; the download is
cached on the `worker-hf-cache` PVC for subsequent restarts.

## Re-running Jobs

Jobs are immutable. To re-run one (e.g. after rebuilding an image), delete and re-apply:
```bash
kubectl -n career-guide delete job career-backfill
kubectl apply -k k8s/overlays/local
```

## Default profession photo (optional)

`minio-init` only creates the bucket unless you provide a default photo. To add one:
```bash
kubectl -n career-guide create configmap minio-default-photo \
  --from-file=profession-default.jpg=/path/to/photo.jpg
kubectl -n career-guide delete job minio-init && kubectl apply -k k8s/overlays/local
```

---

## Notes & alternatives

- **Single Postgres instead of four.** For lower resource use you can run one Postgres
  StatefulSet hosting all four databases (as `infra/docker-compose.yml` does). The default
  here uses four separate StatefulSets to match the database-per-service architecture; to
  consolidate, replace `databases/` with one StatefulSet (+ an init script creating the 4
  DBs) and point all four `*_DATABASE_URL` secret keys at it.
- **Kafka in production.** This is a single-node KRaft broker for the prototype. For a real
  deployment prefer the **Strimzi operator** or the **bitnami Kafka Helm chart**.
- **Helm.** The whole `base/` could be repackaged as a Helm chart (values for image tags,
  replicas, secrets); Kustomize is used here to avoid the extra dependency.
- **Data distribution.** Service Dockerfiles deliberately keep the large artifacts out of
  the images. The `data-loader` image carries them and initContainers copy them onto
  emptyDir volumes (worker) / the seeding Job (career) — mirroring the compose bind-mounts.
  For a fully self-contained image you may instead bake the data into the worker/career
  images and drop the `data-loader` initContainers.
- **Secrets.** `app-secrets` ships with **dev defaults** so `apply -k` works out of the box.
  Rotate every value before any non-local use, and prefer a sealed-secrets / external-secrets
  operator over a plaintext manifest.
