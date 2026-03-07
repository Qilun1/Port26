from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import get_settings
from schemas.sensor import SensorListItem
from services.sensor_readings_service import SensorReadingInput, SensorReadingsService
from services.sensor_service import SensorService

HELSINKI_CENTER_LAT = 60.1699
HELSINKI_CENTER_LON = 24.9384
CITY_INFLUENCE_RADIUS_KM = 22.0


@dataclass(frozen=True)
class SensorFactors:
    sensor_id: int
    center_factor: float
    latitude_temperature_factor: float
    latitude_aqi_factor: float
    temperature_bias: float
    aqi_bias: float


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def gaussian_peak(hour_of_day: float, center_hour: float, width_hours: float) -> float:
    delta = (hour_of_day - center_hour) / width_hours
    return math.exp(-0.5 * delta * delta)


def build_sensor_factors(sensors: list[SensorListItem], rng: random.Random) -> list[SensorFactors]:
    latitudes = [sensor.latitude for sensor in sensors]
    latitude_mean = sum(latitudes) / len(latitudes)
    latitude_span = max(max(latitudes) - min(latitudes), 1e-6)

    factors: list[SensorFactors] = []
    for sensor in sensors:
        latitude_normalized = (sensor.latitude - latitude_mean) / latitude_span
        center_distance_km = haversine_distance_km(
            sensor.latitude,
            sensor.longitude,
            HELSINKI_CENTER_LAT,
            HELSINKI_CENTER_LON,
        )
        center_factor = clamp(1.0 - (center_distance_km / CITY_INFLUENCE_RADIUS_KM), 0.0, 1.0)

        factors.append(
            SensorFactors(
                sensor_id=sensor.id,
                center_factor=center_factor,
                latitude_temperature_factor=-2.0 * latitude_normalized,
                latitude_aqi_factor=-5.0 * abs(latitude_normalized),
                temperature_bias=rng.uniform(-0.6, 0.6),
                aqi_bias=rng.uniform(-2.5, 2.5),
            )
        )

    return factors


def generate_temperature(
    hour_of_day: float,
    factor: SensorFactors,
    rng: random.Random,
) -> float:
    # Day-night oscillation with warm afternoon and cool pre-dawn period.
    diurnal = 5.8 * math.cos((2 * math.pi / 24.0) * (hour_of_day - 15.0))
    baseline = 7.5 + (2.3 * factor.center_factor) + factor.latitude_temperature_factor
    noise = rng.gauss(0.0, 0.25)
    return round(clamp(baseline + diurnal + factor.temperature_bias + noise, -25.0, 40.0), 2)


def generate_aqi(
    hour_of_day: float,
    factor: SensorFactors,
    rng: random.Random,
) -> int:
    diurnal_background = 4.2 * math.cos((2 * math.pi / 24.0) * (hour_of_day - 13.0))
    rush_hour_peak = (
        20.0 * gaussian_peak(hour_of_day, center_hour=9.0, width_hours=1.15)
        + 22.0 * gaussian_peak(hour_of_day, center_hour=16.0, width_hours=1.25)
    )
    baseline = 33.0 + (12.0 * factor.center_factor) + factor.latitude_aqi_factor
    noise = rng.gauss(0.0, 1.5)
    return int(round(clamp(baseline + diurnal_background + rush_hour_peak + factor.aqi_bias + noise, 8.0, 260.0)))


def build_timestamps_local(
    simulation_date: date,
    timezone_name: str,
    interval_minutes: int,
) -> list[datetime]:
    tz = resolve_timezone(timezone_name)
    start_local = datetime(
        simulation_date.year,
        simulation_date.month,
        simulation_date.day,
        tzinfo=tz,
    )
    intervals = (24 * 60) // interval_minutes
    return [start_local + timedelta(minutes=interval_minutes * index) for index in range(intervals)]


def generate_day_readings(
    sensors: list[SensorListItem],
    simulation_date: date,
    timezone_name: str,
    interval_minutes: int,
    seed: int,
) -> list[SensorReadingInput]:
    rng = random.Random(seed)
    factors = build_sensor_factors(sensors, rng)
    factors_by_sensor = {factor.sensor_id: factor for factor in factors}
    timestamps_local = build_timestamps_local(simulation_date, timezone_name, interval_minutes)

    readings: list[SensorReadingInput] = []
    for timestamp_local in timestamps_local:
        hour_of_day = timestamp_local.hour + (timestamp_local.minute / 60.0)
        timestamp_utc = timestamp_local.astimezone(UTC)

        for sensor in sensors:
            factor = factors_by_sensor[sensor.id]
            readings.append(
                SensorReadingInput(
                    sensor_id=sensor.id,
                    timestamp=timestamp_utc,
                    aqi=generate_aqi(hour_of_day, factor, rng),
                    temperature=generate_temperature(hour_of_day, factor, rng),
                )
            )

    return readings


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one day of synthetic AQI and temperature readings for enabled sensors.",
    )
    parser.add_argument(
        "--date",
        dest="day",
        default=None,
        help="Simulation date in YYYY-MM-DD. Defaults to today in the selected timezone.",
    )
    parser.add_argument(
        "--timezone",
        default="Europe/Helsinki",
        help="Timezone used for day/night and rush-hour effects.",
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=15,
        help="Sampling cadence in minutes. 15 creates 96 samples per sensor/day.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=26026,
        help="Deterministic random seed for reproducible simulations.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows per upsert batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate data but do not write to the database.",
    )
    return parser.parse_args()


def resolve_simulation_date(day_argument: str | None, timezone_name: str) -> date:
    if day_argument:
        return date.fromisoformat(day_argument)

    now_local = datetime.now(resolve_timezone(timezone_name))
    return now_local.date()


def resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Timezone '{timezone_name}' is not available. "
            "Install tzdata in the backend environment and retry."
        ) from exc


def main() -> None:
    args = parse_arguments()
    try:
        simulation_date = resolve_simulation_date(args.day, args.timezone)
    except ValueError as exc:
        print(f"Invalid simulation settings: {exc}")
        return

    settings = get_settings()
    sensor_service = SensorService(settings)
    readings_service = SensorReadingsService(settings)

    sensors = sensor_service.list_sensors()
    if not sensors:
        print("No enabled sensors found. Nothing to simulate.")
        return

    readings = generate_day_readings(
        sensors=sensors,
        simulation_date=simulation_date,
        timezone_name=args.timezone,
        interval_minutes=args.interval_minutes,
        seed=args.seed,
    )

    expected_per_sensor = (24 * 60) // args.interval_minutes
    print(
        f"Prepared {len(readings)} rows for {len(sensors)} sensors "
        f"({expected_per_sensor} rows/sensor) on {simulation_date.isoformat()} "
        f"in {args.timezone}."
    )

    if args.dry_run:
        preview = readings[:5]
        print("Dry run enabled. Preview of first rows:")
        for item in preview:
            print(
                f"sensor_id={item.sensor_id} ts={item.timestamp.isoformat()} "
                f"temp={item.temperature} aqi={item.aqi}"
            )
        return

    upserted = readings_service.upsert_readings_bulk(readings, batch_size=args.batch_size)
    print(f"Upserted {upserted} rows into sensor_readings.")


if __name__ == "__main__":
    main()
