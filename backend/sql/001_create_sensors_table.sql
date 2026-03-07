-- Run in Supabase Dashboard -> SQL Editor
-- Primary table for sensor metadata and latest readings.

create table if not exists public.sensors (
    id bigserial primary key,
    sensor_code text not null unique,
    name text,
    latitude double precision not null,
    longitude double precision not null,
    latest_temperature_c double precision,
    latest_air_pressure_hpa double precision,
    latest_aqi integer,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint sensors_latitude_check check (latitude between -90 and 90),
    constraint sensors_longitude_check check (longitude between -180 and 180),
    constraint sensors_aqi_check check (latest_aqi is null or latest_aqi >= 0)
);

create index if not exists idx_sensors_coordinates on public.sensors (latitude, longitude);
create index if not exists idx_sensors_updated_at on public.sensors (updated_at desc);

insert into public.sensors (
    sensor_code,
    name,
    latitude,
    longitude,
    latest_temperature_c,
    latest_air_pressure_hpa,
    latest_aqi
)
values
    ('SEN-001', 'City Center', 50.087451, 14.420671, 11.3, 1015.2, 34),
    ('SEN-002', 'Riverside', 50.095950, 14.430610, 10.9, 1014.8, 40),
    ('SEN-003', 'North Hill', 50.103100, 14.410300, 9.8, 1016.0, 27)
on conflict (sensor_code) do nothing;
