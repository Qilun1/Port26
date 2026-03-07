from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import get_settings
from schemas import InterpolationMetric
from services import (
    GridInterpolationService,
    MetricsService,
    SensorPoint,
    SensorReadingsService,
    SensorService,
    TimestepMetricInput,
)
from services.grid import derive_bbox_from_sensors
from services.interpolation import extract_active_indices, extract_sparse_values
from services.interpolation.timeline_loader import InterpolationTimelineLoaderService


@dataclass(frozen=True)
class _ReadingRow:
    sensor_id: int
    timestamp_utc: datetime
    temperature: float | None
    aqi: float | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one-day precomputed interpolation timeline artifact from sensor_readings.",
    )
    parser.add_argument("--metric", choices=["temperature", "aqi"], required=True)
    parser.add_argument("--date", dest="day", required=True, help="Day in YYYY-MM-DD.")
    parser.add_argument("--grid-size-meters", type=float, default=100.0)
    parser.add_argument("--timezone", default="Europe/Helsinki")
    parser.add_argument("--include-bounds", action="store_true")
    return parser.parse_args()


def _resolve_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            f"Timezone '{timezone_name}' is not available. Install tzdata and retry."
        ) from exc


def _parse_row_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


def _load_rows_for_day(
    day: date,
    timezone_name: str,
) -> dict[tuple[int, datetime], _ReadingRow]:
    settings = get_settings()
    sensor_service = SensorService(settings)
    readings_service = SensorReadingsService(settings)

    sensors = sensor_service.list_sensors()
    if not sensors:
        raise ValueError("No enabled sensors found.")

    tz = _resolve_timezone(timezone_name)
    day_start_local = datetime(day.year, day.month, day.day, tzinfo=tz)
    day_end_local = day_start_local + timedelta(days=1)

    rows_by_key: dict[tuple[int, datetime], _ReadingRow] = {}

    for sensor in sensors:
        rows = readings_service.list_sensor_readings_by_sensor_id(sensor.id)
        for row in rows:
            timestamp_utc = _parse_row_timestamp(str(row["timestamp"]))
            timestamp_local = timestamp_utc.astimezone(tz)
            if not (day_start_local <= timestamp_local < day_end_local):
                continue

            raw_temperature = row.get("temperature")
            raw_aqi = row.get("aqi")
            rounded_utc = timestamp_utc.replace(second=0, microsecond=0)
            rows_by_key[(sensor.id, rounded_utc)] = _ReadingRow(
                sensor_id=sensor.id,
                timestamp_utc=rounded_utc,
                temperature=float(raw_temperature) if raw_temperature is not None else None,
                aqi=float(raw_aqi) if raw_aqi is not None else None,
            )

    return rows_by_key


def _generate_timestamps_for_day(day: date, timezone_name: str) -> list[datetime]:
    tz = _resolve_timezone(timezone_name)
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    return [start + timedelta(minutes=15 * index) for index in range(96)]


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    metric = InterpolationMetric(args.metric)
    selected_day = date.fromisoformat(args.day)

    sensor_service = SensorService(settings)
    interpolation_service = GridInterpolationService(settings)
    metrics_service = MetricsService(settings)
    sensors = sensor_service.list_sensors()

    if not sensors:
        print("No enabled sensors found. Nothing to interpolate.")
        return

    readings_by_key = _load_rows_for_day(
        day=selected_day,
        timezone_name=args.timezone,
    )

    sensor_points_for_bbox = [
        SensorPoint(
            id=str(sensor.id),
            latitude=sensor.latitude,
            longitude=sensor.longitude,
            value=0.0,
        )
        for sensor in sensors
    ]
    bounding_box = derive_bbox_from_sensors(sensor_points_for_bbox)

    frame_timestamps_local = _generate_timestamps_for_day(selected_day, args.timezone)
    frames: list[dict[str, object]] = []
    timestep_metrics: list[TimestepMetricInput] = []
    static_mask: list[int] | None = None
    active_indices: list[int] | None = None
    rows = 0
    cols = 0

    for timestamp_local in frame_timestamps_local:
        timestamp_utc = timestamp_local.astimezone(UTC).replace(second=0, microsecond=0)

        frame_sensors: list[SensorPoint] = []
        frame_aqi_values: list[float] = []
        frame_temperature_values: list[float] = []
        for sensor in sensors:
            reading_row = readings_by_key.get((sensor.id, timestamp_utc))
            if reading_row is None:
                continue

            if reading_row.aqi is not None:
                frame_aqi_values.append(reading_row.aqi)
            if reading_row.temperature is not None:
                frame_temperature_values.append(reading_row.temperature)

            value = (
                reading_row.temperature
                if metric == InterpolationMetric.temperature
                else reading_row.aqi
            )
            if value is None:
                continue

            frame_sensors.append(
                SensorPoint(
                    id=str(sensor.id),
                    latitude=sensor.latitude,
                    longitude=sensor.longitude,
                    value=value,
                )
            )

        timestep_metrics.append(
            TimestepMetricInput(
                date=selected_day,
                timestamp_utc=timestamp_utc,
                avg_aqi=(sum(frame_aqi_values) / len(frame_aqi_values)) if frame_aqi_values else None,
                avg_temperature_c=(sum(frame_temperature_values) / len(frame_temperature_values)) if frame_temperature_values else None,
                sensor_count_aqi=len(frame_aqi_values),
                sensor_count_temperature=len(frame_temperature_values),
            )
        )

        if not frame_sensors:
            raise ValueError(
                f"No sensor values for {timestamp_local.isoformat()} ({metric.value})."
            )

        matrix = interpolation_service.interpolate_masked_matrix_over_bbox(
            sensors=frame_sensors,
            bounding_box=bounding_box,
            grid_size_meters=args.grid_size_meters,
            include_bounds=args.include_bounds,
        )

        rows = matrix.rows
        cols = matrix.cols

        if static_mask is None:
            static_mask = matrix.mask
            active_indices = extract_active_indices(static_mask)

            if not active_indices:
                raise ValueError("Interpolation mask does not contain any covered cells.")
        elif matrix.mask != static_mask:
            raise ValueError(
                "Interpolation coverage mask changed across frames. "
                "Static active-index timeline generation requires stable day mask."
            )

        assert active_indices is not None
        sparse_values = extract_sparse_values(matrix.values, active_indices)

        frames.append(
            {
                "timestamp": timestamp_local.isoformat(),
                "values": sparse_values,
            }
        )

    if static_mask is None or active_indices is None:
        raise ValueError("Failed to produce interpolation active indices.")

    timeline_payload = {
        "metric": metric.value,
        "date": selected_day.isoformat(),
        "grid_size_meters": float(args.grid_size_meters),
        "rows": rows,
        "cols": cols,
        "bounding_box": {
            "min_latitude": bounding_box.min_latitude,
            "min_longitude": bounding_box.min_longitude,
            "max_latitude": bounding_box.max_latitude,
            "max_longitude": bounding_box.max_longitude,
        },
        "active_indices": active_indices,
        "timestamps": [timestamp.isoformat() for timestamp in frame_timestamps_local],
        "frames": frames,
    }

    loader = InterpolationTimelineLoaderService(settings)
    output_path = loader.resolve_artifact_path(
        metric=metric,
        timeline_date=selected_day,
        grid_size_meters=args.grid_size_meters,
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(timeline_payload, file)

    upserted_metrics = metrics_service.upsert_metrics_bulk(timestep_metrics)

    print(f"Wrote timeline artifact: {output_path}")
    print(f"Upserted {upserted_metrics} rows into metrics table.")
    print(f"Frames: {len(frames)} | Grid: {rows}x{cols} | Metric: {metric.value}")


if __name__ == "__main__":
    main()
