from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

from sim.common import apply_normalization, ensure_directories, read_json
from sim.config import load_config


def _split_frame(frame: pd.DataFrame, validation_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    split_idx = max(1, int(len(ordered) * (1.0 - validation_fraction)))
    split_idx = min(split_idx, len(ordered) - 1)
    return ordered.iloc[:split_idx].copy(), ordered.iloc[split_idx:].copy()


def _metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(observed, predicted))),
        "mae": float(mean_absolute_error(observed, predicted)),
        "r2": float(r2_score(observed, predicted)),
    }


def _predict_with_iteration_limit(
    booster: xgb.Booster,
    matrix: xgb.DMatrix,
    best_iteration: int | None,
) -> np.ndarray:
    if best_iteration is None or best_iteration < 0:
        return booster.predict(matrix)
    return booster.predict(matrix, iteration_range=(0, best_iteration + 1))


def _build_validation_frame(
    frame: pd.DataFrame,
    target: str,
    feature_columns: list[str],
    normalization: dict[str, dict[str, float]],
    validation_fraction: float,
    model_path: Path,
    baseline_column: str,
    best_iteration: int | None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    label_column = f"residual_{target}"
    filtered = frame.loc[frame[label_column].notna()].copy()
    _, valid_frame = _split_frame(filtered, validation_fraction)
    normalized_valid = apply_normalization(valid_frame, normalization, feature_columns)

    booster = xgb.Booster()
    booster.load_model(model_path)
    predicted_residual = _predict_with_iteration_limit(
        booster,
        xgb.DMatrix(normalized_valid[feature_columns]),
        best_iteration,
    )

    baseline = valid_frame[baseline_column].to_numpy(dtype=float)
    observed = valid_frame[target].to_numpy(dtype=float)
    predicted = baseline + predicted_residual

    metrics = {
        "target": target,
        "validation_samples": int(len(valid_frame)),
    }
    metrics.update({f"model_{key}": value for key, value in _metrics(observed, predicted).items()})
    metrics.update({f"baseline_{key}": value for key, value in _metrics(observed, baseline).items()})

    output = valid_frame[["timestamp", "station_id", "station_name", "latitude", "longitude", target, baseline_column]].copy()
    output = output.rename(columns={target: "observed", baseline_column: "baseline"})
    output["predicted"] = predicted
    output["predicted_residual"] = predicted_residual
    output["baseline_abs_error"] = np.abs(output["observed"] - output["baseline"])
    output["model_abs_error"] = np.abs(output["observed"] - output["predicted"])
    return output, metrics


def _plot_metric_bars(summary: pd.DataFrame, output_path: Path) -> None:
    targets = summary["target"].tolist()
    positions = np.arange(len(targets))
    width = 0.35

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    axes[0].bar(positions - width / 2, summary["baseline_rmse"], width=width, label="Baseline")
    axes[0].bar(positions + width / 2, summary["model_rmse"], width=width, label="Model")
    axes[0].set_title("Validation RMSE")
    axes[0].set_xticks(positions)
    axes[0].set_xticklabels(targets, rotation=20)
    axes[0].legend()

    axes[1].bar(positions - width / 2, summary["baseline_mae"], width=width, label="Baseline")
    axes[1].bar(positions + width / 2, summary["model_mae"], width=width, label="Model")
    axes[1].set_title("Validation MAE")
    axes[1].set_xticks(positions)
    axes[1].set_xticklabels(targets, rotation=20)

    axes[2].bar(positions - width / 2, summary["baseline_r2"], width=width, label="Baseline")
    axes[2].bar(positions + width / 2, summary["model_r2"], width=width, label="Model")
    axes[2].axhline(0.0, color="black", linewidth=1)
    axes[2].set_title("Validation R2")
    axes[2].set_xticks(positions)
    axes[2].set_xticklabels(targets, rotation=20)

    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_spatial_errors(target: str, frame: pd.DataFrame, output_path: Path) -> None:
    latest_timestamp = frame["timestamp"].max()
    latest = frame.loc[frame["timestamp"] == latest_timestamp].copy()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    baseline_plot = axes[0].scatter(
        latest["longitude"],
        latest["latitude"],
        c=latest["baseline_abs_error"],
        s=18,
        cmap="magma",
    )
    axes[0].set_title(f"{target} baseline abs error")
    axes[0].set_xlabel("Longitude")
    axes[0].set_ylabel("Latitude")
    plt.colorbar(baseline_plot, ax=axes[0])

    model_plot = axes[1].scatter(
        latest["longitude"],
        latest["latitude"],
        c=latest["model_abs_error"],
        s=18,
        cmap="viridis",
    )
    axes[1].set_title(f"{target} model abs error")
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")
    plt.colorbar(model_plot, ax=axes[1])

    fig.suptitle(f"Validation area view at {latest_timestamp}")
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_spatial_comparison(target: str, frame: pd.DataFrame, output_path: Path) -> None:
    latest_timestamp = frame["timestamp"].max()
    latest = frame.loc[frame["timestamp"] == latest_timestamp].copy()

    all_values = pd.concat([latest["baseline"], latest["predicted"], latest["observed"]], axis=0)
    color_min = float(all_values.min())
    color_max = float(all_values.max())

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    baseline_plot = axes[0].scatter(
        latest["longitude"],
        latest["latitude"],
        c=latest["baseline"],
        s=22,
        cmap="coolwarm",
        vmin=color_min,
        vmax=color_max,
    )
    axes[0].set_title(f"{target} ERA5/ECMWF baseline")
    axes[0].set_xlabel("Longitude")
    axes[0].set_ylabel("Latitude")
    plt.colorbar(baseline_plot, ax=axes[0])

    model_plot = axes[1].scatter(
        latest["longitude"],
        latest["latitude"],
        c=latest["predicted"],
        s=22,
        cmap="coolwarm",
        vmin=color_min,
        vmax=color_max,
    )
    axes[1].set_title(f"{target} model prediction")
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")
    plt.colorbar(model_plot, ax=axes[1])

    observed_plot = axes[2].scatter(
        latest["longitude"],
        latest["latitude"],
        c=latest["observed"],
        s=22,
        cmap="coolwarm",
        vmin=color_min,
        vmax=color_max,
    )
    axes[2].set_title(f"{target} observed station")
    axes[2].set_xlabel("Longitude")
    axes[2].set_ylabel("Latitude")
    plt.colorbar(observed_plot, ax=axes[2])

    fig.suptitle(f"Validation comparison at {latest_timestamp}")
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _select_representative_stations(frame: pd.DataFrame, max_stations: int = 3) -> list[tuple[int | str, str]]:
    station_counts = (
        frame.groupby(["station_id", "station_name"], dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(max_stations)
    )
    return [(station_id, station_name) for station_id, station_name in station_counts.index.tolist()]


def _plot_station_timeseries(target: str, frame: pd.DataFrame, output_path: Path, max_stations: int = 3) -> None:
    stations = _select_representative_stations(frame, max_stations=max_stations)
    if not stations:
        return

    fig, axes = plt.subplots(len(stations), 1, figsize=(14, 4 * len(stations)), sharex=True)
    if len(stations) == 1:
        axes = [axes]

    for axis, (station_id, station_name) in zip(axes, stations):
        station_frame = frame.loc[frame["station_id"] == station_id].sort_values("timestamp")
        axis.plot(station_frame["timestamp"], station_frame["observed"], label="Observed", linewidth=1.8)
        axis.plot(station_frame["timestamp"], station_frame["baseline"], label="ERA5/ECMWF", linewidth=1.2)
        axis.plot(station_frame["timestamp"], station_frame["predicted"], label="Model", linewidth=1.2)
        axis.set_title(f"{target} at station {station_name} ({station_id})")
        axis.set_ylabel(target)
        axis.grid(alpha=0.25)
        axis.legend(loc="best")

    axes[-1].set_xlabel("Validation time")
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_mean_error_map(target: str, frame: pd.DataFrame, output_path: Path) -> None:
    grouped = (
        frame.groupby(["station_id", "station_name", "latitude", "longitude"], dropna=False)
        [["baseline_abs_error", "model_abs_error"]]
        .mean()
        .reset_index()
    )

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    baseline_plot = axes[0].scatter(
        grouped["longitude"],
        grouped["latitude"],
        c=grouped["baseline_abs_error"],
        s=28,
        cmap="magma",
    )
    axes[0].set_title(f"{target} mean baseline abs error")
    axes[0].set_xlabel("Longitude")
    axes[0].set_ylabel("Latitude")
    plt.colorbar(baseline_plot, ax=axes[0])

    model_plot = axes[1].scatter(
        grouped["longitude"],
        grouped["latitude"],
        c=grouped["model_abs_error"],
        s=28,
        cmap="viridis",
    )
    axes[1].set_title(f"{target} mean model abs error")
    axes[1].set_xlabel("Longitude")
    axes[1].set_ylabel("Latitude")
    plt.colorbar(model_plot, ax=axes[1])

    fig.suptitle("Validation-period mean absolute error by station")
    plt.tight_layout()
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create simple validation metrics and spatial plots for trained models.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional directory for validation plots and CSV outputs.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    output_dir = args.output_dir or (config.paths.model_registry / "validation_plots")
    ensure_directories(output_dir)

    frame = pd.read_parquet(config.paths.processed / "station_training_raw.parquet")
    metadata = read_json(config.paths.processed / "metadata.json")
    normalization = read_json(config.paths.processed / "normalization.json")
    registry = read_json(config.paths.model_registry / "registry.json")
    best_iterations = {
        metric["target"]: metric.get("best_iteration")
        for metric in registry.get("metrics", [])
        if metric.get("target") is not None
    }

    feature_columns = metadata["feature_columns"]
    summary_rows: list[dict[str, float]] = []

    for target in registry["targets"]:
        model_path = config.paths.model_registry / f"{target}.json"
        if not model_path.exists():
            continue

        validation_frame, metrics = _build_validation_frame(
            frame=frame,
            target=target,
            feature_columns=feature_columns,
            normalization=normalization,
            validation_fraction=config.model.validation_fraction,
            model_path=model_path,
            baseline_column=registry["target_baselines"][target],
            best_iteration=(
                int(best_iterations[target])
                if target in best_iterations and best_iterations[target] is not None
                else None
            ),
        )
        validation_frame.to_parquet(output_dir / f"validation_{target}.parquet", index=False)
        _plot_spatial_errors(target, validation_frame, output_dir / f"validation_map_{target}.png")
        _plot_spatial_comparison(target, validation_frame, output_dir / f"validation_compare_{target}.png")
        _plot_station_timeseries(target, validation_frame, output_dir / f"validation_timeseries_{target}.png")
        _plot_mean_error_map(target, validation_frame, output_dir / f"validation_mean_error_{target}.png")
        summary_rows.append(metrics)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(output_dir / "validation_metrics.csv", index=False)
    _plot_metric_bars(summary, output_dir / "validation_metrics.png")
    print(summary.to_string(index=False))
    print(f"Saved validation outputs to {output_dir}")


if __name__ == "__main__":
    main()