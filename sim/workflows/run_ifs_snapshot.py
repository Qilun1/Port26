from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from sim.common import ensure_directories, read_json
from sim.config import BoundingBox
from sim.data_in.ifs_snapshot import fetch_fmi_weather_snapshot, fetch_ifs_snapshot
from sim.inference.map_plots import save_single_target_comparison_maps
from sim.workflows.common import build_runtime_payload, copy_workflow_config, load_workflow_config, run_module, write_runtime_config


def _plot_sample(frame: pd.DataFrame, max_points: int = 25000) -> pd.DataFrame:
    if len(frame) <= max_points:
        return frame
    return frame.sample(n=max_points, random_state=42).sort_values(["latitude", "longitude"]).reset_index(drop=True)


def _save_comparison_plots(
    coarse_path: Path,
    downscaled_path: Path,
    plot_dir: Path,
    targets: list[str],
    timestamp: pd.Timestamp,
    dem_path: Path,
    clip_bounds: tuple[float, float, float, float] | None,
) -> list[Path]:
    downscaled = pd.read_parquet(downscaled_path)
    return save_single_target_comparison_maps(
        downscaled,
        targets,
        timestamp,
        plot_dir,
        dem_path=dem_path,
        clip_bounds=clip_bounds,
        baseline_label="IFS coarse",
        file_prefix="ifs_compare",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch one live IFS timestep and FMI station snapshot, run one inference request, and save quick comparison plots.")
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    parser.add_argument("--run-name", default=None, help="Optional trained run name override.")
    parser.add_argument("--request-name", default=None, help="Optional request folder override.")
    parser.add_argument("--date", default=None, help="Optional IFS run date as YYYYMMDD. Defaults to latest available.")
    parser.add_argument("--time", type=int, default=None, help="Optional IFS run hour as 0, 6, 12, or 18. Defaults to latest available.")
    parser.add_argument("--step", type=int, default=0, help="Forecast step in hours. Defaults to 0.")
    parser.add_argument("--source", default="ecmwf", help="ECMWF open-data source key.")
    parser.add_argument("--model", default="ifs", help="Open-data model key.")
    parser.add_argument("--resol", default="0p25", help="Open-data resolution key.")
    parser.add_argument("--grid-stride", type=int, default=None, help="Optional preview stride override.")
    parser.add_argument("--station-lookback-hours", type=int, default=6, help="How many hours to look back for FMI station observations.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    run_name = args.run_name or workflow.request.run_name or workflow.train.run_name
    model_dir = workflow.paths.model_runs_root / run_name
    registry_path = model_dir / "registry.json"
    if not model_dir.exists() or not registry_path.exists():
        raise FileNotFoundError(f"Model run {run_name} is not available at {model_dir}.")
    registry = read_json(registry_path)

    bbox = BoundingBox(
        min_lon=workflow.request.min_lon if workflow.request.min_lon is not None else workflow.bbox.min_lon,
        max_lon=workflow.request.max_lon if workflow.request.max_lon is not None else workflow.bbox.max_lon,
        min_lat=workflow.request.min_lat if workflow.request.min_lat is not None else workflow.bbox.min_lat,
        max_lat=workflow.request.max_lat if workflow.request.max_lat is not None else workflow.bbox.max_lat,
    )

    live_dir_name = args.request_name or f"ifs_live_{run_name}"
    request_dir = workflow.paths.inference_runs_root / live_dir_name
    live_input_dir = request_dir / "live_inputs"
    data_dir = request_dir / "data"
    plot_dir = request_dir / "plots"
    ensure_directories(request_dir, live_input_dir, data_dir, plot_dir)

    ifs_result = fetch_ifs_snapshot(
        live_input_dir,
        bbox,
        date=args.date,
        time=args.time,
        step=args.step,
        source=args.source,
        model=args.model,
        resol=args.resol,
    )
    fmi_result = fetch_fmi_weather_snapshot(
        live_input_dir,
        bbox,
        target_time=ifs_result.run_timestamp,
        lookback_hours=args.station_lookback_hours,
    )

    runtime_config = request_dir / "resolved_config.toml"
    runtime_payload = build_runtime_payload(
        workflow,
        model_registry=model_dir,
        output_dir=data_dir,
        station_file=fmi_result.station_path,
        coarse_file=ifs_result.coarse_path,
        dem_file=workflow.inference.dem_file,
        grid_stride=args.grid_stride or workflow.request.grid_stride or workflow.inference.preview_grid_stride,
        prediction_batch_size=workflow.request.prediction_batch_size,
    )
    runtime_payload["model"]["targets"] = list(registry["targets"])
    write_runtime_config(runtime_payload, runtime_config)
    copy_workflow_config(workflow.path, request_dir / "workflow_config.toml")

    timestamp_arg = ifs_result.run_timestamp.isoformat().replace("+00:00", "Z")
    extra_args = [
        "--map-dir",
        str(plot_dir),
        "--start",
        timestamp_arg,
        "--end",
        timestamp_arg,
        "--min-lon",
        str(bbox.min_lon),
        "--max-lon",
        str(bbox.max_lon),
        "--min-lat",
        str(bbox.min_lat),
        "--max-lat",
        str(bbox.max_lat),
    ]
    run_module("sim.inference.run_inference_and_map", runtime_config, extra_args=extra_args)

    timestamp_token = ifs_result.run_timestamp.strftime("%Y%m%dT%H%M%SZ")
    downscaled_path = data_dir / f"{workflow.inference.output_stem}_{timestamp_token}.parquet"
    if downscaled_path.exists():
        _save_comparison_plots(
            ifs_result.coarse_path,
            downscaled_path,
            plot_dir,
            list(registry["targets"]),
            ifs_result.run_timestamp,
            workflow.inference.dem_file,
            (bbox.min_lon, bbox.max_lon, bbox.min_lat, bbox.max_lat),
        )

    print(f"Live IFS inference request saved to {request_dir}")
    print(f"IFS timestamp: {ifs_result.run_timestamp.isoformat()}")
    print(f"FMI station timestamp: {fmi_result.station_timestamp.isoformat()}")


if __name__ == "__main__":
    main()