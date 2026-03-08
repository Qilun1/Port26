from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

from sim.common import apply_normalization, ensure_directories, read_json, save_json
from sim.config import SimulationConfig, load_config
from sim.models.physics import build_anchor, build_custom_objective


def _split_frame(frame: pd.DataFrame, validation_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = frame.sort_values("timestamp").reset_index(drop=True)
    split_idx = max(1, int(len(ordered) * (1.0 - validation_fraction)))
    split_idx = min(split_idx, len(ordered) - 1)
    return ordered.iloc[:split_idx].copy(), ordered.iloc[split_idx:].copy()


def _target_frame(frame: pd.DataFrame, target: str) -> pd.DataFrame:
    label_column = f"residual_{target}"
    return frame.loc[frame[label_column].notna()].copy()


def _compute_validation_metrics(
    valid_frame: pd.DataFrame,
    target: str,
    baseline_column: str,
    predicted_residual: np.ndarray,
) -> dict[str, float]:
    residual_column = f"residual_{target}"
    observed_residual = valid_frame[residual_column].to_numpy(dtype=float)
    baseline = valid_frame[baseline_column].to_numpy(dtype=float)
    observed = valid_frame[target].to_numpy(dtype=float)
    predicted = baseline + predicted_residual
    baseline_prediction = baseline
    zero_residual = np.zeros_like(observed_residual)

    return {
        "validation_rmse": float(np.sqrt(mean_squared_error(observed, predicted))),
        "validation_mae": float(mean_absolute_error(observed, predicted)),
        "validation_r2": float(r2_score(observed, predicted)),
        "baseline_validation_rmse": float(np.sqrt(mean_squared_error(observed, baseline_prediction))),
        "baseline_validation_mae": float(mean_absolute_error(observed, baseline_prediction)),
        "baseline_validation_r2": float(r2_score(observed, baseline_prediction)),
        "residual_validation_rmse": float(np.sqrt(mean_squared_error(observed_residual, predicted_residual))),
        "residual_validation_mae": float(mean_absolute_error(observed_residual, predicted_residual)),
        "residual_validation_r2": float(r2_score(observed_residual, predicted_residual)),
        "residual_baseline_validation_rmse": float(np.sqrt(mean_squared_error(observed_residual, zero_residual))),
        "residual_baseline_validation_mae": float(mean_absolute_error(observed_residual, zero_residual)),
        "residual_baseline_validation_r2": float(r2_score(observed_residual, zero_residual)),
    }


def _predict_with_best_iteration(booster: xgb.Booster, matrix: xgb.DMatrix) -> np.ndarray:
    best_iteration = getattr(booster, "best_iteration", None)
    if best_iteration is None or best_iteration < 0:
        return booster.predict(matrix)
    return booster.predict(matrix, iteration_range=(0, best_iteration + 1))


def _save_learning_curve(
    target: str,
    evals_result: dict[str, dict[str, list[float]]],
    artifact_dir: Path,
    best_iteration: int,
) -> tuple[Path, Path]:
    train_rmse = evals_result.get("train", {}).get("rmse", [])
    valid_rmse = evals_result.get("valid", {}).get("rmse", [])
    curve_frame = pd.DataFrame(
        {
            "iteration": np.arange(len(train_rmse), dtype=int),
            "train_rmse": train_rmse,
            "valid_rmse": valid_rmse,
        }
    )

    csv_path = artifact_dir / f"{target}_learning_curve.csv"
    png_path = artifact_dir / f"{target}_learning_curve.png"
    curve_frame.to_csv(csv_path, index=False)

    fig, axis = plt.subplots(figsize=(8, 5))
    axis.plot(curve_frame["iteration"], curve_frame["train_rmse"], label="train rmse", linewidth=1.8)
    axis.plot(curve_frame["iteration"], curve_frame["valid_rmse"], label="valid rmse", linewidth=1.8)
    axis.axvline(best_iteration, color="black", linestyle="--", linewidth=1.0, label=f"best iter {best_iteration}")
    axis.set_title(f"XGBoost learning curve: {target}")
    axis.set_xlabel("Boosting iteration")
    axis.set_ylabel("RMSE")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    plt.tight_layout()
    fig.savefig(png_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return csv_path, png_path


def _train_single_target(
    frame: pd.DataFrame,
    target: str,
    baseline_column: str,
    feature_columns: list[str],
    config: SimulationConfig,
    artifact_dir: Path,
    normalization_stats: dict[str, dict[str, float]],
) -> dict:
    label_column = f"residual_{target}"
    filtered = _target_frame(frame, target)
    if len(filtered) < 32:
        return {"target": target, "skipped": True, "reason": "Not enough labelled samples."}

    train_frame, valid_frame = _split_frame(filtered, config.model.validation_fraction)
    train_features = apply_normalization(train_frame, normalization_stats, feature_columns)
    valid_features = apply_normalization(valid_frame, normalization_stats, feature_columns)
    train_matrix = xgb.DMatrix(train_features[feature_columns], label=train_frame[label_column])
    valid_matrix = xgb.DMatrix(valid_features[feature_columns], label=valid_frame[label_column])

    train_anchor = build_anchor(
        train_frame,
        target,
        config.model.temperature_lapse_rate_c_per_m,
        config.model.pressure_scale_height_m,
    )
    params = {
        "eta": config.model.learning_rate,
        "max_depth": config.model.max_depth,
        "subsample": config.model.subsample,
        "colsample_bytree": config.model.colsample_bytree,
        "objective": "reg:squarederror",
        "eval_metric": "rmse",
        "tree_method": "hist",
        "seed": 42,
    }
    evals_result: dict[str, dict[str, list[float]]] = {}
    booster = xgb.train(
        params=params,
        dtrain=train_matrix,
        num_boost_round=config.model.num_boost_round,
        evals=[(train_matrix, "train"), (valid_matrix, "valid")],
        obj=build_custom_objective(train_anchor, config.model.physics_lambda),
        early_stopping_rounds=config.model.early_stopping_rounds,
        evals_result=evals_result,
        verbose_eval=False,
    )

    predictions = _predict_with_best_iteration(booster, valid_matrix)
    validation_metrics = _compute_validation_metrics(
        valid_frame=valid_frame,
        target=target,
        baseline_column=baseline_column,
        predicted_residual=predictions,
    )
    target_path = artifact_dir / f"{target}.json"
    booster.save_model(target_path)
    curve_csv_path, curve_png_path = _save_learning_curve(
        target=target,
        evals_result=evals_result,
        artifact_dir=artifact_dir,
        best_iteration=int(booster.best_iteration),
    )
    return {
        "target": target,
        "skipped": False,
        "samples": len(filtered),
        "train_samples": len(train_frame),
        "validation_samples": len(valid_frame),
        **validation_metrics,
        "rmse_improvement_vs_baseline": validation_metrics["baseline_validation_rmse"] - validation_metrics["validation_rmse"],
        "model_path": str(target_path),
        "learning_curve_csv": str(curve_csv_path),
        "learning_curve_png": str(curve_png_path),
        "best_iteration": int(booster.best_iteration),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train XGBoost residual downscaling models.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    args = parser.parse_args()

    config = load_config(args.config)
    ensure_directories(config.paths.model_registry)
    processed_dir = config.paths.processed
    training_frame = pd.read_parquet(processed_dir / "station_training_raw.parquet")
    metadata = read_json(processed_dir / "metadata.json")
    normalization_stats = read_json(processed_dir / "normalization.json")
    feature_columns = metadata["feature_columns"]

    metrics = []
    for target in config.model.targets:
        metrics.append(
            _train_single_target(
                frame=training_frame,
                target=target,
                baseline_column=metadata["target_baselines"][target],
                feature_columns=feature_columns,
                config=config,
                artifact_dir=config.paths.model_registry,
                normalization_stats=normalization_stats,
            )
        )

    save_json(
        {
            "feature_columns": feature_columns,
            "targets": config.model.targets,
            "metrics": metrics,
            "target_baselines": metadata["target_baselines"],
        },
        config.paths.model_registry / "registry.json",
    )


if __name__ == "__main__":
    main()