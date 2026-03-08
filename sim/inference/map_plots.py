from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any

from matplotlib.axes import Axes
from matplotlib.image import AxesImage
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    ctx: Any | None = importlib.import_module("contextily")
except ImportError:
    ctx = None

from sim.common import ensure_directories, read_dem_raster


WEB_MERCATOR_LIMIT = 85.05112878
EARTH_RADIUS_METERS = 6_378_137.0
TARGET_UNITS = {
    "temperature": "degC",
    "pressure": "hPa",
    "u10": "m/s",
    "v10": "m/s",
    "pm25": "ug/m^3",
    "aqi": "AQI",
}
TARGET_DESCRIPTIONS = {
    "temperature": "Temperature",
    "pressure": "Surface pressure",
    "u10": "10 m U wind",
    "v10": "10 m V wind",
    "pm25": "PM2.5",
    "aqi": "Air quality index",
}


@dataclass(frozen=True)
class DemPlotContext:
    surface: np.ndarray
    extent: tuple[float, float, float, float]
    projected_extent: tuple[float, float, float, float]


def _project_lonlat(lon: np.ndarray | float, lat: np.ndarray | float) -> tuple[np.ndarray, np.ndarray] | tuple[float, float]:
    lon_array = np.asarray(lon, dtype=float)
    lat_array = np.asarray(lat, dtype=float)
    clipped_lat = np.clip(lat_array, -WEB_MERCATOR_LIMIT, WEB_MERCATOR_LIMIT)
    x = EARTH_RADIUS_METERS * np.radians(lon_array)
    y = EARTH_RADIUS_METERS * np.log(np.tan((np.pi / 4.0) + (np.radians(clipped_lat) / 2.0)))
    if np.isscalar(lon) and np.isscalar(lat):
        return float(x), float(y)
    return x, y


def _project_extent(extent: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    min_lon, max_lon, min_lat, max_lat = extent
    min_x, min_y = _project_lonlat(min_lon, min_lat)
    max_x, max_y = _project_lonlat(max_lon, max_lat)
    return float(min_x), float(max_x), float(min_y), float(max_y)


def _build_dem_plot_context(dem_path: Path) -> DemPlotContext:
    dem, transform, profile = read_dem_raster(dem_path)
    surface = dem.astype(float)
    nodata = profile.get("nodata")
    if nodata is not None:
        surface = np.where(np.isclose(surface, nodata), np.nan, surface)

    valid = np.isfinite(surface)
    if not valid.any():
        raise ValueError(f"DEM at {dem_path} did not contain any finite values.")

    min_lon = transform.c
    max_lon = transform.c + transform.a * surface.shape[1]
    max_lat = transform.f
    min_lat = transform.f + transform.e * surface.shape[0]
    extent = (min_lon, max_lon, min_lat, max_lat)
    return DemPlotContext(
        surface=surface,
        extent=extent,
        projected_extent=_project_extent(extent),
    )


def _raster_from_grid(frame: pd.DataFrame, value_column: str) -> np.ma.MaskedArray:
    unique_rows = np.sort(frame["row"].unique())
    unique_cols = np.sort(frame["col"].unique())
    row_lookup = {int(row): index for index, row in enumerate(unique_rows)}
    col_lookup = {int(col): index for index, col in enumerate(unique_cols)}
    raster = np.full((len(unique_rows), len(unique_cols)), np.nan, dtype=float)

    rows = frame["row"].to_numpy(dtype=int)
    cols = frame["col"].to_numpy(dtype=int)
    values = frame[value_column].to_numpy(dtype=float)
    for row, col, value in zip(rows, cols, values, strict=False):
        raster[row_lookup[row], col_lookup[col]] = value
    return np.ma.masked_invalid(raster)


def _apply_plot_bounds(axis: Axes, extent: tuple[float, float, float, float], clip_bounds: tuple[float, float, float, float] | None) -> None:
    bounds = clip_bounds if clip_bounds is not None else extent
    min_x, max_x, min_y, max_y = _project_extent(bounds)
    axis.set_xlim(min_x, max_x)
    axis.set_ylim(min_y, max_y)


def _add_simple_basemap(axis: Axes) -> None:
    axis.set_facecolor("#eef2f7")
    if ctx is None:
        return

    try:
        ctx.add_basemap(
            axis,
            source=ctx.providers.CartoDB.PositronNoLabels,
            attribution=False,
            zoom="auto",
            interpolation="bilinear",
        )
    except Exception:
        return


def _plot_reference_underlay(axis: Axes, dem_context: DemPlotContext) -> None:
    _add_simple_basemap(axis)
    for spine in axis.spines.values():
        spine.set_color("#334155")
        spine.set_linewidth(1.0)


def _target_unit(target: str) -> str:
    return TARGET_UNITS.get(target, "value")


def _target_description(target: str) -> str:
    return TARGET_DESCRIPTIONS.get(target, target)


def _difference_scale(frame: pd.DataFrame, baseline_column: str, predicted_column: str) -> tuple[float, float] | None:
    values = (frame[predicted_column] - frame[baseline_column]).dropna()
    if values.empty:
        return None
    magnitude = float(np.nanmax(np.abs(values.to_numpy(dtype=float))))
    if np.isclose(magnitude, 0.0):
        magnitude = 1.0
    return -magnitude, magnitude


def _plot_raster_panel(
    axis: Axes,
    frame: pd.DataFrame,
    value_column: str,
    title: str,
    dem_context: DemPlotContext,
    clip_bounds: tuple[float, float, float, float] | None,
    *,
    vmin: float,
    vmax: float,
) -> AxesImage:
    _plot_reference_underlay(axis, dem_context)
    raster = _raster_from_grid(frame, value_column)
    mappable = axis.imshow(
        raster,
        extent=dem_context.projected_extent,
        origin="upper",
        cmap="coolwarm",
        alpha=0.68,
        interpolation="nearest",
        zorder=1,
        vmin=vmin,
        vmax=vmax,
    )
    axis.set_title(title)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_aspect("equal")
    _apply_plot_bounds(axis, dem_context.extent, clip_bounds)
    return mappable


def _plot_difference_panel(
    axis: Axes,
    frame: pd.DataFrame,
    baseline_column: str,
    predicted_column: str,
    title: str,
    dem_context: DemPlotContext,
    clip_bounds: tuple[float, float, float, float] | None,
    *,
    vmin: float,
    vmax: float,
) -> AxesImage:
    _plot_reference_underlay(axis, dem_context)
    diff_frame = frame.copy()
    diff_frame["plot_difference"] = frame[predicted_column] - frame[baseline_column]
    raster = _raster_from_grid(diff_frame, "plot_difference")
    mappable = axis.imshow(
        raster,
        extent=dem_context.projected_extent,
        origin="upper",
        cmap="RdBu_r",
        alpha=0.72,
        interpolation="nearest",
        zorder=1,
        vmin=vmin,
        vmax=vmax,
    )
    axis.set_title(title)
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_aspect("equal")
    _apply_plot_bounds(axis, dem_context.extent, clip_bounds)
    return mappable


def _plot_dem_panel(
    axis: Axes,
    dem_context: DemPlotContext,
    clip_bounds: tuple[float, float, float, float] | None,
) -> AxesImage:
    _plot_reference_underlay(axis, dem_context)
    dem_raster = np.ma.masked_invalid(dem_context.surface)
    mappable = axis.imshow(
        dem_raster,
        extent=dem_context.projected_extent,
        origin="upper",
        cmap="terrain",
        alpha=0.58,
        interpolation="bilinear",
        zorder=1,
    )
    axis.set_title("DEM elevation reference")
    axis.set_xticks([])
    axis.set_yticks([])
    axis.set_aspect("equal")
    _apply_plot_bounds(axis, dem_context.extent, clip_bounds)
    return mappable


def _shared_scale(frame: pd.DataFrame, baseline_column: str, predicted_column: str) -> tuple[float, float] | None:
    values = pd.concat([frame[baseline_column], frame[predicted_column]], axis=0).dropna()
    if values.empty:
        return None
    vmin = float(values.min())
    vmax = float(values.max())
    if np.isclose(vmin, vmax):
        pad = 1.0 if np.isclose(vmin, 0.0) else abs(vmin) * 0.05
        vmin -= pad
        vmax += pad
    return vmin, vmax


def save_multi_target_comparison_map(
    frame: pd.DataFrame,
    targets: list[str],
    timestamp: pd.Timestamp,
    output_path: Path,
    *,
    label: str,
    dem_path: Path,
    clip_bounds: tuple[float, float, float, float] | None = None,
    baseline_label: str = "ERA5-Land baseline",
) -> Path | None:
    valid_targets = [
        target
        for target in targets
        if f"coarse_{target}" in frame.columns and f"predicted_{target}" in frame.columns
    ]
    if not valid_targets:
        return None

    dem_context = _build_dem_plot_context(dem_path)
    fig, axes = plt.subplots(len(valid_targets), 4, figsize=(22, max(5, 4.8 * len(valid_targets))), squeeze=False)

    for row_index, target in enumerate(valid_targets):
        baseline_column = f"coarse_{target}"
        predicted_column = f"predicted_{target}"
        scale = _shared_scale(frame, baseline_column, predicted_column)
        diff_scale = _difference_scale(frame, baseline_column, predicted_column)
        if scale is None or diff_scale is None:
            axes[row_index, 0].axis("off")
            axes[row_index, 1].axis("off")
            axes[row_index, 2].axis("off")
            axes[row_index, 3].axis("off")
            continue

        unit = _target_unit(target)
        target_label = _target_description(target)
        vmin, vmax = scale
        diff_vmin, diff_vmax = diff_scale
        value_mappable = _plot_raster_panel(
            axes[row_index, 0],
            frame,
            baseline_column,
            f"{baseline_label}: {target_label}",
            dem_context,
            clip_bounds,
            vmin=vmin,
            vmax=vmax,
        )
        _plot_raster_panel(
            axes[row_index, 1],
            frame,
            predicted_column,
            f"SR model: {target_label}",
            dem_context,
            clip_bounds,
            vmin=vmin,
            vmax=vmax,
        )
        diff_mappable = _plot_difference_panel(
            axes[row_index, 2],
            frame,
            baseline_column,
            predicted_column,
            f"SR correction over baseline: {target_label}",
            dem_context,
            clip_bounds,
            vmin=diff_vmin,
            vmax=diff_vmax,
        )
        dem_mappable = _plot_dem_panel(axes[row_index, 3], dem_context, clip_bounds)

        value_colorbar = fig.colorbar(value_mappable, ax=axes[row_index, :2].tolist(), fraction=0.025, pad=0.015)
        value_colorbar.set_label(f"Absolute value [{unit}]", fontsize=8)
        value_colorbar.ax.tick_params(labelsize=8)

        diff_colorbar = fig.colorbar(diff_mappable, ax=[axes[row_index, 2]], fraction=0.046, pad=0.02)
        diff_colorbar.set_label(f"Model increment SR - baseline [{unit}]", fontsize=8)
        diff_colorbar.ax.tick_params(labelsize=8)

        dem_colorbar = fig.colorbar(dem_mappable, ax=[axes[row_index, 3]], fraction=0.046, pad=0.02)
        dem_colorbar.set_label("Elevation [m]", fontsize=8)
        dem_colorbar.ax.tick_params(labelsize=8)

    fig.suptitle(
        f"{label} baseline vs SR at {timestamp.isoformat()}\n"
        "Value colorbars show absolute physical values, not normalized features. The third panel shows the model increment relative to the coarse field, not error versus truth.",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.04, right=0.96, bottom=0.05, top=0.92, wspace=0.08, hspace=0.24)
    fig.savefig(output_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    return output_path


def save_single_target_comparison_maps(
    frame: pd.DataFrame,
    targets: list[str],
    timestamp: pd.Timestamp,
    output_dir: Path,
    *,
    dem_path: Path,
    clip_bounds: tuple[float, float, float, float] | None = None,
    baseline_label: str = "Coarse baseline",
    file_prefix: str = "compare",
) -> list[Path]:
    ensure_directories(output_dir)
    dem_context = _build_dem_plot_context(dem_path)
    written: list[Path] = []

    for target in targets:
        baseline_column = f"coarse_{target}"
        predicted_column = f"predicted_{target}"
        if baseline_column not in frame.columns or predicted_column not in frame.columns:
            continue

        scale = _shared_scale(frame, baseline_column, predicted_column)
        if scale is None:
            continue
        vmin, vmax = scale

        diff_scale = _difference_scale(frame, baseline_column, predicted_column)
        if diff_scale is None:
            continue

        unit = _target_unit(target)
        target_label = _target_description(target)
        diff_vmin, diff_vmax = diff_scale

        fig, axes = plt.subplots(1, 4, figsize=(22, 5.4))
        value_mappable = _plot_raster_panel(
            axes[0],
            frame,
            baseline_column,
            f"{baseline_label}: {target_label}",
            dem_context,
            clip_bounds,
            vmin=vmin,
            vmax=vmax,
        )
        _plot_raster_panel(
            axes[1],
            frame,
            predicted_column,
            f"SR model: {target_label}",
            dem_context,
            clip_bounds,
            vmin=vmin,
            vmax=vmax,
        )
        diff_mappable = _plot_difference_panel(
            axes[2],
            frame,
            baseline_column,
            predicted_column,
            f"SR correction over baseline: {target_label}",
            dem_context,
            clip_bounds,
            vmin=diff_vmin,
            vmax=diff_vmax,
        )
        dem_mappable = _plot_dem_panel(axes[3], dem_context, clip_bounds)

        value_colorbar = fig.colorbar(value_mappable, ax=axes[:2].tolist(), fraction=0.025, pad=0.015)
        value_colorbar.set_label(f"Absolute value [{unit}]", fontsize=8)
        value_colorbar.ax.tick_params(labelsize=8)

        diff_colorbar = fig.colorbar(diff_mappable, ax=[axes[2]], fraction=0.046, pad=0.02)
        diff_colorbar.set_label(f"Model increment SR - baseline [{unit}]", fontsize=8)
        diff_colorbar.ax.tick_params(labelsize=8)

        dem_colorbar = fig.colorbar(dem_mappable, ax=[axes[3]], fraction=0.046, pad=0.02)
        dem_colorbar.set_label("Elevation [m]", fontsize=8)
        dem_colorbar.ax.tick_params(labelsize=8)

        fig.suptitle(
            f"Baseline vs SR at {timestamp.isoformat()}\n"
            "Value colorbars show absolute physical values, not normalized features. The third panel shows the model increment relative to the coarse field, not error versus truth.",
        )
        fig.subplots_adjust(left=0.04, right=0.96, bottom=0.08, top=0.88, wspace=0.08)

        output_path = output_dir / f"{file_prefix}_{target}_{timestamp:%Y%m%dT%H%M%SZ}.png"
        fig.savefig(output_path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        written.append(output_path)

    return written