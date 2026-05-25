# ============================================================================
#  CareerGuide — data-loader image.
#  A tiny BusyBox image that bakes the large ML artifacts and ESCO/LiveCareer
#  CSVs that the service images deliberately do NOT contain (their Dockerfiles
#  mount these at runtime). In Kubernetes this image is used by initContainers
#  that copy the files onto the pods' volumes, so the service Dockerfiles and
#  their .dockerignore stay untouched — the data is "mounted", not baked into
#  the application images (mirrors the per-service docker-compose model).
#
#  BUILD CONTEXT = the project root (the directory that contains backend/), e.g.
#     docker build -f k8s/data-loader/Dockerfile -t careerguide/data-loader:local .
#
#  Prerequisite: the artifacts/CSVs are present on disk (placed manually — see
#  the root .env.example and each worker/career README). They are:
#    - backend/career-service/data/esco/*.csv           (career ESCO seeding)
#    - backend/recommendation-service/worker/models/*    (CareerRNN ckpt + vocab)
#    - backend/recommendation-service/worker/data/*      (skills_en.csv, categories)
# ============================================================================
FROM busybox:1.36

# career-service ESCO seeding CSVs  → /seed/esco
COPY backend/career-service/data/esco/ /seed/esco/

# recommendation-worker CareerRNN checkpoint + industry vocab  → /seed/models
COPY backend/recommendation-service/worker/models/ /seed/models/

# recommendation-worker ESCO skills + LiveCareer categories  → /seed/data
COPY backend/recommendation-service/worker/data/ /seed/data/

# The image is only ever used as an initContainer that runs `cp`; never started
# on its own. Keep a no-op default command for clarity.
CMD ["sh", "-c", "echo 'data-loader image: use as an initContainer to copy /seed/* onto a volume'"]
