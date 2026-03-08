from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import pandas as pd

from sim.common import ensure_directories, read_json
from sim.config import load_config
from sim.inference.map_plots import save_multi_target_comparison_map
from sim.inference.run_downscaling import _load_current_coarse, _load_current_stations, _load_target_models, run_inference_snapshot


def _available_timestamps(stations: pd.DataFrame, coarse: pd.DataFrame) -> list[pd.Timestamp]:
    station_times = sorted(pd.Timestamp(value) for value in stations["timestamp"].dropna().unique().tolist())
    if "timestamp" not in coarse.columns:
        return station_times
    coarse_times = {pd.Timestamp(value) for value in coarse["timestamp"].dropna().unique().tolist()}
    return [timestamp for timestamp in station_times if timestamp in coarse_times]


def _filter_requested_timestamps(
    timestamps: list[pd.Timestamp],
    start: pd.Timestamp | None,
    end: pd.Timestamp | None,
) -> list[pd.Timestamp]:
    result = timestamps
    if start is not None:
        result = [timestamp for timestamp in result if timestamp >= start]
    if end is not None:
        result = [timestamp for timestamp in result if timestamp <= end]
    return result


def _plot_prediction_maps(
    frame: pd.DataFrame,
    targets: list[str],
    timestamp: pd.Timestamp,
    output_path: Path,
    label: str,
    dem_path: Path,
    clip_bounds: tuple[float, float, float, float] | None,
) -> None:
    save_multi_target_comparison_map(
        frame,
        targets,
        timestamp,
        output_path,
        label=label,
        dem_path=dem_path,
        clip_bounds=clip_bounds,
        baseline_label="ERA5-Land baseline",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Internal helper used by sim.workflows.run_inference_request and sim.workflows.run_ifs_snapshot. "
            "For normal plotting, prefer sim.workflows.plot_maps."
        )
    )
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    parser.add_argument("--stations", type=Path, default=None, help="Optional station table with one or more timestamps.")
    parser.add_argument("--coarse", type=Path, default=None, help="Optional coarse table or NetCDF with one or more timestamps.")
    parser.add_argument("--dem", type=Path, default=None, help="Optional DEM GeoTIFF override.")
    parser.add_argument(
        "--grid-stride",
        type=int,
        default=None,
        help="Optional stride override for faster map-oriented inference runs.",
    )
    parser.add_argument(
        "--map-dir",
        type=Path,
        default=None,
        help="Optional directory for saved inference map PNG files.",
    )
    parser.add_argument("--start", type=str, default=None, help="Optional request start timestamp.")
    parser.add_argument("--end", type=str, default=None, help="Optional request end timestamp.")
    parser.add_argument("--min-lon", type=float, default=None, help="Optional minimum longitude clip.")
    parser.add_argument("--max-lon", type=float, default=None, help="Optional maximum longitude clip.")
    parser.add_argument("--min-lat", type=float, default=None, help="Optional minimum latitude clip.")
    parser.add_argument("--max-lat", type=float, default=None, help="Optional maximum latitude clip.")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.dem is not None:
        config = replace(config, inference=replace(config.inference, dem_file=args.dem))
    if args.grid_stride is not None:
        config = replace(config, preprocess=replace(config.preprocess, grid_stride=args.grid_stride))

    station_path = args.stations or config.inference.station_file
    coarse_path = args.coarse or config.inference.coarse_file
    map_dir = args.map_dir or (config.paths.output_dir / "maps")

    ensure_directories(config.paths.output_dir, map_dir)
    registry = read_json(config.paths.model_registry / "registry.json")
    normalization = read_json(config.paths.processed / "normalization.json")
    models = _load_target_models(config, registry["targets"])
    stations = _load_current_stations(station_path, latest_only=False, dem_path=config.inference.dem_file)
    coarse = _load_current_coarse(coarse_path, latest_only=False)
    timestamps = _available_timestamps(stations, coarse)
    start_time = pd.Timestamp(args.start) if args.start is not None else None
    end_time = pd.Timestamp(args.end) if args.end is not None else None
    timestamps = _filter_requested_timestamps(timestamps, start_time, end_time)
    clip_values = [args.min_lon, args.max_lon, args.min_lat, args.max_lat]
    if any(value is not None for value in clip_values) and not all(value is not None for value in clip_values):
        raise ValueError("Area clipping requires all of --min-lon, --max-lon, --min-lat, and --max-lat.")
    clip_bounds = None if not all(value is not None for value in clip_values) else (args.min_lon, args.max_lon, args.min_lat, args.max_lat)

    if not timestamps:
        raise ValueError("No outputtable timestamps were found across the provided station and coarse inputs.")

    outputs: list[tuple[pd.Timestamp, Path, pd.DataFrame]] = []
    using_static_coarse = "timestamp" not in coarse.columns
    if using_static_coarse and len(timestamps) > 1:
        print("Coarse input has no timestamp column; reusing the same coarse field for each station timestamp.")

    total_timestamps = len(timestamps)
    for index, timestamp in enumerate(timestamps, start=1):
        station_snapshot = stations.loc[stations["timestamp"] == timestamp].copy()
        if station_snapshot.empty:
            continue
        if using_static_coarse:
            coarse_snapshot = coarse.copy()
        else:
            coarse_snapshot = coarse.loc[coarse["timestamp"] == timestamp].copy()
        if coarse_snapshot.empty:
            continue

        print(f"Running inference for timestamp {index}/{total_timestamps}: {pd.Timestamp(timestamp).isoformat()}")
        prediction = run_inference_snapshot(config, station_snapshot, coarse_snapshot, registry, normalization, models=models)
        if clip_bounds is not None:
            min_lon, max_lon, min_lat, max_lat = clip_bounds
            prediction = prediction.loc[
                prediction["longitude"].between(min_lon, max_lon)
                & prediction["latitude"].between(min_lat, max_lat)
            ].copy()
        if prediction.empty:
            continue
        timestamp_token = pd.Timestamp(timestamp).strftime("%Y%m%dT%H%M%SZ")
        output_path = config.paths.output_dir / f"{config.inference.output_stem}_{timestamp_token}.parquet"
        prediction.to_parquet(output_path, index=False)
        outputs.append((pd.Timestamp(timestamp), output_path, prediction))
        print(f"Saved inference output: {output_path}")

    if not outputs:
        raise ValueError("Inference did not produce any outputs from the provided inputs.")

    first_timestamp, first_output, first_frame = outputs[0]
    last_timestamp, last_output, last_frame = outputs[-1]
    first_map = map_dir / f"{config.inference.output_stem}_first_{first_timestamp:%Y%m%dT%H%M%SZ}.png"
    _plot_prediction_maps(first_frame, registry["targets"], first_timestamp, first_map, label="First", dem_path=config.inference.dem_file, clip_bounds=clip_bounds)
    print(f"Saved first inference map: {first_map}")

    if last_timestamp != first_timestamp:
        last_map = map_dir / f"{config.inference.output_stem}_last_{last_timestamp:%Y%m%dT%H%M%SZ}.png"
        _plot_prediction_maps(last_frame, registry["targets"], last_timestamp, last_map, label="Last", dem_path=config.inference.dem_file, clip_bounds=clip_bounds)
        print(f"Saved last inference map: {last_map}")
    else:
        last_map = first_map

    print(f"Produced {len(outputs)} inference dataset(s).")
    print(f"First output parquet: {first_output}")
    print(f"Last output parquet: {last_output}")
    print(f"First map PNG: {first_map}")
    print(f"Last map PNG: {last_map}")


if __name__ == "__main__":
    main()