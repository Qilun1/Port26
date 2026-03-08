from services.grid.models import BoundingBox
from services.interpolation.idw import (
    LOCAL_COVERAGE_RADIUS_METERS,
    interpolate_local_idw_point,
)
from services.interpolation.models import SensorPoint
from services.interpolation.service import GridInterpolationService


def test_exact_match_returns_exact_value_and_covered() -> None:
    sensors = [SensorPoint(id="s1", latitude=60.1700, longitude=24.9400, value=12.5)]

    value, covered = interpolate_local_idw_point(
        latitude=60.1700,
        longitude=24.9400,
        sensors=sensors,
    )

    assert covered is True
    assert value == 12.5


def test_no_nearby_sensors_returns_uncovered() -> None:
    sensors = [SensorPoint(id="far", latitude=60.1700, longitude=24.9700, value=99.0)]

    value, covered = interpolate_local_idw_point(
        latitude=60.1700,
        longitude=24.9400,
        sensors=sensors,
    )

    assert covered is False
    assert value is None


def test_one_nearby_sensor_returns_direct_value() -> None:
    sensors = [
        SensorPoint(id="near", latitude=60.1700, longitude=24.9440, value=7.25),
        SensorPoint(id="far", latitude=60.1700, longitude=24.9800, value=1000.0),
    ]

    value, covered = interpolate_local_idw_point(
        latitude=60.1700,
        longitude=24.9400,
        sensors=sensors,
    )

    assert covered is True
    assert value == 7.25


def test_multiple_nearby_sensors_use_local_idw_only() -> None:
    sensors = [
        SensorPoint(id="a", latitude=60.1700, longitude=24.9430, value=10.0),
        SensorPoint(id="b", latitude=60.1700, longitude=24.9440, value=20.0),
        SensorPoint(id="far_extreme", latitude=60.1700, longitude=24.9800, value=10_000.0),
    ]

    value, covered = interpolate_local_idw_point(
        latitude=60.1700,
        longitude=24.9400,
        sensors=sensors,
    )

    assert covered is True
    assert value is not None
    assert 10.0 <= value <= 20.0


def test_matrix_output_has_values_mask_and_consistent_shape() -> None:
    service = GridInterpolationService(settings=object())
    bounding_box = BoundingBox(
        min_latitude=60.1700,
        min_longitude=24.9400,
        max_latitude=60.1704,
        max_longitude=24.9404,
    )

    sensors = [
        SensorPoint(id="far", latitude=60.1700, longitude=24.9800, value=5.0),
    ]

    matrix = service.interpolate_masked_matrix_over_bbox(
        sensors=sensors,
        bounding_box=bounding_box,
        grid_size_meters=100.0,
    )

    assert matrix.rows == 1
    assert matrix.cols == 1
    assert len(matrix.values) == matrix.rows * matrix.cols
    assert len(matrix.mask) == matrix.rows * matrix.cols
    assert matrix.mask[0] in (0, 1)
    if matrix.mask[0] == 0:
        assert matrix.values[0] is None


def test_coverage_radius_constant_is_1000m() -> None:
    assert LOCAL_COVERAGE_RADIUS_METERS == 1000.0
