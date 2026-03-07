from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Latitude/longitude bounds for grid generation."""

    min_latitude: float
    min_longitude: float
    max_latitude: float
    max_longitude: float

    def __post_init__(self) -> None:
        if self.min_latitude >= self.max_latitude:
            raise ValueError("min_latitude must be smaller than max_latitude.")
        if self.min_longitude >= self.max_longitude:
            raise ValueError("min_longitude must be smaller than max_longitude.")


@dataclass(frozen=True, slots=True)
class GridCell:
    """Single regular grid cell metadata and center point."""

    row: int
    col: int
    latitude: float
    longitude: float
    min_latitude: float | None = None
    min_longitude: float | None = None
    max_latitude: float | None = None
    max_longitude: float | None = None
