# pyright: reportMissingImports=false

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from supabase import Client, create_client

from config import Settings


@dataclass(frozen=True)
class TimestepMetricInput:
    date: date
    timestamp_utc: datetime
    avg_aqi: float | None
    avg_temperature_c: float | None
    sensor_count_aqi: int
    sensor_count_temperature: int


class MetricsService:
    """Service layer for daily aggregated timestep metrics."""

    def __init__(self, settings: Settings) -> None:
        self._table_name = settings.supabase_metrics_table
        self._client: Client = create_client(
            settings.supabase_project_url,
            settings.supabase_api_key,
        )

    def upsert_metrics_bulk(
        self,
        metrics: list[TimestepMetricInput],
        *,
        batch_size: int = 1000,
    ) -> int:
        if not metrics:
            return 0

        total_inserted = 0
        for index in range(0, len(metrics), batch_size):
            batch = metrics[index : index + batch_size]
            payload = [
                {
                    "date": item.date.isoformat(),
                    "timestamp_utc": item.timestamp_utc.isoformat(),
                    "avg_aqi": item.avg_aqi,
                    "avg_temperature_c": item.avg_temperature_c,
                    "sensor_count_aqi": item.sensor_count_aqi,
                    "sensor_count_temperature": item.sensor_count_temperature,
                }
                for item in batch
            ]

            (
                self._client.table(self._table_name)
                .upsert(payload, on_conflict="date,timestamp_utc")
                .execute()
            )
            total_inserted += len(payload)

        return total_inserted

    def list_metrics_by_date(self, selected_date: date) -> list[dict]:
        response = (
            self._client.table(self._table_name)
            .select(
                "date,timestamp_utc,avg_aqi,avg_temperature_c,"
                "sensor_count_aqi,sensor_count_temperature"
            )
            .eq("date", selected_date.isoformat())
            .order("timestamp_utc")
            .execute()
        )

        return response.data or []
