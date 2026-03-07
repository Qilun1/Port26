from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config import get_settings
from schemas import (
    InterpolationBoundingBox,
    InterpolationGridQuery,
    InterpolationTimelineResponse,
    InterpolationMaskedGridResponse,
    InterpolationMetric,
)
from services import (
    GridInterpolationService,
    InterpolationTimelineLoaderService,
    InterpolationTimelineNotFoundError,
    SensorPoint,
    SensorService,
)
from services.grid import build_grid_cells, derive_bbox_from_sensors
from services.grid.models import BoundingBox

router = APIRouter(prefix="/interpolation", tags=["interpolation"])

MAX_TRANSFER_GRID_POINTS = 100_000


def get_sensor_service() -> SensorService:
    return SensorService(get_settings())


def get_interpolation_service() -> GridInterpolationService:
    return GridInterpolationService(get_settings())


def get_timeline_loader_service() -> InterpolationTimelineLoaderService:
    return InterpolationTimelineLoaderService(get_settings())


def parse_interpolation_query(
    metric: InterpolationMetric,
    grid_size_meters: float = Query(100.0, ge=50.0, le=200.0),
    min_latitude: float | None = Query(None),
    min_longitude: float | None = Query(None),
    max_latitude: float | None = Query(None),
    max_longitude: float | None = Query(None),
) -> InterpolationGridQuery:
    return InterpolationGridQuery(
        metric=metric,
        grid_size_meters=grid_size_meters,
        min_latitude=min_latitude,
        min_longitude=min_longitude,
        max_latitude=max_latitude,
        max_longitude=max_longitude,
    )


@router.get("/grid", response_model=InterpolationMaskedGridResponse)
def get_interpolated_grid(
    query: InterpolationGridQuery = Depends(parse_interpolation_query),
    sensor_service: SensorService = Depends(get_sensor_service),
    interpolation_service: GridInterpolationService = Depends(get_interpolation_service),
) -> InterpolationMaskedGridResponse:
    try:
        sensors = sensor_service.list_sensors()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch sensors from data source.",
        ) from exc

    metric_sensors: list[SensorPoint] = []
    for sensor in sensors:
        if query.metric == InterpolationMetric.temperature:
            value = sensor.latest_temperature_c
        else:
            value = sensor.latest_aqi

        if value is None:
            continue

        metric_sensors.append(
            SensorPoint(
                id=str(sensor.id),
                latitude=sensor.latitude,
                longitude=sensor.longitude,
                value=float(value),
            )
        )

    if not metric_sensors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No sensors have values for metric '{query.metric.value}'.",
        )

    try:
        if query.has_bbox:
            assert query.min_latitude is not None
            assert query.min_longitude is not None
            assert query.max_latitude is not None
            assert query.max_longitude is not None

            bounding_box = BoundingBox(
                min_latitude=query.min_latitude,
                min_longitude=query.min_longitude,
                max_latitude=query.max_latitude,
                max_longitude=query.max_longitude,
            )
        else:
            bounding_box = derive_bbox_from_sensors(metric_sensors)

        candidate_cells = build_grid_cells(
            bounding_box=bounding_box,
            grid_size_meters=query.grid_size_meters,
            include_bounds=False,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if len(candidate_cells) > MAX_TRANSFER_GRID_POINTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Requested grid is too large to transfer. "
                f"Computed {len(candidate_cells)} points, maximum is {MAX_TRANSFER_GRID_POINTS}. "
                "Increase grid_size_meters or narrow the bounding box."
            ),
        )

    interpolated_grid = interpolation_service.interpolate_masked_matrix_over_bbox(
        sensors=metric_sensors,
        bounding_box=bounding_box,
        grid_size_meters=query.grid_size_meters,
        include_bounds=False,
    )

    return InterpolationMaskedGridResponse(
        metric=query.metric,
        rows=interpolated_grid.rows,
        cols=interpolated_grid.cols,
        bbox=InterpolationBoundingBox(
            min_latitude=interpolated_grid.bounding_box.min_latitude,
            min_longitude=interpolated_grid.bounding_box.min_longitude,
            max_latitude=interpolated_grid.bounding_box.max_latitude,
            max_longitude=interpolated_grid.bounding_box.max_longitude,
        ),
        cell_size_m=query.grid_size_meters,
        values=interpolated_grid.values,
        mask=interpolated_grid.mask,
    )


@router.get("/timeline", response_model=InterpolationTimelineResponse)
def get_interpolated_timeline(
    metric: InterpolationMetric,
    date_value: date = Query(alias="date"),
    grid_size_meters: float = Query(100.0, ge=50.0, le=200.0),
    timeline_loader: InterpolationTimelineLoaderService = Depends(get_timeline_loader_service),
) -> InterpolationTimelineResponse:
    try:
        return timeline_loader.load_timeline(
            metric=metric,
            timeline_date=date_value,
            grid_size_meters=grid_size_meters,
        )
    except InterpolationTimelineNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Precomputed interpolation timeline does not exist for the requested "
                "metric/date/grid size. Generate the artifact first."
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
