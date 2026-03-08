from __future__ import annotations

import argparse
from pathlib import Path

from fmiopendata.wfs import download_stored_query
import pandas as pd
import xarray as xr

from sim.common import ensure_directories
from sim.config import BoundingBox, load_config


SILAM_QUERY_ID = "fmi::forecast::silam::airquality::surface::grid"
FINLAND_BBOX = BoundingBox(min_lon=19.0, max_lon=32.0, min_lat=59.0, max_lat=71.5)
PM25_ALIASES = (
    "PM25",
    "pm25",
    "PM2.5",
    "pm2p5",
    "particulate_matter_2.5um",
)


def _to_utc_timestamp(raw: str | None) -> pd.Timestamp | None:
    if raw is None:
        return None
    timestamp = pd.Timestamp(raw)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _as_fmi_time(raw: pd.Timestamp) -> str:
    return raw.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def _find_name(candidates: list[str], names: list[str]) -> str | None:
    lowered = {name.lower(): name for name in names}
    for candidate in candidates:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return None


def _normalize_rectilinear_coords(dataset: xr.Dataset) -> xr.Dataset:
    coord_names = list(dataset.coords)
    data_var_names = list(dataset.data_vars)
    available_names = coord_names + data_var_names

    rename_map: dict[str, str] = {}
    latitude_name = _find_name(["latitude", "lat"], available_names)
    longitude_name = _find_name(["longitude", "lon"], available_names)
    time_name = _find_name(["time", "valid_time"], available_names)

    if latitude_name is not None and latitude_name != "latitude":
        rename_map[latitude_name] = "latitude"
    if longitude_name is not None and longitude_name != "longitude":
        rename_map[longitude_name] = "longitude"
    if time_name is not None and time_name != "time":
        rename_map[time_name] = "time"

    normalized = dataset.rename(rename_map)

    if "latitude" not in normalized.coords and "latitude" in normalized:
        normalized = normalized.set_coords("latitude")
    if "longitude" not in normalized.coords and "longitude" in normalized:
        normalized = normalized.set_coords("longitude")
    if "time" not in normalized.coords and "time" in normalized:
        normalized = normalized.set_coords("time")

    if "latitude" in normalized.coords and "longitude" in normalized.coords:
        latitude = normalized["latitude"]
        longitude = normalized["longitude"]
        if latitude.ndim == 2 and longitude.ndim == 2:
            latitude_dim, longitude_dim = latitude.dims
            if latitude_dim == longitude_dim:
                raise ValueError("Could not infer separate spatial dimensions from 2D latitude/longitude coordinates.")
            lat_1d = latitude.isel({longitude_dim: 0})
            lon_1d = longitude.isel({latitude_dim: 0})
            if lat_1d.ndim != 1 or lon_1d.ndim != 1:
                raise ValueError("Only rectilinear 2D latitude/longitude grids are supported.")
            normalized = normalized.assign_coords({latitude_dim: lat_1d.to_numpy(), longitude_dim: lon_1d.to_numpy()})
            normalized = normalized.rename({latitude_dim: "latitude", longitude_dim: "longitude"})
            normalized = normalized.drop_vars([name for name in ["latitude", "longitude"] if name in normalized.data_vars], errors="ignore")

    if "latitude" not in normalized.dims or "longitude" not in normalized.dims:
        raise ValueError("Dataset must expose rectilinear latitude and longitude dimensions for xarray interpolation.")

    normalized = normalized.sortby("latitude")
    normalized = normalized.sortby("longitude")
    if "time" in normalized.coords:
        normalized = normalized.sortby("time")
    return normalized


def _subset_bbox(dataset: xr.Dataset, bbox: BoundingBox) -> xr.Dataset:
    subset = dataset.sel(latitude=slice(bbox.min_lat, bbox.max_lat), longitude=slice(bbox.min_lon, bbox.max_lon))
    if subset.sizes.get("latitude", 0) == 0 or subset.sizes.get("longitude", 0) == 0:
        raise ValueError("Requested Finland bounding box does not overlap the dataset grid.")
    return subset


def _pick_pm25_variable(dataset: xr.Dataset) -> str:
    data_vars = list(dataset.data_vars)
    exact = _find_name(list(PM25_ALIASES), data_vars)
    if exact is not None:
        return exact

    lowered = {name.lower(): name for name in data_vars}
    for key, original in lowered.items():
        if "pm25" in key or "pm2p5" in key or "pm2.5" in key:
            return original

    raise ValueError(f"Could not find a PM2.5 variable in SILAM file. Available variables: {data_vars}")


def open_ecmwf_reference(path: Path, bbox: BoundingBox) -> xr.Dataset:
    dataset = xr.open_dataset(path)
    normalized = _normalize_rectilinear_coords(dataset)
    return _subset_bbox(normalized, bbox)


def _derive_request_window(ecmwf_dataset: xr.Dataset, start: pd.Timestamp | None, end: pd.Timestamp | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    if start is not None and end is not None:
        return start, end
    if "time" not in ecmwf_dataset.coords:
        raise ValueError("ECMWF dataset has no time coordinate. Pass --start and --end explicitly.")

    ecmwf_times = pd.to_datetime(ecmwf_dataset["time"].to_numpy(), utc=True)
    derived_start = ecmwf_times.min()
    derived_end = ecmwf_times.max()
    return start or derived_start, end or derived_end


def open_aligned_silam(path: Path, bbox: BoundingBox) -> xr.Dataset:
    dataset = xr.open_dataset(path)
    normalized = _normalize_rectilinear_coords(dataset)
    subset = _subset_bbox(normalized, bbox)
    if "silam_pm25" in subset.data_vars:
        return subset[["silam_pm25"]]
    pm25_name = _pick_pm25_variable(subset)
    return subset[[pm25_name]].rename({pm25_name: "silam_pm25"})


def fetch_silam_pm25(
    target: Path,
    bbox: BoundingBox,
    start: pd.Timestamp,
    end: pd.Timestamp,
    parameter: str,
) -> Path:
    response = download_stored_query(
        SILAM_QUERY_ID,
        args=[
            f"starttime={_as_fmi_time(start)}",
            f"endtime={_as_fmi_time(end)}",
            f"bbox={bbox.as_fmi_bbox()}",
            f"parameters={parameter}",
        ],
    )
    if not response.data:
        raise RuntimeError("FMI SILAM request returned no grid runs for the requested time window.")

    latest_run = max(response.data)
    grid = response.data[latest_run]
    grid.download(str(target))
    return target


def align_silam_to_ecmwf(
    silam_path: Path,
    ecmwf_path: Path,
    bbox: BoundingBox,
    output_dir: Path,
    method: str,
) -> tuple[Path, Path, Path]:
    ensure_directories(output_dir)

    ecmwf_reference = open_ecmwf_reference(ecmwf_path, bbox)
    silam_pm25 = open_aligned_silam(silam_path, bbox)

    interp_kwargs = {
        "latitude": ecmwf_reference["latitude"],
        "longitude": ecmwf_reference["longitude"],
    }
    if "time" in silam_pm25.coords and "time" in ecmwf_reference.coords:
        interp_kwargs["time"] = ecmwf_reference["time"]

    silam_aligned = silam_pm25.interp(method=method, kwargs={"fill_value": "extrapolate"}, **interp_kwargs)
    ecmwf_aligned = ecmwf_reference

    merged = xr.merge([ecmwf_aligned, silam_aligned], compat="override")

    silam_target = output_dir / "silam_pm25_aligned.nc"
    ecmwf_target = output_dir / "ecmwf_weather_aligned.nc"
    merged_target = output_dir / "silam_ecmwf_shared_grid.nc"
    silam_aligned.to_netcdf(silam_target)
    ecmwf_aligned.to_netcdf(ecmwf_target)
    merged.to_netcdf(merged_target)
    return silam_target, ecmwf_target, merged_target


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch hourly FMI SILAM PM2.5 grids and align them to an ECMWF NetCDF grid.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    parser.add_argument("--ecmwf-file", type=Path, required=True, help="NetCDF file containing the ECMWF weather grid.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for the raw SILAM and aligned NetCDF outputs.")
    parser.add_argument("--start", type=str, default=None, help="Optional UTC start time. Defaults to the first ECMWF timestep.")
    parser.add_argument("--end", type=str, default=None, help="Optional UTC end time. Defaults to the last ECMWF timestep.")
    parser.add_argument("--min-lon", type=float, default=FINLAND_BBOX.min_lon, help="Finland bounding box minimum longitude.")
    parser.add_argument("--max-lon", type=float, default=FINLAND_BBOX.max_lon, help="Finland bounding box maximum longitude.")
    parser.add_argument("--min-lat", type=float, default=FINLAND_BBOX.min_lat, help="Finland bounding box minimum latitude.")
    parser.add_argument("--max-lat", type=float, default=FINLAND_BBOX.max_lat, help="Finland bounding box maximum latitude.")
    parser.add_argument("--silam-parameter", type=str, default="PM25", help="SILAM parameter name to request from FMI.")
    parser.add_argument("--interp-method", type=str, default="linear", choices=["linear", "nearest"], help="xarray interpolation method for regridding SILAM to the ECMWF grid.")
    args = parser.parse_args()

    config = load_config(args.config)
    bbox = BoundingBox(
        min_lon=args.min_lon,
        max_lon=args.max_lon,
        min_lat=args.min_lat,
        max_lat=args.max_lat,
    )
    output_dir = args.output_dir or (config.paths.training_data / "fmi" / "silam")
    ensure_directories(output_dir)

    requested_start = _to_utc_timestamp(args.start)
    requested_end = _to_utc_timestamp(args.end)
    ecmwf_reference = open_ecmwf_reference(args.ecmwf_file, bbox)
    request_start, request_end = _derive_request_window(ecmwf_reference, requested_start, requested_end)

    raw_silam_path = output_dir / f"silam_pm25_{request_start:%Y%m%dT%H%M%SZ}_{request_end:%Y%m%dT%H%M%SZ}.nc"
    fetch_silam_pm25(
        target=raw_silam_path,
        bbox=bbox,
        start=request_start,
        end=request_end,
        parameter=args.silam_parameter,
    )
    align_silam_to_ecmwf(
        silam_path=raw_silam_path,
        ecmwf_path=args.ecmwf_file,
        bbox=bbox,
        output_dir=output_dir,
        method=args.interp_method,
    )


if __name__ == "__main__":
    main()