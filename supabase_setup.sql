CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS cloud_memory (
    key TEXT PRIMARY KEY, content TEXT, checksum TEXT, updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cloud_memory_log (
    id SERIAL PRIMARY KEY, key TEXT, checksum TEXT, length INT, logged_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS cloud_memory_log_key_idx ON cloud_memory_log(key);
