from typing import Sequence

from config import Settings, get_settings
from services.grid.grid_builder import (
    DEFAULT_BBOX_MARGIN_METERS,
    build_grid_cells,
    build_grid_from_sensors,
)
from services.grid.models import BoundingBox, GridCell

from .idw import (
    DEFAULT_IDW_POWER,
    DEFAULT_MAX_NEIGHBORS,
    DISTANCE_EPSILON_METERS,
    interpolate_idw_point,
)
from .models import InterpolatedGridCell, SensorPoint


class GridInterpolationService:
    """Create regular grids and interpolate sensor values over them."""

    def __init__(self, settings: Settings) -> None:
        # Keep dependency signature aligned with backend service conventions.
        self._settings = settings

    def interpolate_over_bbox(
        self,
        sensors: Sequence[SensorPoint],
        bounding_box: BoundingBox,
        grid_size_meters: float,
        *,
        include_bounds: bool = True,
        idw_power: float = DEFAULT_IDW_POWER,
        distance_epsilon_meters: float = DISTANCE_EPSILON_METERS,
        max_neighbors: int | None = DEFAULT_MAX_NEIGHBORS,
    ) -> list[InterpolatedGridCell]:
        grid_cells = build_grid_cells(
            bounding_box=bounding_box,
            grid_size_meters=grid_size_meters,
            include_bounds=include_bounds,
        )
        return self._interpolate_grid_cells(
            grid_cells=grid_cells,
            sensors=sensors,
            idw_power=idw_power,
            distance_epsilon_meters=distance_epsilon_meters,
            max_neighbors=max_neighbors,
        )

    def interpolate_from_sensor_extent(
        self,
        sensors: Sequence[SensorPoint],
        grid_size_meters: float,
        *,
        bbox_margin_meters: float = DEFAULT_BBOX_MARGIN_METERS,
        include_bounds: bool = True,
        idw_power: float = DEFAULT_IDW_POWER,
        distance_epsilon_meters: float = DISTANCE_EPSILON_METERS,
        max_neighbors: int | None = DEFAULT_MAX_NEIGHBORS,
    ) -> tuple[BoundingBox, list[InterpolatedGridCell]]:
        bounding_box, grid_cells = build_grid_from_sensors(
            sensors=sensors,
            grid_size_meters=grid_size_meters,
            margin_meters=bbox_margin_meters,
            include_bounds=include_bounds,
        )

        interpolated_cells = self._interpolate_grid_cells(
            grid_cells=grid_cells,
            sensors=sensors,
            idw_power=idw_power,
            distance_epsilon_meters=distance_epsilon_meters,
            max_neighbors=max_neighbors,
        )
        return bounding_box, interpolated_cells

    def _interpolate_grid_cells(
        self,
        grid_cells: Sequence[GridCell],
        sensors: Sequence[SensorPoint],
        idw_power: float,
        distance_epsilon_meters: float,
        max_neighbors: int | None,
    ) -> list[InterpolatedGridCell]:
        return [
            InterpolatedGridCell(
                row=cell.row,
                col=cell.col,
                latitude=cell.latitude,
                longitude=cell.longitude,
                interpolated_value=interpolate_idw_point(
                    latitude=cell.latitude,
                    longitude=cell.longitude,
                    sensors=sensors,
                    power=idw_power,
                    distance_epsilon_meters=distance_epsilon_meters,
                    max_neighbors=max_neighbors,
                ),
                min_latitude=cell.min_latitude,
                min_longitude=cell.min_longitude,
                max_latitude=cell.max_latitude,
                max_longitude=cell.max_longitude,
            )
            for cell in grid_cells
        ]


def build_default_interpolation_service() -> GridInterpolationService:
    return GridInterpolationService(get_settings())


def demo_helsinki_interpolation(
    grid_size_meters: float = 100.0,
) -> tuple[BoundingBox, list[InterpolatedGridCell]]:
    """Small local demo that can be called from REPL or a script."""

    sensors = [
        SensorPoint(id="KAMPI", latitude=60.1699, longitude=24.9384, value=9.5),
        SensorPoint(id="KALLIO", latitude=60.1841, longitude=24.9506, value=8.9),
        SensorPoint(id="OTANIEMI", latitude=60.1845, longitude=24.8276, value=8.2),
    ]
    service = build_default_interpolation_service()
    return service.interpolate_from_sensor_extent(
        sensors=sensors,
        grid_size_meters=grid_size_meters,
    )
