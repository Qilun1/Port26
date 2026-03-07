import math
from typing import Protocol, Sequence

from .geo import meters_to_latitude_degrees, meters_to_longitude_degrees
from .models import BoundingBox, GridCell

MIN_GRID_SIZE_METERS = 50.0
MAX_GRID_SIZE_METERS = 200.0
DEFAULT_BBOX_MARGIN_METERS = 200.0


class HasCoordinates(Protocol):
    latitude: float
    longitude: float


def validate_grid_size_meters(grid_size_meters: float) -> None:
    if grid_size_meters < MIN_GRID_SIZE_METERS or grid_size_meters > MAX_GRID_SIZE_METERS:
        raise ValueError(
            f"grid_size_meters must be between {MIN_GRID_SIZE_METERS:.0f} and {MAX_GRID_SIZE_METERS:.0f}."
        )


def derive_bbox_from_sensors(
    sensors: Sequence[HasCoordinates],
    margin_meters: float = DEFAULT_BBOX_MARGIN_METERS,
) -> BoundingBox:
    """Create a bounding box from sensor coordinates with a configurable margin."""

    if not sensors:
        raise ValueError("At least one sensor is required to derive a bounding box.")
    if margin_meters < 0:
        raise ValueError("margin_meters cannot be negative.")

    min_latitude = min(sensor.latitude for sensor in sensors)
    max_latitude = max(sensor.latitude for sensor in sensors)
    min_longitude = min(sensor.longitude for sensor in sensors)
    max_longitude = max(sensor.longitude for sensor in sensors)

    center_latitude = (min_latitude + max_latitude) / 2
    margin_latitude = meters_to_latitude_degrees(max(margin_meters, 0.001))
    margin_longitude = meters_to_longitude_degrees(max(margin_meters, 0.001), center_latitude)

    return BoundingBox(
        min_latitude=min_latitude - margin_latitude,
        min_longitude=min_longitude - margin_longitude,
        max_latitude=max_latitude + margin_latitude,
        max_longitude=max_longitude + margin_longitude,
    )


def build_grid_cells(
    bounding_box: BoundingBox,
    grid_size_meters: float,
    include_bounds: bool = True,
) -> list[GridCell]:
    """Generate row-major regular grid cells over the bounding box."""

    validate_grid_size_meters(grid_size_meters)

    center_latitude = (bounding_box.min_latitude + bounding_box.max_latitude) / 2
    lat_step = meters_to_latitude_degrees(grid_size_meters)
    lon_step = meters_to_longitude_degrees(grid_size_meters, center_latitude)

    latitude_span = bounding_box.max_latitude - bounding_box.min_latitude
    longitude_span = bounding_box.max_longitude - bounding_box.min_longitude

    row_count = max(1, math.ceil(latitude_span / lat_step))
    col_count = max(1, math.ceil(longitude_span / lon_step))

    cells: list[GridCell] = []
    for row in range(row_count):
        cell_min_latitude = bounding_box.min_latitude + (row * lat_step)
        cell_max_latitude = min(cell_min_latitude + lat_step, bounding_box.max_latitude)
        center_lat = (cell_min_latitude + cell_max_latitude) / 2

        for col in range(col_count):
            cell_min_longitude = bounding_box.min_longitude + (col * lon_step)
            cell_max_longitude = min(cell_min_longitude + lon_step, bounding_box.max_longitude)
            center_lon = (cell_min_longitude + cell_max_longitude) / 2

            cells.append(
                GridCell(
                    row=row,
                    col=col,
                    latitude=center_lat,
                    longitude=center_lon,
                    min_latitude=cell_min_latitude if include_bounds else None,
                    min_longitude=cell_min_longitude if include_bounds else None,
                    max_latitude=cell_max_latitude if include_bounds else None,
                    max_longitude=cell_max_longitude if include_bounds else None,
                )
            )

    return cells


def build_grid_from_sensors(
    sensors: Sequence[HasCoordinates],
    grid_size_meters: float,
    margin_meters: float = DEFAULT_BBOX_MARGIN_METERS,
    include_bounds: bool = True,
) -> tuple[BoundingBox, list[GridCell]]:
    """Derive bbox from sensors and generate a regular grid."""

    bounding_box = derive_bbox_from_sensors(sensors=sensors, margin_meters=margin_meters)
    return bounding_box, build_grid_cells(
        bounding_box=bounding_box,
        grid_size_meters=grid_size_meters,
        include_bounds=include_bounds,
    )
