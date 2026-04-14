-- Create a read-only user for LLM query tools.
-- This script runs automatically on first container startup (empty volume).

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'query_reader') THEN
        CREATE USER query_reader WITH PASSWORD 'query_reader_pw';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE financial_assistant TO query_reader;
GRANT USAGE ON SCHEMA public TO query_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO query_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO query_reader;
