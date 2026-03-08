from pydantic import BaseModel


class SensorListItem(BaseModel):
    id: int
    sensor_code: str
    name: str | None = None
    latitude: float
    longitude: float
    latest_temperature_c: float | None = None
    latest_air_pressure_hpa: float | None = None
    latest_aqi: int | None = None
    enabled: bool = True


class SensorListResponse(BaseModel):
    sensors: list[SensorListItem]
    count: int


class SensorHistoryReadingItem(BaseModel):
    timestamp: str
    aqi: int | None = None
    temperature: float | None = None


class SensorHistoryResponse(BaseModel):
    sensor_id: int
    readings: list[SensorHistoryReadingItem]
    count: int
