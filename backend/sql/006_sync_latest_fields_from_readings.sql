-- Run in Supabase Dashboard -> SQL Editor
-- Keep sensors.latest_* fields synchronized from newest readings.

create or replace function public.sync_sensor_latest_fields_from_reading()
returns trigger
language plpgsql
as $$
declare
    existing_updated_at timestamptz;
begin
    select s.updated_at
    into existing_updated_at
    from public.sensors s
    where s.id = new.sensor_id;

    update public.sensors
    set
        latest_aqi = coalesce(new.aqi, latest_aqi),
        latest_temperature_c = coalesce(new.temperature, latest_temperature_c),
        updated_at = case
            when existing_updated_at is null or new.timestamp >= existing_updated_at then new.timestamp
            else updated_at
        end
    where id = new.sensor_id
      and (existing_updated_at is null or new.timestamp >= existing_updated_at);

    return new;
end;
$$;

drop trigger if exists trg_sensor_readings_sync_latest on public.sensor_readings;

create trigger trg_sensor_readings_sync_latest
after insert or update on public.sensor_readings
for each row
execute function public.sync_sensor_latest_fields_from_reading();
