from typing import Sequence

from services.grid.geo import approximate_distance_meters

from .models import SensorPoint

DEFAULT_IDW_POWER = 2.0
DISTANCE_EPSILON_METERS = 1.0
DEFAULT_MAX_NEIGHBORS: int | None = None


def interpolate_idw_point(
    latitude: float,
    longitude: float,
    sensors: Sequence[SensorPoint],
    power: float = DEFAULT_IDW_POWER,
    distance_epsilon_meters: float = DISTANCE_EPSILON_METERS,
    max_neighbors: int | None = DEFAULT_MAX_NEIGHBORS,
) -> float | None:
    """Interpolate one point from sensor values using inverse-distance weighting."""

    if power <= 0:
        raise ValueError("power must be greater than zero.")
    if distance_epsilon_meters <= 0:
        raise ValueError("distance_epsilon_meters must be greater than zero.")
    if max_neighbors is not None and max_neighbors <= 0:
        raise ValueError("max_neighbors must be positive when provided.")

    if not sensors:
        return None

    distance_value_pairs: list[tuple[float, float]] = []
    for sensor in sensors:
        distance_meters = approximate_distance_meters(
            latitude,
            longitude,
            sensor.latitude,
            sensor.longitude,
        )

        if distance_meters <= distance_epsilon_meters:
            return sensor.value

        distance_value_pairs.append((distance_meters, sensor.value))

    distance_value_pairs.sort(key=lambda pair: pair[0])
    if max_neighbors is not None:
        distance_value_pairs = distance_value_pairs[:max_neighbors]

    weighted_sum = 0.0
    weight_total = 0.0
    for distance_meters, value in distance_value_pairs:
        weight = 1.0 / (distance_meters**power)
        weighted_sum += value * weight
        weight_total += weight

    if weight_total == 0:
        return None

    return weighted_sum / weight_total
