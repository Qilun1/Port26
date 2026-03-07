from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from supabase import Client, create_client

from config import Settings


@dataclass(frozen=True)
class SensorReadingInput:
    sensor_id: int
    timestamp: datetime
    aqi: int | None
    temperature: float | None


class SensorReadingsService:
    """Service layer for historical sensor readings."""

    def __init__(self, settings: Settings) -> None:
        self._table_name = settings.supabase_sensor_readings_table
        self._client: Client = create_client(
            settings.supabase_project_url,
            settings.supabase_api_key,
        )

    def upsert_readings_bulk(
        self,
        readings: list[SensorReadingInput],
        *,
        batch_size: int = 1000,
    ) -> int:
        if not readings:
            return 0

        total_inserted = 0
        for index in range(0, len(readings), batch_size):
            batch = readings[index : index + batch_size]
            payload = [
                {
                    "sensor_id": item.sensor_id,
                    "timestamp": item.timestamp.isoformat(),
                    "aqi": item.aqi,
                    "temperature": item.temperature,
                }
                for item in batch
            ]

            (
                self._client.table(self._table_name)
                .upsert(payload, on_conflict="sensor_id,timestamp")
                .execute()
            )
            total_inserted += len(payload)

        return total_inserted

    def list_sensor_readings(
        self,
        sensor_id: int,
        start_timestamp: datetime,
        end_timestamp: datetime,
    ) -> list[dict]:
        response = (
            self._client.table(self._table_name)
            .select("sensor_id,timestamp,aqi,temperature")
            .eq("sensor_id", sensor_id)
            .gte("timestamp", start_timestamp.isoformat())
            .lte("timestamp", end_timestamp.isoformat())
            .order("timestamp")
            .execute()
        )

        return response.data or []

    def list_sensor_readings_by_sensor_id(self, sensor_id: int) -> list[dict]:
        response = (
            self._client.table(self._table_name)
            .select("sensor_id,timestamp,aqi,temperature")
            .eq("sensor_id", sensor_id)
            .order("timestamp")
            .execute()
        )

        return response.data or []
