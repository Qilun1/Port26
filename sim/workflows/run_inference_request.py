from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import KDTree

from sim.common import ensure_directories, read_json
from sim.inference.run_downscaling import _load_current_coarse, _load_current_stations
from sim.workflows.common import build_runtime_payload, copy_workflow_config, load_workflow_config, run_module, write_runtime_config


DEFAULT_STATION_PLOT_HOURS = 24
DEFAULT_STATION_PLOT_MAX_STATIONS = 3


def _select_station_plot_window(
    timestamps: list[pd.Timestamp],
    sample_hours: int,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if not timestamps:
        return None
    ordered = sorted(pd.Timestamp(timestamp) for timestamp in timestamps)
    start = ordered[0]
    end_limit = start + pd.Timedelta(hours=max(sample_hours - 1, 0))
    eligible = [timestamp for timestamp in ordered if timestamp <= end_limit]
    end = eligible[-1] if eligible else start
    return start, end


def _nearest_rows(source: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    tree = KDTree(np.column_stack([source["longitude"].to_numpy(), source["latitude"].to_numpy()]))
    _, indices = tree.query(np.column_stack([target["longitude"].to_numpy(), target["latitude"].to_numpy()]), k=1)
    return source.iloc[np.asarray(indices)].reset_index(drop=True)


def _build_station_comparison_frame(
    stations: pd.DataFrame,
    coarse: pd.DataFrame,
    predictions: pd.DataFrame,
    targets: list[str],
) -> pd.DataFrame:
    station_meta_columns = [
        column
        for column in ["timestamp", "station_id", "station_name", "latitude", "longitude"]
        if column in stations.columns
    ]
    station_base = stations[station_meta_columns + [target for target in targets if target in stations.columns]].reset_index(drop=True)
    nearest_coarse = _nearest_rows(coarse, station_base)
    nearest_predictions = _nearest_rows(predictions, station_base)

    comparison = station_base.copy()
    for target in targets:
        baseline_column = f"coarse_{target}"
        predicted_column = f"predicted_{target}"
        if baseline_column in nearest_coarse.columns:
            comparison[baseline_column] = nearest_coarse[baseline_column].to_numpy()
        if predicted_column in nearest_predictions.columns:
            comparison[predicted_column] = nearest_predictions[predicted_column].to_numpy()
    return comparison


def _select_representative_station_ids(frame: pd.DataFrame, max_stations: int) -> list[object]:
    counts = (
        frame.groupby(["station_id", "station_name"], dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(max_stations)
    )
    return [station_id for station_id, _ in counts.index.tolist()]


def _plot_station_timeseries(
    target: str,
    frame: pd.DataFrame,
    output_path: Path,
    max_stations: int,
    baseline_label: str,
) -> None:
    target_frame = frame.loc[
        frame[target].notna()
        & frame[f"coarse_{target}"].notna()
        & frame[f"predicted_{target}"].notna()
    ].copy()
    if target_frame.empty:
        return

    station_ids = _select_representative_station_ids(target_frame, max_stations=max_stations)
    if not station_ids:
        return

    fig, axes = plt.subplots(len(station_ids), 1, figsize=(14, 4 * len(station_ids)), sharex=True)
    if len(station_ids) == 1:
        axes = [axes]

    for axis, station_id in zip(axes, station_ids):
        station_frame = target_frame.loc[target_frame["station_id"] == station_id].sort_values("timestamp")
        station_name = str(station_frame["station_name"].iloc[0]) if "station_name" in station_frame.columns else str(station_id)
        axis.plot(station_frame["timestamp"], station_frame[target], label="Station", linewidth=1.9)
        axis.plot(station_frame["timestamp"], station_frame[f"coarse_{target}"], label=baseline_label, linewidth=1.2)
        axis.plot(station_frame["timestamp"], station_frame[f"predicted_{target}"], label="SR model", linewidth=1.2)
        axis.set_title(f"{target} at station {station_name} ({station_id})")
        axis.set_ylabel(target)
        axis.grid(alpha=0.25)
        axis.legend(loc="best")

    axes[-1].set_xlabel("Time")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _save_station_comparison_plots(
    *,
    request_dir: Path,
    station_path: Path,
    coarse_path: Path,
    dem_path: Path,
    output_stem: str,
    targets: list[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    sample_hours: int,
    max_stations: int,
    baseline_label: str,
) -> list[Path]:
    stations = _load_current_stations(station_path, latest_only=False, dem_path=dem_path)
    stations = stations.loc[(stations["timestamp"] >= start) & (stations["timestamp"] <= end)].copy()
    if stations.empty:
        return []

    coarse = _load_current_coarse(coarse_path, latest_only=False)
    available_timestamps = sorted(pd.Timestamp(value) for value in stations["timestamp"].dropna().unique().tolist())
    sample_window = _select_station_plot_window(available_timestamps, sample_hours)
    if sample_window is None:
        return []
    sample_start, sample_end = sample_window
    sample_timestamps = [timestamp for timestamp in available_timestamps if sample_start <= timestamp <= sample_end]
    using_static_coarse = "timestamp" not in coarse.columns

    comparison_frames: list[pd.DataFrame] = []
    for timestamp in sample_timestamps:
        prediction_path = request_dir / "data" / f"{output_stem}_{pd.Timestamp(timestamp):%Y%m%dT%H%M%SZ}.parquet"
        if not prediction_path.exists():
            continue
        station_snapshot = stations.loc[stations["timestamp"] == timestamp].copy()
        if station_snapshot.empty:
            continue
        coarse_snapshot = coarse.copy() if using_static_coarse else coarse.loc[coarse["timestamp"] == timestamp].copy()
        if coarse_snapshot.empty:
            continue
        prediction_snapshot = pd.read_parquet(prediction_path)
        comparison_frames.append(
            _build_station_comparison_frame(
                stations=station_snapshot,
                coarse=coarse_snapshot,
                predictions=prediction_snapshot,
                targets=targets,
            )
        )

    if not comparison_frames:
        return []

    comparison = pd.concat(comparison_frames, ignore_index=True)
    station_plot_dir = request_dir / "plots" / "stations"
    station_plot_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_parquet(station_plot_dir / "station_comparison_sample.parquet", index=False)

    written: list[Path] = []
    for target in targets:
        required_columns = {target, f"coarse_{target}", f"predicted_{target}"}
        if not required_columns.issubset(comparison.columns):
            continue
        output_path = station_plot_dir / f"station_compare_{target}.png"
        _plot_station_timeseries(
            target=target,
            frame=comparison,
            output_path=output_path,
            max_stations=max_stations,
            baseline_label=baseline_label,
        )
        if output_path.exists():
            written.append(output_path)
    return written


def _resolve_demo_inference_inputs(
    workflow,
    request_dir: Path,
    *,
    explicit_stations: str | None,
    explicit_coarse: str | None,
    requested_start: pd.Timestamp | None,
    requested_end: pd.Timestamp | None,
) -> tuple[Path | None, Path | None]:
    station_path = Path(explicit_stations) if explicit_stations is not None else workflow.inference.station_file
    coarse_path = Path(explicit_coarse) if explicit_coarse is not None else workflow.inference.coarse_file

    missing_station = not station_path.exists()
    missing_coarse = not coarse_path.exists()
    if not missing_station and not missing_coarse:
        return None, None

    if explicit_stations is not None and missing_station:
        raise FileNotFoundError(
            f"Station input was not found: {station_path}. Pass an existing file with --stations or update [inference].station_file in your workflow config."
        )
    if explicit_coarse is not None and missing_coarse:
        raise FileNotFoundError(
            f"Coarse input was not found: {coarse_path}. Pass an existing file with --coarse or update [inference].coarse_file in your workflow config."
        )

    processed_path = workflow.paths.processed / "station_training_raw.parquet"
    if not processed_path.exists():
        missing_labels = []
        if missing_station:
            missing_labels.append(f"station input {station_path}")
        if missing_coarse:
            missing_labels.append(f"coarse input {coarse_path}")
        joined = " and ".join(missing_labels)
        raise FileNotFoundError(
            f"{joined} not found, and no processed training snapshot is available at {processed_path} for an automatic smoke-test fallback."
        )

    raw = pd.read_parquet(processed_path)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
    candidate = raw.copy()
    if requested_start is not None:
        candidate = candidate.loc[candidate["timestamp"] >= requested_start].copy()
    if requested_end is not None:
        candidate = candidate.loc[candidate["timestamp"] <= requested_end].copy()
    if candidate.empty:
        latest_timestamp = raw["timestamp"].max()
        candidate = raw.loc[raw["timestamp"] == latest_timestamp].copy()
        print(
            "Requested inference window was not found in processed training data; "
            f"using the latest available snapshot at {latest_timestamp.isoformat()} as a smoke test."
        )
    else:
        print(
            "Configured inference inputs were missing; using processed training data as a smoke-test source "
            f"for {candidate['timestamp'].min().isoformat()} to {candidate['timestamp'].max().isoformat()}."
        )

    cadence = (workflow.data.frequency or "1H").lower()
    candidate = candidate.copy()
    candidate["timestamp"] = candidate["timestamp"].dt.floor(cadence)

    demo_station_path = request_dir / "demo_current_stations.parquet"
    demo_coarse_path = request_dir / "demo_current_coarse.parquet"

    if missing_station:
        station_columns = [
            column
            for column in [
                "timestamp",
                "station_name",
                "station_id",
                "latitude",
                "longitude",
                "temperature",
                "pressure",
                "wind_speed",
                "wind_direction",
                "station_u10",
                "station_v10",
                "u10",
                "v10",
            ]
            if column in candidate.columns
        ]
        station_frame = candidate[station_columns].drop_duplicates(
            subset=["timestamp", "station_id"],
            keep="last",
        ).reset_index(drop=True)
        if station_frame.empty:
            raise ValueError("Automatic smoke-test station input generation produced no rows.")
        station_frame.to_parquet(demo_station_path, index=False)
        station_path = demo_station_path

    if missing_coarse:
        coarse_columns = [
            column
            for column in [
                "timestamp",
                "coarse_latitude",
                "coarse_longitude",
                "coarse_temperature",
                "coarse_pressure",
                "coarse_u10",
                "coarse_v10",
                "coarse_pm25",
                "coarse_no2",
                "coarse_o3",
                "coarse_so2",
                "coarse_aqi",
            ]
            if column in candidate.columns
        ]
        coarse_frame = candidate[coarse_columns].rename(
            columns={
                "coarse_latitude": "latitude",
                "coarse_longitude": "longitude",
            }
        )
        coarse_frame = coarse_frame.drop_duplicates(subset=["timestamp", "latitude", "longitude"]).reset_index(drop=True)
        if coarse_frame.empty:
            raise ValueError("Automatic smoke-test coarse input generation produced no rows.")
        coarse_frame.to_parquet(demo_coarse_path, index=False)
        coarse_path = demo_coarse_path

    return station_path, coarse_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an inference request with explicit time and area controls using the simplified workflow config.")
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    parser.add_argument("--run-name", default=None, help="Optional trained run name to use for inference.")
    parser.add_argument("--request-name", default=None, help="Optional request folder name.")
    parser.add_argument("--stations", default=None, help="Optional station table override.")
    parser.add_argument("--coarse", default=None, help="Optional coarse table or NetCDF override.")
    parser.add_argument("--dem", default=None, help="Optional DEM override.")
    parser.add_argument("--start", default=None, help="Optional inference start timestamp.")
    parser.add_argument("--end", default=None, help="Optional inference end timestamp.")
    parser.add_argument("--min-lon", type=float, default=None, help="Optional minimum longitude clip.")
    parser.add_argument("--max-lon", type=float, default=None, help="Optional maximum longitude clip.")
    parser.add_argument("--min-lat", type=float, default=None, help="Optional minimum latitude clip.")
    parser.add_argument("--max-lat", type=float, default=None, help="Optional maximum latitude clip.")
    parser.add_argument("--grid-stride", type=int, default=None, help="Optional preview stride override.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    run_name = args.run_name or workflow.request.run_name or workflow.train.run_name
    model_dir = workflow.paths.model_runs_root / run_name
    if not model_dir.exists():
        raise FileNotFoundError(
            f"Model run directory was not found: {model_dir}. Train a run first or pass an existing --run-name."
        )
    registry_path = model_dir / "registry.json"
    if not registry_path.exists():
        raise FileNotFoundError(
            f"Model registry was not found: {registry_path}. The selected run does not look complete."
        )
    registry = read_json(registry_path)
    request_name = args.request_name or workflow.request.request_name or datetime.now(timezone.utc).strftime("request_%Y%m%dT%H%M%SZ")
    request_dir = workflow.paths.inference_runs_root / request_name
    data_dir = request_dir / "data"
    plot_dir = request_dir / "plots"
    ensure_directories(request_dir, data_dir, plot_dir)

    configured_station_path = str(workflow.request.station_file) if workflow.request.station_file is not None else None
    configured_coarse_path = str(workflow.request.coarse_file) if workflow.request.coarse_file is not None else None
    configured_dem_path = str(workflow.request.dem_file) if workflow.request.dem_file is not None else None
    resolved_station_arg = args.stations or configured_station_path
    resolved_coarse_arg = args.coarse or configured_coarse_path
    resolved_dem_arg = args.dem or configured_dem_path
    default_request_start = workflow.request.start or workflow.data.start
    default_request_end = workflow.request.end or workflow.data.end
    requested_start = pd.Timestamp(args.start, tz="UTC") if args.start is not None else default_request_start
    requested_end = pd.Timestamp(args.end, tz="UTC") if args.end is not None else default_request_end
    station_override, coarse_override = _resolve_demo_inference_inputs(
        workflow,
        request_dir,
        explicit_stations=resolved_station_arg,
        explicit_coarse=resolved_coarse_arg,
        requested_start=requested_start,
        requested_end=requested_end,
    )

    runtime_config = request_dir / "resolved_config.toml"
    payload = build_runtime_payload(
        workflow,
        model_registry=model_dir,
        output_dir=data_dir,
        station_file=station_override or resolved_station_arg,
        coarse_file=coarse_override or resolved_coarse_arg,
        dem_file=resolved_dem_arg,
        grid_stride=args.grid_stride or workflow.request.grid_stride or workflow.inference.preview_grid_stride,
        prediction_batch_size=workflow.request.prediction_batch_size,
    )
    write_runtime_config(payload, runtime_config)
    copy_workflow_config(workflow.path, request_dir / "workflow_config.toml")

    extra_args = ["--map-dir", str(plot_dir)]
    start_arg = args.start or (requested_start.isoformat().replace("+00:00", "Z") if requested_start is not None else None)
    end_arg = args.end or (requested_end.isoformat().replace("+00:00", "Z") if requested_end is not None else None)
    min_lon = args.min_lon if args.min_lon is not None else workflow.request.min_lon
    max_lon = args.max_lon if args.max_lon is not None else workflow.request.max_lon
    min_lat = args.min_lat if args.min_lat is not None else workflow.request.min_lat
    max_lat = args.max_lat if args.max_lat is not None else workflow.request.max_lat
    if start_arg is not None:
        extra_args.extend(["--start", start_arg])
    if end_arg is not None:
        extra_args.extend(["--end", end_arg])
    if min_lon is not None:
        extra_args.extend(["--min-lon", str(min_lon)])
    if max_lon is not None:
        extra_args.extend(["--max-lon", str(max_lon)])
    if min_lat is not None:
        extra_args.extend(["--min-lat", str(min_lat)])
    if max_lat is not None:
        extra_args.extend(["--max-lat", str(max_lat)])

    run_module("sim.inference.run_inference_and_map", runtime_config, extra_args=extra_args)

    if station_override is not None:
        resolved_station_path = station_override
    else:
        if resolved_station_arg is None:
            raise ValueError("No station input was resolved for station comparison plots.")
        resolved_station_path = Path(resolved_station_arg)

    if coarse_override is not None:
        resolved_coarse_path = coarse_override
    else:
        if resolved_coarse_arg is None:
            raise ValueError("No coarse input was resolved for station comparison plots.")
        resolved_coarse_path = Path(resolved_coarse_arg)

    station_plot_paths = _save_station_comparison_plots(
        request_dir=request_dir,
        station_path=resolved_station_path,
        coarse_path=resolved_coarse_path,
        dem_path=workflow.request.dem_file or workflow.inference.dem_file,
        output_stem=workflow.inference.output_stem,
        targets=list(registry["targets"]),
        start=requested_start,
        end=requested_end,
        sample_hours=workflow.request.station_plot_hours or DEFAULT_STATION_PLOT_HOURS,
        max_stations=workflow.request.station_plot_max_stations or DEFAULT_STATION_PLOT_MAX_STATIONS,
        baseline_label="ERA5-Land baseline",
    )
    print(f"Inference request saved to {request_dir}")
    for path in station_plot_paths:
        print(f"Saved station comparison plot: {path}")


if __name__ == "__main__":
    main()