from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import cast

import numpy as np
import pandas as pd
import xarray as xr

from sim.common import (
    add_time_features,
    apply_normalization,
    build_leave_one_out_idw,
    coerce_pressure_to_hpa,
    convert_fmi_station_pressure_to_surface,
    compute_dem_slope,
    compute_normalization,
    ensure_columns,
    ensure_directories,
    pm25_to_aqi,
    raster_points,
    read_dem_raster,
    sample_raster_values,
    save_json,
    standardize_cams_dataset,
    standardize_era5_dataset,
    station_feature_columns,
    wind_speed_direction_to_uv,
)
from sim.data_in.fmi_fetcher import open_aligned_silam
from sim.config import SimulationConfig, load_config


TARGET_BASELINES = {
    "temperature": "coarse_temperature",
    "pressure": "coarse_pressure",
    "pm25": "coarse_pm25",
    "aqi": "coarse_aqi",
    "u10": "coarse_u10",
    "v10": "coarse_v10",
}


def _requires_pm_targets(config: SimulationConfig) -> bool:
    return any(target in {"pm25", "aqi"} for target in config.model.targets)

HOURLY_NETCDF_RE = re.compile(r".*_\d{8}T\d{4}Z\.nc$")


def _open_combined_dataset(files: list[Path]) -> xr.Dataset:
    datasets = [xr.open_dataset(path) for path in files]
    try:
        return cast(xr.Dataset, xr.combine_by_coords(datasets, combine_attrs="drop_conflicts").load())
    finally:
        for dataset in datasets:
            dataset.close()


def _hourly_netcdf_files(directory: Path) -> list[Path]:
    return sorted(path for path in directory.glob("*.nc") if HOURLY_NETCDF_RE.match(path.name))


def _load_era5(config: SimulationConfig) -> xr.Dataset:
    files = _hourly_netcdf_files(config.paths.training_data / "era5_land")
    if not files:
        raise FileNotFoundError("No ERA5-Land files found. Run sim.data_in.download_training_data first.")
    dataset = _open_combined_dataset(files)
    return standardize_era5_dataset(dataset)


def _load_cams(config: SimulationConfig) -> xr.Dataset | None:
    files = _hourly_netcdf_files(config.paths.training_data / "cams_europe")
    if not files:
        return None
    dataset = _open_combined_dataset(files)
    return standardize_cams_dataset(dataset)


def _load_silam_pm25(config: SimulationConfig) -> xr.Dataset:
    silam_path = config.paths.training_data / "fmi" / "silam" / "silam_pm25_aligned.nc"
    if not silam_path.exists():
        raise FileNotFoundError("No aligned SILAM PM2.5 file found. Run sim.data_in.download_training_data first.")
    return open_aligned_silam(silam_path, config.bbox)


def _load_fmi(config: SimulationConfig) -> pd.DataFrame:
    observations = pd.read_parquet(config.paths.training_data / "fmi" / "observations.parquet")
    observations["timestamp"] = pd.to_datetime(observations["timestamp"], utc=True)
    observations["pressure"] = coerce_pressure_to_hpa(observations["pressure"])
    if "wind_speed" in observations and "wind_direction" in observations:
        station_u10, station_v10 = wind_speed_direction_to_uv(
            observations["wind_speed"],
            observations["wind_direction"],
        )
        observations["station_u10"] = station_u10
        observations["station_v10"] = station_v10
        observations["u10"] = station_u10
        observations["v10"] = station_v10
    return ensure_columns(observations, ["station_u10", "station_v10", "u10", "v10"])


def _sample_era5_at_stations(stations: pd.DataFrame, coarse: xr.Dataset) -> pd.DataFrame:
    sampled = coarse[[name for name in coarse.data_vars]].sel(
        time=xr.DataArray(pd.to_datetime(stations["timestamp"]).dt.tz_localize(None).to_numpy(), dims="sample"),
        latitude=xr.DataArray(stations["latitude"].to_numpy(), dims="sample"),
        longitude=xr.DataArray(stations["longitude"].to_numpy(), dims="sample"),
        method="nearest",
    )
    sampled_df = sampled.to_dataframe().reset_index(drop=True)
    sampled_df = sampled_df.rename(columns={"latitude": "coarse_latitude", "longitude": "coarse_longitude"})
    return pd.concat([stations.reset_index(drop=True), sampled_df], axis=1)


def _sample_dataset_at_stations(
    stations: pd.DataFrame,
    dataset: xr.Dataset,
    variable_names: list[str],
    time_column: str = "timestamp",
) -> pd.DataFrame:
    sampled = dataset[variable_names].sel(
        time=xr.DataArray(pd.to_datetime(stations[time_column]).dt.tz_localize(None).to_numpy(), dims="sample"),
        latitude=xr.DataArray(stations["latitude"].to_numpy(), dims="sample"),
        longitude=xr.DataArray(stations["longitude"].to_numpy(), dims="sample"),
        method="nearest",
    )
    return sampled.to_dataframe().reset_index(drop=True)[variable_names]


def _sample_silam_at_stations(stations: pd.DataFrame, silam: xr.Dataset) -> pd.DataFrame:
    sampled = silam[["silam_pm25"]].sel(
        time=xr.DataArray(pd.to_datetime(stations["timestamp"]).dt.tz_localize(None).to_numpy(), dims="sample"),
        latitude=xr.DataArray(stations["latitude"].to_numpy(), dims="sample"),
        longitude=xr.DataArray(stations["longitude"].to_numpy(), dims="sample"),
        method="nearest",
    )
    return sampled.to_dataframe().reset_index(drop=True).rename(columns={"silam_pm25": "coarse_pm25"})[["coarse_pm25"]]


def _prepare_station_samples(
    config: SimulationConfig,
    coarse: xr.Dataset,
    cams: xr.Dataset | None,
    silam_pm25: xr.Dataset | None,
    dem: np.ndarray,
    transform,
) -> pd.DataFrame:
    stations = _load_fmi(config)
    stations = stations.loc[
        (stations["longitude"] >= config.bbox.min_lon)
        & (stations["longitude"] <= config.bbox.max_lon)
        & (stations["latitude"] >= config.bbox.min_lat)
        & (stations["latitude"] <= config.bbox.max_lat)
    ].reset_index(drop=True)
    prefixes = config.filters.station_name_prefixes
    if prefixes and "station_name" in stations.columns:
        stations = stations.loc[
            stations["station_name"].fillna("").astype(str).map(
                lambda name: any(name.startswith(prefix) for prefix in prefixes)
            )
        ].reset_index(drop=True)
    stations = _sample_era5_at_stations(stations, coarse)
    if cams is not None:
        cams_feature_names = [
            str(name)
            for name in cams.data_vars
            if str(name).startswith("coarse_") and str(name) != "coarse_pm25"
        ]
        if cams_feature_names:
            stations = pd.concat(
                [
                    stations.reset_index(drop=True),
                    _sample_dataset_at_stations(
                        stations,
                        cams,
                        cams_feature_names,
                    ),
                ],
                axis=1,
            )
    if silam_pm25 is not None:
        stations = pd.concat(
            [
                stations.reset_index(drop=True),
                _sample_silam_at_stations(stations, silam_pm25),
            ],
            axis=1,
        )
    stations = ensure_columns(
        stations,
        ["coarse_pm25", "coarse_no2", "coarse_o3", "coarse_so2"],
    )
    stations["coarse_aqi"] = pm25_to_aqi(stations["coarse_pm25"])

    stations["dem_elevation"] = sample_raster_values(
        dem,
        transform,
        stations["longitude"].to_numpy(),
        stations["latitude"].to_numpy(),
    )
    if "pressure" in stations.columns:
        stations = convert_fmi_station_pressure_to_surface(stations)
    stations["coarse_elevation"] = sample_raster_values(
        dem,
        transform,
        stations["coarse_longitude"].to_numpy(),
        stations["coarse_latitude"].to_numpy(),
    )

    slope = compute_dem_slope(dem, transform)
    stations["dem_slope"] = sample_raster_values(
        slope,
        transform,
        stations["longitude"].to_numpy(),
        stations["latitude"].to_numpy(),
    )
    stations["elevation_delta"] = stations["dem_elevation"] - stations["coarse_elevation"]
    stations = add_time_features(stations)
    idw_value_columns = list(dict.fromkeys(config.model.targets + ["station_u10", "station_v10"]))
    stations = build_leave_one_out_idw(
        stations,
        value_columns=idw_value_columns,
        timestamp_column="timestamp",
        k=config.preprocess.idw_k,
        power=config.preprocess.idw_power,
        min_station_neighbors=config.preprocess.min_station_neighbors,
    )

    for target, baseline in TARGET_BASELINES.items():
        if target not in stations:
            stations[target] = np.nan
        valid_mask = stations[target].notna() & stations[baseline].notna()
        stations[f"residual_{target}"] = np.where(
            valid_mask,
            stations[target] - stations[baseline],
            np.nan,
        )

    if config.preprocess.dropna_targets:
        target_columns = [f"residual_{target}" for target in config.model.targets]
        stations = stations.dropna(subset=target_columns, how="all")

    return ensure_columns(stations, station_feature_columns(config.model.targets))


def _build_dem_grid(config: SimulationConfig, dem: np.ndarray, transform) -> pd.DataFrame:
    slope = compute_dem_slope(dem, transform)
    grid = raster_points(transform, dem.shape[0], dem.shape[1], stride=config.preprocess.grid_stride)
    grid = grid.loc[
        (grid["longitude"] >= config.bbox.min_lon)
        & (grid["longitude"] <= config.bbox.max_lon)
        & (grid["latitude"] >= config.bbox.min_lat)
        & (grid["latitude"] <= config.bbox.max_lat)
    ].reset_index(drop=True)
    grid["dem_elevation"] = sample_raster_values(
        dem,
        transform,
        grid["longitude"].to_numpy(),
        grid["latitude"].to_numpy(),
    )
    grid["dem_slope"] = sample_raster_values(
        slope,
        transform,
        grid["longitude"].to_numpy(),
        grid["latitude"].to_numpy(),
    )
    return grid


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess downloaded training data for downscaling.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    args = parser.parse_args()

    config = load_config(args.config)
    ensure_directories(config.paths.processed)
    print("Loading ERA5-Land hourly files...", flush=True)
    coarse = _load_era5(config)
    cams = None
    if _requires_pm_targets(config):
        print("Loading CAMS Europe hourly files...", flush=True)
        cams = _load_cams(config)
    if _requires_pm_targets(config):
        print("Loading aligned SILAM PM2.5...", flush=True)
    silam_pm25 = _load_silam_pm25(config) if _requires_pm_targets(config) else None
    print("Loading DEM raster...", flush=True)
    dem, transform, _ = read_dem_raster(config.paths.training_data / "dem" / "cop_dem_30m.tif")
    print("Preparing station samples and IDW features...", flush=True)
    station_samples = _prepare_station_samples(config, coarse, cams, silam_pm25, dem, transform)
    print("Building DEM grid template...", flush=True)
    grid_template = _build_dem_grid(config, dem, transform)

    feature_columns = station_feature_columns(config.model.targets)
    print("Computing normalization statistics...", flush=True)
    normalization_stats = compute_normalization(station_samples, feature_columns)
    normalized_station_samples = apply_normalization(station_samples, normalization_stats, feature_columns)

    station_target = config.paths.processed / "station_training.parquet"
    raw_station_target = config.paths.processed / "station_training_raw.parquet"
    grid_target = config.paths.processed / "dem_grid.parquet"
    metadata_target = config.paths.processed / "metadata.json"
    stats_target = config.paths.processed / "normalization.json"

    normalized_station_samples.to_parquet(station_target, index=False)
    station_samples.to_parquet(raw_station_target, index=False)
    grid_template.to_parquet(grid_target, index=False)
    save_json(normalization_stats, stats_target)
    save_json(
        {
            "feature_columns": feature_columns,
            "targets": config.model.targets,
            "grid_stride": config.preprocess.grid_stride,
            "target_baselines": {target: TARGET_BASELINES[target] for target in config.model.targets},
            "raw_training_path": str(raw_station_target),
            "normalized_training_path": str(station_target),
        },
        metadata_target,
    )
    print("Preprocessing complete.", flush=True)


if __name__ == "__main__":
    main()