from __future__ import annotations

import argparse
from pathlib import Path
import re

import pandas as pd

from sim.common import ensure_directories
from sim.inference.map_plots import save_multi_target_comparison_map, save_single_target_comparison_maps
from sim.workflows.common import load_workflow_config


TIMESTAMP_RE = re.compile(r"(\d{8}T\d{6}Z)")
TARGET_PRIORITY = ["temperature", "pressure", "pm25", "aqi", "u10", "v10"]


def _extract_timestamp_token(path: Path) -> str | None:
    match = TIMESTAMP_RE.search(path.stem)
    return match.group(1) if match is not None else None


def _resolve_timestamp_arg(raw: str) -> str:
    if TIMESTAMP_RE.fullmatch(raw):
        return raw
    return pd.Timestamp(raw, tz="UTC").strftime("%Y%m%dT%H%M%SZ")


def _resolve_parquet_path(request_dir: Path | None, parquet_path: Path | None, timestamp: str | None) -> tuple[Path, Path | None]:
    if (request_dir is None) == (parquet_path is None):
        raise ValueError("Pass exactly one of --request-dir or --parquet.")

    if parquet_path is not None:
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet input was not found: {parquet_path}")
        return parquet_path, None

    assert request_dir is not None
    if not request_dir.exists():
        raise FileNotFoundError(f"Request directory was not found: {request_dir}")

    data_dir = request_dir / "data"
    if not data_dir.exists():
        raise FileNotFoundError(f"Request data directory was not found: {data_dir}")

    candidates = sorted(data_dir.glob("*.parquet"))
    if not candidates:
        raise FileNotFoundError(f"No parquet outputs were found under {data_dir}")

    if timestamp is not None:
        token = _resolve_timestamp_arg(timestamp)
        matches = [path for path in candidates if token in path.name]
        if not matches:
            raise FileNotFoundError(f"No parquet output matched timestamp {token} under {data_dir}")
        return matches[-1], request_dir

    timestamped = [(path, _extract_timestamp_token(path)) for path in candidates]
    timestamped = [(path, token) for path, token in timestamped if token is not None]
    if timestamped:
        latest_path, _ = max(timestamped, key=lambda item: item[1])
        return latest_path, request_dir

    return candidates[-1], request_dir


def _infer_targets(frame: pd.DataFrame, raw_targets: str | None) -> list[str]:
    coarse_targets = {column.removeprefix("coarse_") for column in frame.columns if column.startswith("coarse_")}
    predicted_targets = {
        column.removeprefix("predicted_")
        for column in frame.columns
        if column.startswith("predicted_") and not column.startswith("predicted_residual_")
    }
    available = coarse_targets & predicted_targets

    ordered_available = [target for target in TARGET_PRIORITY if target in available]
    ordered_available.extend(sorted(target for target in available if target not in TARGET_PRIORITY))

    if raw_targets is None:
        if not ordered_available:
            raise ValueError("No plottable targets were found. Expected matching coarse_* and predicted_* columns.")
        return ordered_available

    requested = [target.strip() for target in raw_targets.split(",") if target.strip()]
    missing = [target for target in requested if target not in available]
    if missing:
        raise ValueError(f"Requested targets are not plottable from this parquet: {', '.join(missing)}")
    return requested


def _resolve_plot_dir(plot_dir: Path | None, request_dir: Path | None, parquet_path: Path) -> Path:
    if plot_dir is not None:
        return plot_dir
    if request_dir is not None:
        return request_dir / "plots" / "manual"
    if parquet_path.parent.name == "data":
        return parquet_path.parent.parent / "plots" / "manual"
    return parquet_path.parent / "plots"


def _default_baseline_label(request_dir: Path | None, explicit_label: str | None) -> str:
    if explicit_label is not None:
        return explicit_label
    if request_dir is not None and (request_dir / "live_inputs").exists():
        return "IFS coarse"
    return "ERA5-Land baseline"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plot side-by-side baseline vs SR maps from an existing downscaled parquet. "
            "This is the main user-facing plotting command."
        )
    )
    parser.add_argument("--config", default=None, help="Optional path to the simplified workflow TOML.")
    parser.add_argument("--request-dir", type=Path, default=None, help="Inference request directory containing data/ and plots/.")
    parser.add_argument("--parquet", type=Path, default=None, help="Single downscaled parquet to plot.")
    parser.add_argument("--timestamp", default=None, help="Optional timestamp to select from --request-dir. Accepts YYYYMMDDTHHMMSSZ or any pandas-readable UTC time.")
    parser.add_argument("--plot-dir", type=Path, default=None, help="Optional output directory for PNG files.")
    parser.add_argument("--dem", type=Path, default=None, help="Optional DEM override.")
    parser.add_argument("--targets", default=None, help="Optional comma-separated target list such as temperature,pressure.")
    parser.add_argument("--baseline-label", default=None, help="Optional panel label for the coarse field.")
    parser.add_argument("--min-lon", type=float, default=None, help="Optional minimum longitude clip.")
    parser.add_argument("--max-lon", type=float, default=None, help="Optional maximum longitude clip.")
    parser.add_argument("--min-lat", type=float, default=None, help="Optional minimum latitude clip.")
    parser.add_argument("--max-lat", type=float, default=None, help="Optional maximum latitude clip.")
    args = parser.parse_args()

    workflow = load_workflow_config(args.config)
    parquet_path, resolved_request_dir = _resolve_parquet_path(args.request_dir, args.parquet, args.timestamp)
    frame = pd.read_parquet(parquet_path)
    targets = _infer_targets(frame, args.targets)
    dem_path = args.dem or workflow.request.dem_file or workflow.inference.dem_file
    plot_dir = _resolve_plot_dir(args.plot_dir, resolved_request_dir, parquet_path)
    ensure_directories(plot_dir)

    clip_values = [args.min_lon, args.max_lon, args.min_lat, args.max_lat]
    if any(value is not None for value in clip_values) and not all(value is not None for value in clip_values):
        raise ValueError("Area clipping requires all of --min-lon, --max-lon, --min-lat, and --max-lat.")
    clip_bounds = None if not all(value is not None for value in clip_values) else (args.min_lon, args.max_lon, args.min_lat, args.max_lat)

    timestamp_token = _extract_timestamp_token(parquet_path)
    if timestamp_token is not None:
        timestamp = pd.Timestamp(timestamp_token)
    elif "timestamp" in frame.columns:
        timestamp = pd.to_datetime(frame["timestamp"], utc=True).max()
    else:
        raise ValueError("Could not determine a timestamp from the parquet filename or contents.")

    baseline_label = _default_baseline_label(resolved_request_dir, args.baseline_label)
    combined_path = plot_dir / f"comparison_{timestamp:%Y%m%dT%H%M%SZ}.png"
    save_multi_target_comparison_map(
        frame,
        targets,
        timestamp,
        combined_path,
        label="Selected",
        dem_path=dem_path,
        clip_bounds=clip_bounds,
        baseline_label=baseline_label,
    )
    single_paths = save_single_target_comparison_maps(
        frame,
        targets,
        timestamp,
        plot_dir,
        dem_path=dem_path,
        clip_bounds=clip_bounds,
        baseline_label=baseline_label,
        file_prefix="compare",
    )

    print(f"Source parquet: {parquet_path}")
    print(f"Targets: {', '.join(targets)}")
    print(f"Combined plot: {combined_path}")
    for path in single_paths:
        print(f"Per-target plot: {path}")


if __name__ == "__main__":
    main()