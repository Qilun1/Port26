from supabase import Client, create_client

from config import Settings
from schemas import SensorListItem


class SensorService:
    """Service layer for sensor catalog operations."""

    def __init__(self, settings: Settings) -> None:
        self._table_name = settings.supabase_sensors_table
        self._client: Client = create_client(
            settings.supabase_project_url,
            settings.supabase_api_key,
        )

    def list_sensors(self) -> list[SensorListItem]:
        response = (
            self._client.table(self._table_name)
            .select(
                "id,sensor_code,name,latitude,longitude,latest_temperature_c,latest_air_pressure_hpa,latest_aqi"
            )
            .order("id")
            .execute()
        )

        return [SensorListItem.model_validate(item) for item in response.data or []]
