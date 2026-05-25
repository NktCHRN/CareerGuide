-- ============================================================================
--  CareerGuide — create the logical databases in the shared PostgreSQL instance.
--  Runs ONLY on first initialization of the pgdata volume (docker-entrypoint-initdb.d).
--
--  This script is executed by the entrypoint as the superuser from POSTGRES_USER,
--  so each CREATE DATABASE without an explicit OWNER is owned by that user.
--  recommendationdb gets the pgvector extension (the image is pgvector/pgvector:pg16).
-- ============================================================================

CREATE DATABASE userdb;
CREATE DATABASE careerdb;
CREATE DATABASE chatdb;
CREATE DATABASE recommendationdb;

\connect recommendationdb
CREATE EXTENSION IF NOT EXISTS vector;
