FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Cache HF model downloads on a mountable volume (career-SBERT + EmbeddingGemma).
    HF_HOME=/app/.hf-cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install the CPU build of torch first so the large CUDA wheels are not pulled.
# For GPU, drop this line and let requirements.txt pull the matching CUDA wheel
# (and switch the base image to an nvidia/cuda one).
RUN pip install --upgrade pip \
    && pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

# Model checkpoints / vocab and the ESCO + LiveCareer data are NOT baked into the
# image — they are mounted at runtime (./models → /app/models, ./data → /app/data),
# see docker-compose.yml.

EXPOSE 8005

# Migrations and startup are run by the command from docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
