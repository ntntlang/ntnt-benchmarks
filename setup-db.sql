-- TechEmpower-style World table for benchmark database queries
-- Run against your PostgreSQL instance:
--   createdb benchmarks
--   psql -d benchmarks -f setup-db.sql

CREATE TABLE IF NOT EXISTS world (
    id SERIAL PRIMARY KEY,
    randomnumber INTEGER NOT NULL DEFAULT 0
);

-- Seed with 10,000 rows (standard TechEmpower count)
TRUNCATE world RESTART IDENTITY;
INSERT INTO world (randomnumber)
SELECT floor(random() * 10000 + 1)::int
FROM generate_series(1, 10000);
