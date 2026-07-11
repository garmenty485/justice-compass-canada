-- Lakebase schema for Justice Compass (PostgreSQL dialect)
-- Integration model: Lake↔Base (Synced Tables + CDF) — see docs/LAKEBASE.md
-- Run in your Free Edition Lakebase project (1 project/account).

CREATE TABLE IF NOT EXISTS cases (
    case_id         VARCHAR(64) PRIMARY KEY,
    citation        VARCHAR(128) NOT NULL,
    title           TEXT NOT NULL,
    court           VARCHAR(128),
    decision_date   DATE,
    canlii_url      TEXT,
    topics          TEXT[],
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_logs (
    log_id          BIGSERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    answer_preview  TEXT,
    citation_count  INT DEFAULT 0,
    mock_mode       BOOLEAN DEFAULT FALSE,
    latency_ms      INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          VARCHAR(64) PRIMARY KEY,
    layer           VARCHAR(16) NOT NULL CHECK (layer IN ('bronze', 'silver', 'gold', 'serving')),
    status          VARCHAR(16) NOT NULL,
    row_count       INT,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS data_quality_scores (
    case_id         VARCHAR(64) REFERENCES cases(case_id),
    check_name      VARCHAR(64) NOT NULL,
    score           NUMERIC(5, 2),
    checked_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, check_name)
);

CREATE INDEX IF NOT EXISTS idx_query_logs_created ON query_logs(created_at DESC);
