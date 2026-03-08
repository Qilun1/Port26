CREATE TABLE IF NOT EXISTS public.metrics (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    timestamp_utc TIMESTAMPTZ NOT NULL,
    avg_aqi DOUBLE PRECISION,
    avg_temperature_c DOUBLE PRECISION,
    sensor_count_aqi INTEGER,
    sensor_count_temperature INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (date, timestamp_utc)
);

CREATE INDEX IF NOT EXISTS idx_metrics_date_timestamp
    ON public.metrics (date, timestamp_utc DESC);
