from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from config import Settings, get_settings
from schemas import InterpolationMetric, InterpolationTimelineResponse


class InterpolationTimelineNotFoundError(FileNotFoundError):
    """Raised when no precomputed timeline artifact is found on disk."""


class InterpolationTimelineLoaderService:
    """Load precomputed interpolation timelines from local filesystem artifacts."""

    def __init__(self, settings: Settings) -> None:
        self._artifacts_dir = Path(settings.interpolation_timeline_artifacts_dir)

    def build_artifact_filename(
        self,
        metric: InterpolationMetric,
        timeline_date: date,
        grid_size_meters: float,
    ) -> str:
        grid_token = self._format_grid_size_token(grid_size_meters)
        return f"{metric.value}_{timeline_date.isoformat()}_{grid_token}m.json"

    def resolve_artifact_path(
        self,
        metric: InterpolationMetric,
        timeline_date: date,
        grid_size_meters: float,
    ) -> Path:
        return self._artifacts_dir / self.build_artifact_filename(
            metric=metric,
            timeline_date=timeline_date,
            grid_size_meters=grid_size_meters,
        )

    def load_timeline(
        self,
        metric: InterpolationMetric,
        timeline_date: date,
        grid_size_meters: float,
    ) -> InterpolationTimelineResponse:
        artifact_path = self.resolve_artifact_path(
            metric=metric,
            timeline_date=timeline_date,
            grid_size_meters=grid_size_meters,
        )

        if not artifact_path.is_file():
            raise InterpolationTimelineNotFoundError(
                f"Precomputed interpolation timeline not found: {artifact_path}"
            )

        try:
            with artifact_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Timeline artifact contains invalid JSON: {artifact_path}") from exc

        timeline = InterpolationTimelineResponse.model_validate(payload)

        if timeline.metric != metric:
            raise ValueError("Timeline artifact metric does not match query metric.")
        if timeline.date != timeline_date:
            raise ValueError("Timeline artifact date does not match query date.")
        if timeline.grid_size_meters != grid_size_meters:
            raise ValueError("Timeline artifact grid_size_meters does not match query value.")

        return timeline

    @staticmethod
    def _format_grid_size_token(grid_size_meters: float) -> str:
        if float(grid_size_meters).is_integer():
            return str(int(grid_size_meters))

        return (
            format(grid_size_meters, ".6f")
            .rstrip("0")
            .rstrip(".")
            .replace(".", "p")
        )


def build_default_timeline_loader_service() -> InterpolationTimelineLoaderService:
    return InterpolationTimelineLoaderService(get_settings())
