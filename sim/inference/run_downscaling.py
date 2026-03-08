from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import KDTree
import xgboost as xgb
import xarray as xr

from sim.common import (
    add_time_features,
    apply_normalization,
    coerce_pressure_to_hpa,
    compute_dem_slope,
    convert_fmi_station_pressure_to_surface,
    ensure_columns,
    ensure_directories,
    idw_to_grid,
    pm25_to_aqi,
    raster_points,
    read_dem_raster,
    read_json,
    sample_raster_values,
    standardize_cams_dataset,
    standardize_era5_dataset,
    uv_to_wind_speed_direction,
    wind_speed_direction_to_uv,
)
from sim.data_in.fmi_fetcher import open_aligned_silam
from sim.config import SimulationConfig, load_config


INPUT_ALIASES = {
    "lat": "latitude",
    "lon": "longitude",
    "t2m": "temperature",
    "sp": "pressure",
    "u10": "coarse_u10",
    "v10": "coarse_v10",
    "wind_u": "station_u10",
    "wind_v": "station_v10",
}

COARSE_OUTPUT_COLUMNS = {
    "timestamp",
    "latitude",
    "longitude",
    "coarse_temperature",
    "coarse_pressure",
    "coarse_u10",
    "coarse_v10",
    "coarse_pm25",
    "coarse_no2",
    "coarse_o3",
    "coarse_so2",
    "coarse_aqi",
}


def _load_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    return frame.rename(columns={key: value for key, value in INPUT_ALIASES.items() if key in frame.columns})


def _load_current_coarse(path: Path, latest_only: bool = True) -> pd.DataFrame:
    if path.suffix == ".nc":
        dataset = standardize_cams_dataset(standardize_era5_dataset(xr.open_dataset(path)))
        if latest_only and "time" in dataset.coords:
            dataset = dataset.isel(time=-1)
        frame = dataset.to_dataframe().reset_index()
    else:
        frame = _load_table(path)

    if "time" in frame.columns and "timestamp" not in frame.columns:
        frame = frame.rename(columns={"time": "timestamp"})
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        if latest_only:
            latest_time = frame["timestamp"].max()
            frame = frame.loc[frame["timestamp"] == latest_time].copy()

    if "silam_pm25" in frame.columns and "coarse_pm25" in frame.columns:
        frame = frame.drop(columns=["coarse_pm25"])

    frame = frame.rename(columns={
        "temperature": "coarse_temperature",
        "pressure": "coarse_pressure",
        "pm25": "coarse_pm25",
        "silam_pm25": "coarse_pm25",
        "aqi": "coarse_aqi",
        "no2": "coarse_no2",
        "o3": "coarse_o3",
        "so2": "coarse_so2",
    })
    if "coarse_pressure" in frame:
        frame["coarse_pressure"] = coerce_pressure_to_hpa(frame["coarse_pressure"])
    frame = ensure_columns(frame, ["coarse_pm25", "coarse_no2", "coarse_o3", "coarse_so2", "coarse_aqi"])
    if frame["coarse_aqi"].isna().all() and frame["coarse_pm25"].notna().any():
        frame["coarse_aqi"] = pm25_to_aqi(frame["coarse_pm25"])
    return frame[[column for column in frame.columns if column in COARSE_OUTPUT_COLUMNS]]


def _sample_coarse_to_grid(grid: pd.DataFrame, coarse: pd.DataFrame) -> pd.DataFrame:
    required_columns = [
        column
        for column in ["coarse_temperature", "coarse_pressure", "coarse_u10", "coarse_v10", "coarse_pm25", "coarse_aqi"]
        if column in coarse.columns
    ]
    coarse = coarse.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
    if required_columns:
        valid_coarse = coarse.dropna(subset=required_columns, how="all").reset_index(drop=True)
        if not valid_coarse.empty:
            coarse = valid_coarse
    coarse_tree = KDTree(np.column_stack([coarse["longitude"].to_numpy(), coarse["latitude"].to_numpy()]))
    _, indices = coarse_tree.query(np.column_stack([grid["longitude"].to_numpy(), grid["latitude"].to_numpy()]), k=1)
    sampled = coarse.iloc[np.asarray(indices)].reset_index(drop=True)
    sampled = sampled.add_prefix("sampled_")
    sampled = sampled.rename(columns={
        "sampled_coarse_temperature": "coarse_temperature",
        "sampled_coarse_pressure": "coarse_pressure",
        "sampled_coarse_u10": "coarse_u10",
        "sampled_coarse_v10": "coarse_v10",
        "sampled_coarse_pm25": "coarse_pm25",
        "sampled_coarse_no2": "coarse_no2",
        "sampled_coarse_o3": "coarse_o3",
        "sampled_coarse_so2": "coarse_so2",
        "sampled_coarse_aqi": "coarse_aqi",
        "sampled_latitude": "coarse_latitude",
        "sampled_longitude": "coarse_longitude",
    })
    return pd.concat([grid.reset_index(drop=True), sampled], axis=1)


def _load_current_stations(path: Path, latest_only: bool = True, dem_path: Path | None = None) -> pd.DataFrame:
    frame = _load_table(path)
    if "pressure" in frame:
        if dem_path is not None or "dem_elevation" in frame.columns:
            frame = convert_fmi_station_pressure_to_surface(frame, dem_path=dem_path)
        else:
            frame["pressure"] = coerce_pressure_to_hpa(frame["pressure"])
    if "station_u10" not in frame.columns or "station_v10" not in frame.columns:
        if "wind_speed" in frame.columns and "wind_direction" in frame.columns:
            station_u10, station_v10 = wind_speed_direction_to_uv(frame["wind_speed"], frame["wind_direction"])
            frame["station_u10"] = station_u10
            frame["station_v10"] = station_v10
    if "station_u10" in frame.columns and "station_v10" in frame.columns:
        frame["u10"] = frame["station_u10"]
        frame["v10"] = frame["station_v10"]
    frame = ensure_columns(frame, ["station_u10", "station_v10", "u10", "v10"])
    if "timestamp" not in frame:
        raise ValueError("Current station input must contain a timestamp column.")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if latest_only:
        latest_time = frame["timestamp"].max()
        frame = frame.loc[frame["timestamp"] == latest_time].copy()
    return frame


def _prepare_grid(config: SimulationConfig, stations: pd.DataFrame, coarse: pd.DataFrame) -> pd.DataFrame:
    dem, transform, _ = read_dem_raster(config.inference.dem_file)
    slope = compute_dem_slope(dem, transform)
    grid = raster_points(transform, dem.shape[0], dem.shape[1], stride=config.preprocess.grid_stride)
    grid["dem_elevation"] = sample_raster_values(dem, transform, grid["longitude"].to_numpy(), grid["latitude"].to_numpy())
    grid["dem_slope"] = sample_raster_values(slope, transform, grid["longitude"].to_numpy(), grid["latitude"].to_numpy())
    grid = _sample_coarse_to_grid(grid, coarse)
    grid["coarse_elevation"] = sample_raster_values(
        dem,
        transform,
        grid["coarse_longitude"].to_numpy(),
        grid["coarse_latitude"].to_numpy(),
    )
    grid["elevation_delta"] = grid["dem_elevation"] - grid["coarse_elevation"]
    grid["timestamp"] = stations["timestamp"].iloc[0]
    grid = add_time_features(grid)

    silam_path = config.paths.training_data / "fmi" / "silam" / "silam_pm25_aligned.nc"
    if silam_path.exists():
        silam = open_aligned_silam(silam_path, config.bbox)
        silam_sample = silam[["silam_pm25"]].sel(
            time=xr.DataArray(pd.to_datetime(grid["timestamp"]).dt.tz_localize(None).to_numpy(), dims="sample"),
            latitude=xr.DataArray(grid["latitude"].to_numpy(), dims="sample"),
            longitude=xr.DataArray(grid["longitude"].to_numpy(), dims="sample"),
            method="nearest",
        )
        silam_values = silam_sample.to_dataframe().reset_index(drop=True)["silam_pm25"]
        if grid["coarse_pm25"].isna().all():
            grid["coarse_pm25"] = silam_values

    grid = ensure_columns(grid, ["coarse_pm25", "coarse_no2", "coarse_o3", "coarse_so2", "coarse_aqi"])
    if grid["coarse_aqi"].isna().all() and grid["coarse_pm25"].notna().any():
        grid["coarse_aqi"] = pm25_to_aqi(grid["coarse_pm25"])
    grid = idw_to_grid(
        stations,
        grid,
        value_columns=config.model.targets + ["station_u10", "station_v10"],
        k=config.preprocess.idw_k,
        power=config.preprocess.idw_power,
        min_station_neighbors=config.preprocess.min_station_neighbors,
    )
    return grid


def _predict_target(grid: pd.DataFrame, model_path: Path, feature_columns: list[str]) -> np.ndarray:
    booster = xgb.Booster()
    booster.load_model(model_path)
    matrix = xgb.DMatrix(grid[feature_columns])
    return booster.predict(matrix)


def _load_target_models(config: SimulationConfig, targets: list[str]) -> dict[str, xgb.Booster]:
    models: dict[str, xgb.Booster] = {}
    for target in targets:
        model_path = config.paths.model_registry / f"{target}.json"
        if not model_path.exists():
            continue
        booster = xgb.Booster()
        booster.load_model(model_path)
        models[target] = booster
    return models


def _predict_target_with_model(grid: pd.DataFrame, booster: xgb.Booster, feature_columns: list[str]) -> np.ndarray:
    matrix = xgb.DMatrix(grid[feature_columns])
    return booster.predict(matrix)


def _predict_with_iteration_limit(
    booster: xgb.Booster,
    matrix: xgb.DMatrix,
    best_iteration: int | None,
) -> np.ndarray:
    if best_iteration is None or best_iteration < 0:
        return booster.predict(matrix)
    return booster.predict(matrix, iteration_range=(0, best_iteration + 1))


def _registry_best_iterations(registry: dict) -> dict[str, int | None]:
    best_iterations: dict[str, int | None] = {}
    for metric in registry.get("metrics", []):
        target = metric.get("target")
        if not target:
            continue
        raw_best_iteration = metric.get("best_iteration")
        best_iterations[str(target)] = int(raw_best_iteration) if raw_best_iteration is not None else None
    return best_iterations


def _predict_target_in_batches(
    grid: pd.DataFrame,
    booster: xgb.Booster,
    feature_columns: list[str],
    normalization: dict[str, dict[str, float]] | None,
    batch_size: int | None,
    best_iteration: int | None,
) -> np.ndarray:
    if batch_size is None or batch_size <= 0 or len(grid) <= batch_size:
        normalized = apply_normalization(grid, normalization, feature_columns) if normalization is not None else grid
        matrix = xgb.DMatrix(normalized[feature_columns])
        return _predict_with_iteration_limit(booster, matrix, best_iteration)

    predictions = np.empty(len(grid), dtype=float)
    for start_idx in range(0, len(grid), batch_size):
        end_idx = min(start_idx + batch_size, len(grid))
        chunk = grid.iloc[start_idx:end_idx].copy()
        if normalization is not None:
            chunk = apply_normalization(chunk, normalization, feature_columns)
        matrix = xgb.DMatrix(chunk[feature_columns])
        predictions[start_idx:end_idx] = _predict_with_iteration_limit(booster, matrix, best_iteration)
    return predictions


def run_inference_snapshot(
    config: SimulationConfig,
    stations: pd.DataFrame,
    coarse: pd.DataFrame,
    registry: dict,
    normalization: dict[str, dict[str, float]],
    models: dict[str, xgb.Booster] | None = None,
) -> pd.DataFrame:
    raw_grid = _prepare_grid(config, stations, coarse.drop(columns=["timestamp"], errors="ignore"))
    raw_grid = ensure_columns(raw_grid, registry["feature_columns"])
    target_models = models if models is not None else _load_target_models(config, registry["targets"])
    best_iterations = _registry_best_iterations(registry)
    batch_size = config.inference.prediction_batch_size
    normalized_grid = None
    if batch_size is None or batch_size <= 0:
        normalized_grid = apply_normalization(raw_grid, normalization, registry["feature_columns"])

    for target in registry["targets"]:
        booster = target_models.get(target)
        if booster is None:
            continue
        residual = _predict_target_in_batches(
            grid=normalized_grid if normalized_grid is not None else raw_grid,
            booster=booster,
            feature_columns=registry["feature_columns"],
            normalization=None if normalized_grid is not None else normalization,
            batch_size=batch_size,
            best_iteration=best_iterations.get(target),
        )
        baseline_column = registry["target_baselines"][target]
        if baseline_column is None:
            baseline = pd.Series(0.0, index=raw_grid.index, dtype=float)
            raw_grid[f"predicted_{target}"] = baseline + residual
        else:
            baseline = raw_grid[baseline_column]
            raw_grid[f"predicted_{target}"] = np.where(baseline.notna(), baseline + residual, np.nan)
        raw_grid[f"predicted_residual_{target}"] = residual

    if "predicted_u10" in raw_grid.columns and "predicted_v10" in raw_grid.columns:
        predicted_speed, predicted_direction = uv_to_wind_speed_direction(
            raw_grid["predicted_u10"],
            raw_grid["predicted_v10"],
        )
        raw_grid["predicted_wind_speed"] = predicted_speed
        raw_grid["predicted_wind_direction"] = predicted_direction

    return raw_grid


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dense-grid downscaling inference.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    parser.add_argument("--stations", type=Path, default=None, help="Optional current stations table.")
    parser.add_argument("--coarse", type=Path, default=None, help="Optional current coarse grid table or NetCDF.")
    parser.add_argument("--dem", type=Path, default=None, help="Optional DEM GeoTIFF override.")
    args = parser.parse_args()

    config = load_config(args.config)
    station_path = args.stations or config.inference.station_file
    coarse_path = args.coarse or config.inference.coarse_file
    if args.dem is not None:
        config = replace(config, inference=replace(config.inference, dem_file=args.dem))

    ensure_directories(config.paths.output_dir)
    registry = read_json(config.paths.model_registry / "registry.json")
    normalization = read_json(config.paths.processed / "normalization.json")
    models = _load_target_models(config, registry["targets"])
    stations = _load_current_stations(station_path, dem_path=config.inference.dem_file)
    coarse = _load_current_coarse(coarse_path)
    raw_grid = run_inference_snapshot(config, stations, coarse, registry, normalization, models=models)

    timestamp = pd.Timestamp(stations["timestamp"].iloc[0]).strftime("%Y%m%dT%H%M%SZ")
    output = config.paths.output_dir / f"{config.inference.output_stem}_{timestamp}.parquet"
    raw_grid.to_parquet(output, index=False)


if __name__ == "__main__":
    main()