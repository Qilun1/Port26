from __future__ import annotations

import numpy as np
import pandas as pd
import xgboost as xgb


def temperature_physics_anchor(elevation_delta: np.ndarray, lapse_rate_c_per_m: float) -> np.ndarray:
    return -lapse_rate_c_per_m * elevation_delta


def pressure_physics_anchor(
    coarse_pressure_hpa: np.ndarray,
    elevation_delta: np.ndarray,
    scale_height_m: float,
) -> np.ndarray:
    return coarse_pressure_hpa * (np.exp(-elevation_delta / scale_height_m) - 1.0)


def build_anchor(frame: pd.DataFrame, target: str, lapse_rate_c_per_m: float, scale_height_m: float) -> np.ndarray:
    if target == "temperature":
        return temperature_physics_anchor(frame["elevation_delta"].to_numpy(dtype=float), lapse_rate_c_per_m)
    if target == "pressure":
        return pressure_physics_anchor(
            frame["coarse_pressure"].to_numpy(dtype=float),
            frame["elevation_delta"].to_numpy(dtype=float),
            scale_height_m,
        )
    if target in {"u10", "v10"}:
        return np.zeros(len(frame), dtype=float)
    return np.zeros(len(frame), dtype=float)


def build_custom_objective(anchor: np.ndarray, physics_lambda: float):
    def objective(predt: np.ndarray, dtrain: xgb.DMatrix) -> tuple[np.ndarray, np.ndarray]:
        labels = dtrain.get_label()
        grad = (predt - labels) + physics_lambda * (predt - anchor)
        hess = np.ones_like(predt) * (1.0 + physics_lambda)
        return grad, hess

    return objective