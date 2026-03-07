import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from schemas import InterpolationMetric, InterpolationTimelineResponse
from services.interpolation.timeline_loader import (
    InterpolationTimelineLoaderService,
    InterpolationTimelineNotFoundError,
)


class _StubSettings:
    def __init__(self, artifacts_dir: Path) -> None:
        self.interpolation_timeline_artifacts_dir = str(artifacts_dir)


class _FakeTimelineLoader:
    def __init__(self, payload: InterpolationTimelineResponse | None = None, missing: bool = False) -> None:
        self._payload = payload
        self._missing = missing

    def load_timeline(
        self,
        metric: InterpolationMetric,
        timeline_date: date,
        grid_size_meters: float,
    ) -> InterpolationTimelineResponse:
        if self._missing:
            raise InterpolationTimelineNotFoundError("missing")
        assert self._payload is not None
        return self._payload


def _build_timeline_payload(frame_count: int = 96) -> dict:
    start = datetime.fromisoformat("2026-03-07T00:00:00+02:00")
    timestamps = [start + timedelta(minutes=15 * index) for index in range(frame_count)]
    active_indices = [0, 1, 3]

    return {
        "metric": "aqi",
        "date": "2026-03-07",
        "grid_size_meters": 100.0,
        "rows": 2,
        "cols": 2,
        "bounding_box": {
            "min_latitude": 60.05,
            "min_longitude": 24.72,
            "max_latitude": 60.29,
            "max_longitude": 25.16,
        },
        "timestamps": [value.isoformat() for value in timestamps],
        "active_indices": active_indices,
        "frames": [
            {
                "timestamp": value.isoformat(),
                "values": [20.0, 22.0, 21.0],
            }
            for value in timestamps
        ],
    }


def test_timeline_loader_reads_artifact_with_96_frames(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "timelines"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    loader = InterpolationTimelineLoaderService(_StubSettings(artifact_dir))
    filename = loader.build_artifact_filename(
        metric=InterpolationMetric.aqi,
        timeline_date=date(2026, 3, 7),
        grid_size_meters=100.0,
    )

    payload = _build_timeline_payload(frame_count=96)
    with (artifact_dir / filename).open("w", encoding="utf-8") as file:
        json.dump(payload, file)

    timeline = loader.load_timeline(
        metric=InterpolationMetric.aqi,
        timeline_date=date(2026, 3, 7),
        grid_size_meters=100.0,
    )

    assert len(timeline.frames) == 96
    assert timeline.rows == 2
    assert timeline.cols == 2
    assert timeline.active_indices == [0, 1, 3]
    assert all(len(frame.values) == len(timeline.active_indices) for frame in timeline.frames)


def test_timeline_loader_resolve_path_uses_stable_filename(tmp_path: Path) -> None:
    loader = InterpolationTimelineLoaderService(_StubSettings(tmp_path))
    path = loader.resolve_artifact_path(
        metric=InterpolationMetric.temperature,
        timeline_date=date(2026, 3, 7),
        grid_size_meters=75.5,
    )

    assert path.name == "temperature_2026-03-07_75p5m.json"


def test_interpolation_timeline_endpoint_returns_payload() -> None:
    from endpoints.interpolation import get_timeline_loader_service

    payload = InterpolationTimelineResponse.model_validate(_build_timeline_payload(frame_count=96))
    app.dependency_overrides[get_timeline_loader_service] = lambda: _FakeTimelineLoader(payload=payload)

    client = TestClient(app)
    response = client.get("/interpolation/timeline?metric=aqi&date=2026-03-07&grid_size_meters=100")

    assert response.status_code == 200
    body = response.json()
    assert body["metric"] == "aqi"
    assert body["date"] == "2026-03-07"
    assert len(body["frames"]) == 96
    assert body["active_indices"] == [0, 1, 3]
    assert len(body["frames"][0]["values"]) == len(body["active_indices"])

    app.dependency_overrides.clear()


def test_interpolation_timeline_endpoint_returns_404_when_missing() -> None:
    from endpoints.interpolation import get_timeline_loader_service

    app.dependency_overrides[get_timeline_loader_service] = lambda: _FakeTimelineLoader(missing=True)

    client = TestClient(app)
    response = client.get("/interpolation/timeline?metric=aqi&date=2026-03-07&grid_size_meters=100")

    assert response.status_code == 404
    assert "Precomputed interpolation timeline" in response.json()["detail"]

    app.dependency_overrides.clear()


def test_timeline_schema_rejects_unsorted_active_indices() -> None:
    payload = _build_timeline_payload(frame_count=2)
    payload["active_indices"] = [1, 0, 3]

    try:
        InterpolationTimelineResponse.model_validate(payload)
    except ValueError as error:
        assert "strictly increasing" in str(error)
        return

    raise AssertionError("Expected validation error for unsorted active_indices")


def test_sparse_frames_are_smaller_than_dense_grid() -> None:
    timeline = InterpolationTimelineResponse.model_validate(_build_timeline_payload(frame_count=4))

    dense_length = timeline.rows * timeline.cols
    assert dense_length > len(timeline.active_indices)
    assert all(len(frame.values) == len(timeline.active_indices) for frame in timeline.frames)
