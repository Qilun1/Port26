# pyright: reportMissingImports=false

from datetime import date

from fastapi.testclient import TestClient

from main import app


class _FakeMetricsService:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def list_metrics_by_date(self, selected_date: date) -> list[dict]:
        assert selected_date == date(2026, 3, 7)
        return self._rows


class _FailingMetricsService:
    def list_metrics_by_date(self, _selected_date: date) -> list[dict]:
        raise RuntimeError("backend fetch failed")


def test_get_interpolation_metrics_returns_items() -> None:
    from endpoints.interpolation import get_metrics_service

    app.dependency_overrides[get_metrics_service] = lambda: _FakeMetricsService(
        [
            {
                "timestamp_utc": "2026-03-07T00:00:00+00:00",
                "avg_aqi": 42.0,
                "avg_temperature_c": 3.5,
                "sensor_count_aqi": 10,
                "sensor_count_temperature": 12,
            },
            {
                "timestamp_utc": "2026-03-07T00:15:00+00:00",
                "avg_aqi": 44.0,
                "avg_temperature_c": 3.8,
                "sensor_count_aqi": 9,
                "sensor_count_temperature": 11,
            },
        ]
    )

    client = TestClient(app)
    response = client.get("/interpolation/metrics?date=2026-03-07")

    assert response.status_code == 200
    payload = response.json()
    assert payload["date"] == "2026-03-07"
    assert payload["count"] == 2
    assert payload["items"][0]["timestamp_utc"] == "2026-03-07T00:00:00Z"
    assert payload["items"][0]["avg_aqi"] == 42.0
    assert payload["items"][0]["avg_temperature_c"] == 3.5
    assert payload["items"][0]["sensor_count_aqi"] == 10
    assert payload["items"][0]["sensor_count_temperature"] == 12

    app.dependency_overrides.clear()


def test_get_interpolation_metrics_returns_502_on_service_error() -> None:
    from endpoints.interpolation import get_metrics_service

    app.dependency_overrides[get_metrics_service] = lambda: _FailingMetricsService()

    client = TestClient(app)
    response = client.get("/interpolation/metrics?date=2026-03-07")

    assert response.status_code == 502
    assert (
        response.json()["detail"]
        == "Could not fetch interpolation timestep metrics from data source."
    )

    app.dependency_overrides.clear()
