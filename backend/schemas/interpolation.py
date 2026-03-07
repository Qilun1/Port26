from datetime import date, datetime
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


class InterpolationMaskedGridResponse(BaseModel):
    metric: InterpolationMetric
    rows: int = Field(ge=0)
    cols: int = Field(ge=0)
    bbox: InterpolationBoundingBox
    cell_size_m: float = Field(gt=0)
    values: list[float | None]
    mask: list[int]

    @model_validator(mode="after")
    def validate_matrix(self) -> "InterpolationMaskedGridResponse":
        expected_length = self.rows * self.cols
        if len(self.values) != expected_length:
            raise ValueError("values length must equal rows * cols.")
        if len(self.mask) != expected_length:
            raise ValueError("mask length must equal rows * cols.")

        for index, cell_mask in enumerate(self.mask):
            if cell_mask not in (0, 1):
                raise ValueError("mask entries must be 0 or 1.")
            if cell_mask == 0 and self.values[index] is not None:
                raise ValueError("uncovered cells (mask=0) must have null value.")

        return self


class InterpolationTimelineFrame(BaseModel):
    timestamp: datetime
    values: list[float]


class InterpolationTimelineResponse(BaseModel):
    metric: InterpolationMetric
    date: date
    grid_size_meters: float = Field(gt=0)
    rows: int = Field(ge=0)
    cols: int = Field(ge=0)
    bounding_box: InterpolationBoundingBox
    active_indices: list[int]
    timestamps: list[datetime]
    frames: list[InterpolationTimelineFrame]

    @model_validator(mode="after")
    def validate_timeline(self) -> "InterpolationTimelineResponse":
        expected_grid_length = self.rows * self.cols

        if len(self.timestamps) != len(self.frames):
            raise ValueError("timestamps length must equal frames length.")

        if not self.active_indices:
            raise ValueError("active_indices cannot be empty.")

        previous_index = -1
        for index in self.active_indices:
            if index < 0 or index >= expected_grid_length:
                raise ValueError("active_indices entries must be valid row-major indexes.")
            if index <= previous_index:
                raise ValueError("active_indices must be strictly increasing.")
            previous_index = index

        expected_frame_length = len(self.active_indices)

        for index, frame in enumerate(self.frames):
            if len(frame.values) != expected_frame_length:
                raise ValueError("each frame values length must equal active_indices length.")
            if frame.timestamp != self.timestamps[index]:
                raise ValueError("frame timestamps must match top-level timestamps order.")

        return self


class TimestepMetricItem(BaseModel):
    timestamp_utc: datetime
    avg_aqi: float | None
    avg_temperature_c: float | None
    sensor_count_aqi: int = Field(ge=0)
    sensor_count_temperature: int = Field(ge=0)


class TimestepMetricsResponse(BaseModel):
    date: date
    count: int = Field(ge=0)
    items: list[TimestepMetricItem]
