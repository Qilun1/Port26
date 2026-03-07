from datetime import UTC, datetime

from fastapi.testclient import TestClient

from main import app
from schemas.sensor import SensorListItem


class _FakeSensorService:
    def __init__(self, sensors: list[SensorListItem]) -> None:
        self._sensors = sensors

    def list_sensors(self) -> list[SensorListItem]:
        return self._sensors


class _FakeSensorReadingsService:
    def __init__(self, readings_by_sensor: dict[int, list[dict]]) -> None:
        self._readings_by_sensor = readings_by_sensor

    def list_sensor_readings_by_sensor_id(self, sensor_id: int) -> list[dict]:
        return self._readings_by_sensor.get(sensor_id, [])


def _build_sensor(sensor_id: int) -> SensorListItem:
    return SensorListItem(
        id=sensor_id,
        sensor_code=f"SEN-{sensor_id:03d}",
        name=f"Sensor {sensor_id}",
        latitude=60.17,
        longitude=24.94,
        latest_temperature_c=5.5,
        latest_air_pressure_hpa=1009.0,
        latest_aqi=31,
        enabled=True,
    )


def test_get_sensor_history_by_id_returns_ordered_readings() -> None:
    from endpoints.sensors import get_sensor_readings_service, get_sensor_service

    sensor_id = 101
    app.dependency_overrides[get_sensor_service] = lambda: _FakeSensorService([_build_sensor(sensor_id)])
    app.dependency_overrides[get_sensor_readings_service] = lambda: _FakeSensorReadingsService(
        {
            sensor_id: [
                {
                    "sensor_id": sensor_id,
                    "timestamp": datetime(2026, 3, 7, 0, 0, tzinfo=UTC).isoformat(),
                    "aqi": 30,
                    "temperature": 3.1,
                },
                {
                    "sensor_id": sensor_id,
                    "timestamp": datetime(2026, 3, 7, 0, 15, tzinfo=UTC).isoformat(),
                    "aqi": 31,
                    "temperature": 3.3,
                },
            ]
        }
    )

    client = TestClient(app)
    response = client.get(f"/sensors/{sensor_id}/readings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sensor_id"] == sensor_id
    assert payload["count"] == 2
    assert payload["readings"][0]["timestamp"] == "2026-03-07T00:00:00+00:00"
    assert payload["readings"][1]["aqi"] == 31

    app.dependency_overrides.clear()


def test_get_sensor_history_by_id_returns_404_for_unknown_sensor() -> None:
    from endpoints.sensors import get_sensor_readings_service, get_sensor_service

    app.dependency_overrides[get_sensor_service] = lambda: _FakeSensorService([_build_sensor(1)])
    app.dependency_overrides[get_sensor_readings_service] = lambda: _FakeSensorReadingsService({})

    client = TestClient(app)
    response = client.get("/sensors/404/readings")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sensor was not found."

    app.dependency_overrides.clear()


def test_get_sensor_history_by_id_returns_empty_readings_for_existing_sensor() -> None:
    from endpoints.sensors import get_sensor_readings_service, get_sensor_service

    sensor_id = 7
    app.dependency_overrides[get_sensor_service] = lambda: _FakeSensorService([_build_sensor(sensor_id)])
    app.dependency_overrides[get_sensor_readings_service] = lambda: _FakeSensorReadingsService({sensor_id: []})

    client = TestClient(app)
    response = client.get(f"/sensors/{sensor_id}/readings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sensor_id"] == sensor_id
    assert payload["count"] == 0
    assert payload["readings"] == []

    app.dependency_overrides.clear()
