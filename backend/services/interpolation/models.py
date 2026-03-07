from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SensorPoint:
    """Input sensor sample used in interpolation."""

    id: str
    latitude: float
    longitude: float
    value: float


@dataclass(frozen=True, slots=True)
class InterpolatedGridCell:
    """Output shape for interpolated regular grid cells."""

    row: int
    col: int
    latitude: float
    longitude: float
    interpolated_value: float | None
    min_latitude: float | None = None
    min_longitude: float | None = None
    max_latitude: float | None = None
    max_longitude: float | None = None
