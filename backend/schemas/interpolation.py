from enum import Enum

from pydantic import BaseModel, Field, model_validator


class InterpolationMetric(str, Enum):
    temperature = "temperature"
    aqi = "aqi"


class InterpolationGridQuery(BaseModel):
    metric: InterpolationMetric
    grid_size_meters: float = Field(ge=50.0, le=200.0)
    min_latitude: float | None = None
    min_longitude: float | None = None
    max_latitude: float | None = None
    max_longitude: float | None = None

    @model_validator(mode="after")
    def validate_bbox(self) -> "InterpolationGridQuery":
        bbox_values = (
            self.min_latitude,
            self.min_longitude,
            self.max_latitude,
            self.max_longitude,
        )
        has_any = any(value is not None for value in bbox_values)
        has_all = all(value is not None for value in bbox_values)

        if has_any and not has_all:
            raise ValueError(
                "Provide all bbox parameters together: min_latitude, min_longitude, max_latitude, max_longitude."
            )

        if has_all:
            assert self.min_latitude is not None
            assert self.min_longitude is not None
            assert self.max_latitude is not None
            assert self.max_longitude is not None

            if self.min_latitude >= self.max_latitude:
                raise ValueError("min_latitude must be smaller than max_latitude.")
            if self.min_longitude >= self.max_longitude:
                raise ValueError("min_longitude must be smaller than max_longitude.")

        return self

    @property
    def has_bbox(self) -> bool:
        return (
            self.min_latitude is not None
            and self.min_longitude is not None
            and self.max_latitude is not None
            and self.max_longitude is not None
        )


class InterpolationBoundingBox(BaseModel):
    min_latitude: float
    min_longitude: float
    max_latitude: float
    max_longitude: float


class InterpolationGridPoint(BaseModel):
    row: int
    col: int
    latitude: float
    longitude: float
    interpolated_value: float | None


class InterpolationGridResponse(BaseModel):
    metric: InterpolationMetric
    grid_size_meters: float
    count: int
    bounding_box: InterpolationBoundingBox
    points: list[InterpolationGridPoint]
