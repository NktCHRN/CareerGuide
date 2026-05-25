FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies (asyncpg is built from wheels, but curl is needed for
# health checks/diagnostics).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

# The ESCO CSVs needed by the seeding migration are NOT baked into the image;
# they are mounted at runtime (./data/esco → /app/data/esco), see docker-compose.yml.

EXPOSE 8002

# Migrations (+ESCO seeding) and startup are run by the command from docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
