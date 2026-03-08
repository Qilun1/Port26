-- Run in Supabase Dashboard -> SQL Editor
-- Add enabled column to control which sensors are active

alter table public.sensors 
add column if not exists enabled boolean not null default true;

create index if not exists idx_sensors_enabled on public.sensors (enabled);

comment on column public.sensors.enabled is 'Controls whether sensor is retrieved by API and used in grid calculations';
