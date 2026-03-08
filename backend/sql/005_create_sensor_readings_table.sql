-- Run in Supabase Dashboard -> SQL Editor
-- Time-series table for sensor AQI and temperature readings.

create table if not exists public.sensor_readings (
    id bigserial primary key,
    sensor_id bigint not null,
    timestamp timestamptz not null,
    aqi integer,
    temperature double precision,
    created_at timestamptz not null default now(),
    constraint sensor_readings_sensor_id_fkey
        foreign key (sensor_id)
        references public.sensors(id)
        on delete cascade,
    constraint sensor_readings_sensor_timestamp_key unique (sensor_id, timestamp),
    constraint sensor_readings_aqi_check check (aqi is null or aqi >= 0),
    constraint sensor_readings_temperature_check check (
        temperature is null or (temperature >= -50 and temperature <= 60)
    )
);

create index if not exists idx_sensor_readings_sensor_time
    on public.sensor_readings (sensor_id, timestamp desc);
create index if not exists idx_sensor_readings_time
    on public.sensor_readings (timestamp desc);
