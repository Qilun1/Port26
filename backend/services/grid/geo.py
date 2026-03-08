import math

EARTH_RADIUS_METERS = 6_371_000.0
METERS_PER_DEGREE_LATITUDE = 111_320.0
MIN_COSINE_LATITUDE = 0.01


def meters_to_latitude_degrees(meters: float) -> float:
    """Convert north/south meter distance to latitude degree delta."""

    if meters <= 0:
        raise ValueError("meters must be greater than zero.")
    return meters / METERS_PER_DEGREE_LATITUDE


def meters_to_longitude_degrees(meters: float, at_latitude: float) -> float:
    """Convert east/west meter distance to longitude degree delta at a latitude."""

    if meters <= 0:
        raise ValueError("meters must be greater than zero.")

    latitude_radians = math.radians(at_latitude)
    meters_per_degree = METERS_PER_DEGREE_LATITUDE * max(
        MIN_COSINE_LATITUDE,
        abs(math.cos(latitude_radians)),
    )
    return meters / meters_per_degree


def approximate_distance_meters(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Approximate local distance using equirectangular projection.

    The approximation is stable and accurate enough for city-scale interpolation.
    """

    lat_a_radians = math.radians(latitude_a)
    lat_b_radians = math.radians(latitude_b)
    delta_lat = lat_b_radians - lat_a_radians
    delta_lon = math.radians(longitude_b - longitude_a)

    x = delta_lon * math.cos((lat_a_radians + lat_b_radians) / 2)
    y = delta_lat
    return math.sqrt((x * x) + (y * y)) * EARTH_RADIUS_METERS
