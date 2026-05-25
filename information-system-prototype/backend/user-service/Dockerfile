FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies (psycopg/asyncpg/bcrypt are built from wheels, but curl
# is needed for health checks/diagnostics).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

EXPOSE 8001

# Migrations (+seeding) and startup are run by the command from docker-compose.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
