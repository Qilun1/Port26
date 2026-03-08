from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol, xy
from scipy.spatial import KDTree
import xarray as xr


ERA5_RENAME_MAP = {
    "2m_temperature": "coarse_temperature",
    "t2m": "coarse_temperature",
    "surface_pressure": "coarse_pressure",
    "sp": "coarse_pressure",
    "10m_u_component_of_wind": "coarse_u10",
    "u10": "coarse_u10",
    "10m_v_component_of_wind": "coarse_v10",
    "v10": "coarse_v10",
    "valid_time": "time",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
}


CAMS_RENAME_MAP = {
    "particulate_matter_2.5um": "coarse_pm25",
    "pm2p5": "coarse_pm25",
    "nitrogen_dioxide": "coarse_no2",
    "no2": "coarse_no2",
    "ozone": "coarse_o3",
    "o3": "coarse_o3",
    "sulphur_dioxide": "coarse_so2",
    "so2": "coarse_so2",
    "valid_time": "time",
    "latitude": "latitude",
    "lat": "latitude",
    "longitude": "longitude",
    "lon": "longitude",
}


AQI_BREAKPOINTS = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]
STANDARD_PRESSURE_SCALE_HEIGHT_M = 8434.5
STANDARD_LAPSE_RATE_C_PER_M = 0.0065
STANDARD_TEMPERATURE_K = 288.15
MIN_LAYER_TEMPERATURE_K = 180.0


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def standardize_era5_dataset(ds: xr.Dataset) -> xr.Dataset:
    rename_map = {str(name): ERA5_RENAME_MAP[str(name)] for name in ds.variables if str(name) in ERA5_RENAME_MAP}
    coord_map = {str(name): ERA5_RENAME_MAP[str(name)] for name in ds.coords if str(name) in ERA5_RENAME_MAP}
    standardized = ds.rename(rename_map | coord_map)
    if "coarse_temperature" in standardized:
        standardized["coarse_temperature"] = standardized["coarse_temperature"] - 273.15
    if "coarse_pressure" in standardized:
        standardized["coarse_pressure"] = standardized["coarse_pressure"] / 100.0
    return standardized.sortby("time")


def standardize_cams_dataset(ds: xr.Dataset) -> xr.Dataset:
    rename_map = {str(name): CAMS_RENAME_MAP[str(name)] for name in ds.variables if str(name) in CAMS_RENAME_MAP}
    coord_map = {str(name): CAMS_RENAME_MAP[str(name)] for name in ds.coords if str(name) in CAMS_RENAME_MAP}
    standardized = ds.rename(rename_map | coord_map)
    if "forecast_reference_time" in standardized.coords and "forecast_period" in standardized.coords and "time" not in standardized.coords:
        standardized = standardized.assign_coords(
            time=standardized["forecast_reference_time"] + standardized["forecast_period"]
        )
    if "time" in standardized.coords:
        standardized = standardized.sortby("time")
    return standardized


def read_dem_raster(dem_path: Path) -> tuple[np.ndarray, rasterio.Affine, dict]:
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        transform = src.transform
    return dem, transform, profile


def raster_points(transform: rasterio.Affine, height: int, width: int, stride: int = 1) -> pd.DataFrame:
    rows = np.arange(0, height, stride)
    cols = np.arange(0, width, stride)
    mesh_rows, mesh_cols = np.meshgrid(rows, cols, indexing="ij")
    xs, ys = xy(transform, mesh_rows, mesh_cols)
    return pd.DataFrame(
        {
            "row": mesh_rows.ravel(),
            "col": mesh_cols.ravel(),
            "longitude": np.asarray(xs).ravel(),
            "latitude": np.asarray(ys).ravel(),
        }
    )


def compute_dem_slope(dem: np.ndarray, transform: rasterio.Affine) -> np.ndarray:
    pixel_width_deg = abs(transform.a)
    pixel_height_deg = abs(transform.e)
    lat_scale_m = 111_320.0 * pixel_height_deg
    lon_scale_m = 111_320.0 * pixel_width_deg
    dz_dy, dz_dx = np.gradient(dem, lat_scale_m, lon_scale_m)
    return np.sqrt(dz_dx**2 + dz_dy**2).astype(np.float32)


def sample_raster_values(dem: np.ndarray, transform: rasterio.Affine, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    rows, cols = rowcol(transform, lons, lats)
    rows = np.clip(np.asarray(rows, dtype=int), 0, dem.shape[0] - 1)
    cols = np.clip(np.asarray(cols, dtype=int), 0, dem.shape[1] - 1)
    return dem[rows, cols]


def add_time_features(frame: pd.DataFrame, timestamp_column: str = "timestamp") -> pd.DataFrame:
    frame = frame.copy()
    timestamps = pd.to_datetime(frame[timestamp_column], utc=True)
    hour = timestamps.dt.hour.to_numpy()
    day_of_year = timestamps.dt.dayofyear.to_numpy()
    frame["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
    frame["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
    frame["doy_sin"] = np.sin(2.0 * np.pi * day_of_year / 366.0)
    frame["doy_cos"] = np.cos(2.0 * np.pi * day_of_year / 366.0)
    return frame


def wind_speed_direction_to_uv(
    speed: pd.Series | np.ndarray,
    direction_deg_from: pd.Series | np.ndarray,
) -> tuple[pd.Series, pd.Series]:
    speed_series = pd.Series(speed, dtype=float)
    direction_series = pd.Series(direction_deg_from, dtype=float)
    radians = np.deg2rad(direction_series)
    u_component = -speed_series * np.sin(radians)
    v_component = -speed_series * np.cos(radians)
    return u_component, v_component


def uv_to_wind_speed_direction(
    u_component: pd.Series | np.ndarray,
    v_component: pd.Series | np.ndarray,
) -> tuple[pd.Series, pd.Series]:
    u_series = pd.Series(u_component, dtype=float)
    v_series = pd.Series(v_component, dtype=float)
    speed = pd.Series(np.sqrt(u_series**2 + v_series**2), index=u_series.index, dtype=float)
    direction_deg_from = pd.Series(
        (np.degrees(np.arctan2(-u_series, -v_series)) + 360.0) % 360.0,
        index=u_series.index,
        dtype=float,
    )
    return speed, direction_deg_from


def project_lon_lat(lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    ref_lat = np.deg2rad(np.nanmean(lats))
    x = lons * np.cos(ref_lat)
    y = lats
    return np.column_stack([x, y])


def _inverse_distance_weighted(
    source_xy: np.ndarray,
    source_values: np.ndarray,
    target_xy: np.ndarray,
    k: int,
    power: float,
) -> np.ndarray:
    tree = KDTree(source_xy)
    effective_k = min(k, len(source_xy))
    distances, indices = tree.query(target_xy, k=effective_k)
    distances = np.asarray(distances)
    indices = np.asarray(indices)
    if np.ndim(distances) == 1:
        distances = distances[:, None]
        indices = indices[:, None]
    weights = 1.0 / np.maximum(distances, 1.0e-6) ** power
    weighted_values = source_values[indices] * weights
    return weighted_values.sum(axis=1) / weights.sum(axis=1)


def build_leave_one_out_idw(
    frame: pd.DataFrame,
    value_columns: list[str],
    timestamp_column: str,
    k: int,
    power: float,
    min_station_neighbors: int,
) -> pd.DataFrame:
    result = frame.copy()
    unique_columns = list(dict.fromkeys(value_columns))
    for column in unique_columns:
        result[f"idw_{column}"] = np.nan

    for _, group in result.groupby(timestamp_column, sort=False):
        group_index = group.index.to_numpy()
        coords = project_lon_lat(group["longitude"].to_numpy(), group["latitude"].to_numpy())
        query_cache: dict[bytes, tuple[np.ndarray, np.ndarray]] = {}
        for column in unique_columns:
            valid_mask = group[column].notna().to_numpy()
            if valid_mask.sum() < min_station_neighbors:
                continue
            valid_values = group.loc[valid_mask, column].to_numpy(dtype=float)
            cache_key = valid_mask.tobytes()
            if cache_key not in query_cache:
                valid_coords = coords[valid_mask]
                tree = KDTree(valid_coords)
                neighbor_count = min(k + 1, len(valid_coords))
                distances, indices = tree.query(coords, k=neighbor_count)
                distances = np.asarray(distances)
                indices = np.asarray(indices)
                if np.ndim(distances) == 1:
                    distances = distances[:, None]
                    indices = indices[:, None]
                query_cache[cache_key] = (distances, indices)

            distances, indices = query_cache[cache_key]
            if np.ndim(distances) == 1:
                distances = distances[:, None]
                indices = indices[:, None]

            usable = distances > 1.0e-9
            finite = np.isfinite(distances)
            fallback_rows = usable.sum(axis=1) < min_station_neighbors
            if np.any(fallback_rows):
                usable[fallback_rows] = finite[fallback_rows]

            weights = np.where(usable, 1.0 / np.maximum(distances, 1.0e-6) ** power, 0.0)
            weight_sums = weights.sum(axis=1)
            weighted_values = valid_values[indices] * weights
            interpolated = np.full(len(group), np.nan, dtype=float)
            nonzero = weight_sums > 0.0
            interpolated[nonzero] = weighted_values[nonzero].sum(axis=1) / weight_sums[nonzero]

            result.loc[group_index, f"idw_{column}"] = interpolated

    return result


def idw_to_grid(
    stations: pd.DataFrame,
    grid: pd.DataFrame,
    value_columns: list[str],
    k: int,
    power: float,
    min_station_neighbors: int,
) -> pd.DataFrame:
    result = grid.copy()
    station_coords = project_lon_lat(stations["longitude"].to_numpy(), stations["latitude"].to_numpy())
    grid_coords = project_lon_lat(grid["longitude"].to_numpy(), grid["latitude"].to_numpy())

    for column in value_columns:
        valid = stations[column].notna().to_numpy()
        if valid.sum() < min_station_neighbors:
            result[f"idw_{column}"] = np.nan
            continue
        result[f"idw_{column}"] = _inverse_distance_weighted(
            source_xy=station_coords[valid],
            source_values=stations.loc[valid, column].to_numpy(dtype=float),
            target_xy=grid_coords,
            k=k,
            power=power,
        )
    return result


def ensure_columns(frame: pd.DataFrame, columns: list[str], fill_value: float = np.nan) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column not in result:
            result[column] = fill_value
    return result


def compute_normalization(frame: pd.DataFrame, feature_columns: list[str]) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for column in feature_columns:
        series = frame[column].astype(float)
        mean = float(series.mean())
        std = float(series.std(ddof=0))
        stats[column] = {"mean": mean, "std": 1.0 if std == 0.0 or np.isnan(std) else std}
    return stats


def apply_normalization(frame: pd.DataFrame, stats: dict[str, dict[str, float]], feature_columns: list[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for column in feature_columns:
        normalized[column] = (normalized[column] - stats[column]["mean"]) / stats[column]["std"]
    return normalized


def save_json(payload: dict, target: Path) -> None:
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_json(target: Path) -> dict:
    return json.loads(target.read_text(encoding="utf-8"))


def station_feature_columns(targets: list[str]) -> list[str]:
    columns = [
        "coarse_temperature",
        "coarse_pressure",
        "coarse_u10",
        "coarse_v10",
        "idw_station_u10",
        "idw_station_v10",
        "dem_elevation",
        "dem_slope",
        "coarse_elevation",
        "elevation_delta",
        "hour_sin",
        "hour_cos",
        "doy_sin",
        "doy_cos",
        "latitude",
        "longitude",
    ]
    if any(target in {"pm25", "aqi"} for target in targets):
        columns.extend([
            "coarse_pm25",
            "coarse_no2",
            "coarse_o3",
            "coarse_so2",
            "coarse_aqi",
        ])
    for target in targets:
        columns.append(f"idw_{target}")
    return columns


def coerce_pressure_to_hpa(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.dropna().median() > 2_000:
        return numeric / 100.0
    return numeric


def msl_pressure_to_surface_pressure(
    pressure_hpa: pd.Series | np.ndarray,
    elevation_m: pd.Series | np.ndarray,
    temperature_c: pd.Series | np.ndarray | None = None,
    *,
    default_scale_height_m: float = STANDARD_PRESSURE_SCALE_HEIGHT_M,
    lapse_rate_c_per_m: float = STANDARD_LAPSE_RATE_C_PER_M,
) -> pd.Series:
    pressure_series = coerce_pressure_to_hpa(pd.Series(pressure_hpa, dtype=float))
    elevation_series = pd.Series(elevation_m, dtype=float)

    if temperature_c is None:
        effective_scale_height = pd.Series(default_scale_height_m, index=pressure_series.index, dtype=float)
    else:
        surface_temperature_k = pd.Series(temperature_c, dtype=float) + 273.15
        mean_layer_temperature_k = surface_temperature_k + (0.5 * lapse_rate_c_per_m * elevation_series)
        mean_layer_temperature_k = mean_layer_temperature_k.clip(lower=MIN_LAYER_TEMPERATURE_K)
        effective_scale_height = (287.05 * mean_layer_temperature_k) / 9.80665
        effective_scale_height = effective_scale_height.fillna(default_scale_height_m)

    surface_pressure = pressure_series * np.exp(-elevation_series / effective_scale_height)
    surface_pressure.loc[pressure_series.isna() | elevation_series.isna()] = np.nan
    return surface_pressure


def convert_fmi_station_pressure_to_surface(
    frame: pd.DataFrame,
    *,
    dem_path: Path | None = None,
    pressure_column: str = "pressure",
    temperature_column: str = "temperature",
    elevation_column: str = "dem_elevation",
    longitude_column: str = "longitude",
    latitude_column: str = "latitude",
    msl_backup_column: str = "pressure_msl",
) -> pd.DataFrame:
    if pressure_column not in frame.columns:
        return frame.copy()

    result = frame.copy()
    pressure_hpa = coerce_pressure_to_hpa(result[pressure_column])

    if elevation_column in result.columns:
        elevation_m = pd.to_numeric(result[elevation_column], errors="coerce")
    else:
        if dem_path is None:
            raise ValueError("DEM path is required when FMI station data has no elevation column.")
        if longitude_column not in result.columns or latitude_column not in result.columns:
            raise ValueError("FMI station data must contain longitude and latitude columns for DEM sampling.")
        dem, transform, _ = read_dem_raster(dem_path)
        elevation_values = sample_raster_values(
            dem,
            transform,
            result[longitude_column].to_numpy(dtype=float),
            result[latitude_column].to_numpy(dtype=float),
        )
        elevation_m = pd.Series(elevation_values, index=result.index, dtype=float)
        result[elevation_column] = elevation_m

    if msl_backup_column not in result.columns:
        result[msl_backup_column] = pressure_hpa

    temperatures = result[temperature_column] if temperature_column in result.columns else None
    result[pressure_column] = msl_pressure_to_surface_pressure(
        pressure_hpa=pressure_hpa,
        elevation_m=elevation_m,
        temperature_c=temperatures,
    )
    return result


def fix_fmi_station_pressure_file(
    station_path: Path,
    dem_path: Path,
    output_path: Path | None = None,
) -> Path:
    destination = output_path or station_path.with_name(f"{station_path.stem}_surface_pressure{station_path.suffix}")
    if station_path.suffix == ".parquet":
        frame = pd.read_parquet(station_path)
    else:
        frame = pd.read_csv(station_path)

    fixed = convert_fmi_station_pressure_to_surface(frame, dem_path=dem_path)

    if destination.suffix == ".parquet":
        fixed.to_parquet(destination, index=False)
    else:
        fixed.to_csv(destination, index=False)
    return destination


def pm25_to_aqi(values: pd.Series | np.ndarray) -> pd.Series:
    series = pd.Series(values, dtype=float)
    aqi = pd.Series(np.nan, index=series.index, dtype=float)
    for conc_low, conc_high, aqi_low, aqi_high in AQI_BREAKPOINTS:
        mask = series.between(conc_low, conc_high, inclusive="both")
        if not mask.any():
            continue
        slope = (aqi_high - aqi_low) / (conc_high - conc_low)
        aqi.loc[mask] = (series.loc[mask] - conc_low) * slope + aqi_low
    aqi.loc[series > AQI_BREAKPOINTS[-1][1]] = 500.0
    return aqi


def config_to_metadata(config: dict) -> dict:
    return json.loads(json.dumps(config))