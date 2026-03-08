from __future__ import annotations

import argparse
from collections.abc import Iterable
import os
from pathlib import Path
from urllib.request import urlretrieve
import zipfile

import cdsapi
from dotenv import load_dotenv
from fmiopendata.wfs import download_stored_query
import pandas as pd
import planetary_computer
from pystac_client import Client
import rasterio
from rasterio.merge import merge
import xarray as xr

from sim.common import ensure_directories, standardize_cams_dataset
from sim.data_in.fmi_fetcher import align_silam_to_ecmwf, fetch_silam_pm25
from sim.config import BoundingBox, FmiStoredQueryConfig, SimulationConfig, load_config


DEFAULT_CDS_URL = "https://cds.climate.copernicus.eu/api"
DEFAULT_ADS_URL = "https://ads.atmosphere.copernicus.eu/api"
FMI_MAX_HOURS = 168

CAMS_MODEL_ALIASES = {
    "ensemble_median": "ensemble",
}

HOURLY_FILE_RE = "{prefix}_{timestamp:%Y%m%dT%H00Z}.nc"


def _requires_pm_targets(config: SimulationConfig) -> bool:
    return any(target in {"pm25", "aqi"} for target in config.model.targets)


def _open_combined_dataset(files: list[Path]) -> xr.Dataset:
    datasets = [xr.open_dataset(path) for path in files]
    try:
        return xr.combine_by_coords(datasets, combine_attrs="drop_conflicts").load()
    finally:
        for dataset in datasets:
            dataset.close()


def _daily_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start=start.floor("D"), end=end.floor("D"), freq="D", tz="UTC"))


def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    month_start = pd.Timestamp(year=start.year, month=start.month, day=1, tz="UTC")
    return list(pd.date_range(start=month_start, end=end.floor("D"), freq="MS", tz="UTC"))


def _hourly_timestamps(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start=start, end=end, freq="h", tz="UTC"))


def _hourly_target(output_dir: Path, prefix: str, timestamp: pd.Timestamp) -> Path:
    return output_dir / HOURLY_FILE_RE.format(prefix=prefix, timestamp=timestamp)


def _existing_hourly_targets(output_dir: Path, prefix: str, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    return [_hourly_target(output_dir, prefix, timestamp) for timestamp in _hourly_timestamps(start, end)]


def _time_coord_name(dataset: xr.Dataset) -> str:
    for candidate in ("time", "valid_time"):
        if candidate in dataset.coords or candidate in dataset.dims:
            return candidate
    raise KeyError("Dataset does not contain a supported time coordinate.")


def _write_hourly_files(
    dataset: xr.Dataset,
    output_dir: Path,
    prefix: str,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> list[Path]:
    time_name = _time_coord_name(dataset)
    timestamps = pd.to_datetime(dataset[time_name].values, utc=True)
    created: list[Path] = []

    for index, raw_timestamp in enumerate(timestamps):
        timestamp = pd.Timestamp(raw_timestamp)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp > end:
            continue

        target = _hourly_target(output_dir, prefix, timestamp)
        created.append(target)
        if target.exists():
            continue

        hourly_slice = dataset.isel({time_name: slice(index, index + 1)}).load()
        hourly_slice.to_netcdf(target, engine="netcdf4")

    return created


def _load_dotenv_files(config: SimulationConfig) -> None:
    load_dotenv(config.repo_root / ".env", override=False)
    load_dotenv(config.sim_root / ".env", override=False)


def _build_copernicus_client(
    service_name: str,
    key_env: str,
    default_url: str,
    url_env: str,
) -> cdsapi.Client:
    key = os.getenv(key_env)
    url = os.getenv(url_env, default_url)
    if not key:
        raise RuntimeError(
            f"Missing {service_name} credentials. Set {key_env} in a .env file or environment variables."
        )
    return cdsapi.Client(url=url, key=key)


def download_era5_land(config: SimulationConfig) -> list[Path]:
    era5_dir = config.paths.training_data / "era5_land"
    ensure_directories(era5_dir)
    client = _build_copernicus_client(
        service_name="CDS",
        key_env="PORT26_CDS_KEY",
        default_url=DEFAULT_CDS_URL,
        url_env="PORT26_CDS_URL",
    )
    created: list[Path] = []

    for day_start in _daily_starts(config.time.start, config.time.end):
        day_end = min(day_start + pd.Timedelta(hours=23), config.time.end)
        hourly_targets = _existing_hourly_targets(era5_dir, "era5_land", max(day_start, config.time.start), day_end)
        if hourly_targets and all(target.exists() for target in hourly_targets):
            created.extend(hourly_targets)
            continue

        temp_target = era5_dir / f"era5_land_{day_start:%Y%m%d}.download.nc"
        request = {
            "product_type": "reanalysis",
            "variable": config.era5_land.variables,
            "year": [f"{day_start.year:04d}"],
            "month": [f"{day_start.month:02d}"],
            "day": [f"{day_start.day:02d}"],
            "time": [f"{timestamp.hour:02d}:00" for timestamp in _hourly_timestamps(max(day_start, config.time.start), day_end)],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": config.bbox.as_cds_area(),
        }
        client.retrieve(config.era5_land.dataset, request, str(temp_target))
        with xr.open_dataset(temp_target) as dataset:
            created.extend(_write_hourly_files(dataset, era5_dir, "era5_land"))
        temp_target.unlink(missing_ok=True)
    return created


def download_cams_europe(config: SimulationConfig) -> list[Path]:
    cams_dir = config.paths.training_data / "cams_europe"
    ensure_directories(cams_dir)
    client = _build_copernicus_client(
        service_name="ADS",
        key_env="PORT26_ADS_KEY",
        default_url=config.cams_europe.url or DEFAULT_ADS_URL,
        url_env="PORT26_ADS_URL",
    )
    created: list[Path] = []

    for month_start in _month_starts(config.time.start, config.time.end):
        month_end = min((month_start + pd.offsets.MonthBegin(1)) - pd.Timedelta(hours=1), config.time.end)
        month_start_clipped = max(month_start, config.time.start)
        hourly_targets = _existing_hourly_targets(cams_dir, "cams_europe", month_start_clipped, month_end)
        if hourly_targets and all(target.exists() for target in hourly_targets):
            created.extend(hourly_targets)
            continue

        temp_target = cams_dir / f"cams_europe_{month_start:%Y_%m}.download"
        temp_dataset_target = cams_dir / f"cams_europe_{month_start:%Y_%m}.tmp.nc"
        request = _build_cams_request(config, client, month_start)
        client.retrieve(config.cams_europe.dataset, request, str(temp_target))

        if zipfile.is_zipfile(temp_target):
            with zipfile.ZipFile(temp_target) as archive:
                members = [member for member in archive.namelist() if member.lower().endswith(".nc")]
                if not members:
                    raise RuntimeError(f"CAMS archive {temp_target.name} did not contain a NetCDF file.")
                with archive.open(members[0]) as source, temp_dataset_target.open("wb") as sink:
                    sink.write(source.read())
        else:
            temp_target.replace(temp_dataset_target)

        with xr.open_dataset(temp_dataset_target) as dataset:
            standardized = standardize_cams_dataset(dataset)
            created.extend(
                _write_hourly_files(
                    standardized,
                    cams_dir,
                    "cams_europe",
                    start=month_start_clipped,
                    end=month_end,
                )
            )

        temp_target.unlink(missing_ok=True)
        temp_dataset_target.unlink(missing_ok=True)

    return created


def _build_cams_request(
    config: SimulationConfig,
    client: cdsapi.Client,
    month_start: pd.Timestamp,
) -> dict[str, list[str]]:
    normalized_model = CAMS_MODEL_ALIASES.get(config.cams_europe.model, config.cams_europe.model)
    base_request: dict[str, list[str]] = {
            "variable": config.cams_europe.variables,
            "model": [normalized_model],
            "level": [config.cams_europe.level],
            "year": [f"{month_start.year:04d}"],
            "month": [f"{month_start.month:02d}"],
        }
    preferred_type = config.cams_europe.type
    request = dict(base_request)
    request["type"] = [preferred_type]

    constraints_client = getattr(client, "client", None)
    if constraints_client is None or not hasattr(constraints_client, "apply_constraints"):
        return request

    try:
        constraints = constraints_client.apply_constraints(config.cams_europe.dataset, request)
    except Exception:
        return request

    valid_types = constraints.get("type") or []
    if not valid_types:
        return request

    if preferred_type in valid_types:
        return request

    fallback_type = next((candidate for candidate in valid_types if candidate != preferred_type), valid_types[0])
    request["type"] = [fallback_type]
    return request


def _fmi_args(config: FmiStoredQueryConfig, bbox: BoundingBox, start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
    args = [
        f"bbox={bbox.as_fmi_bbox()}",
        f"starttime={start.isoformat().replace('+00:00', 'Z')}",
        f"endtime={end.isoformat().replace('+00:00', 'Z')}",
    ]
    if config.use_timeseries:
        args.append("timeseries=True")
    return args


def _fmi_time_windows(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    window_start = start
    while window_start <= end:
        window_end = min(window_start + pd.Timedelta(hours=FMI_MAX_HOURS - 1), end)
        windows.append((window_start, window_end))
        window_start = window_end + pd.Timedelta(hours=1)
    return windows


def _flatten_fmi_timeseries(response: object, query: FmiStoredQueryConfig) -> pd.DataFrame:
    rows: list[dict] = []
    data = getattr(response, "data", {})
    metadata = getattr(response, "location_metadata", {})
    for station_name, station_payload in data.items():
        station_meta = metadata.get(station_name, {})
        timestamps = station_payload.get("times", [])
        for idx, timestamp in enumerate(timestamps):
            row = {
                "timestamp": pd.Timestamp(timestamp, tz="UTC"),
                "station_name": station_name,
                "station_id": station_meta.get("fmisid", station_name),
                "latitude": station_meta.get("latitude"),
                "longitude": station_meta.get("longitude"),
            }
            for canonical_name, source_name in query.parameter_mapping.items():
                source_payload = station_payload.get(source_name, {})
                values = source_payload.get("values", [])
                row[canonical_name] = values[idx] if idx < len(values) else None
            rows.append(row)
    expected_columns = [
        "timestamp",
        "station_name",
        "station_id",
        "latitude",
        "longitude",
        *query.parameter_mapping.keys(),
    ]
    if not rows:
        return pd.DataFrame(columns=expected_columns)
    return pd.DataFrame(rows)


def _download_fmi_frame(
    query: FmiStoredQueryConfig,
    bbox: BoundingBox,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for window_start, window_end in _fmi_time_windows(start, end):
        response = download_stored_query(
            query.query_id,
            args=_fmi_args(query, bbox, window_start, window_end),
        )
        frames.append(_flatten_fmi_timeseries(response, query))

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    if combined.empty:
        return combined

    return combined.drop_duplicates(
        subset=["timestamp", "station_name", "station_id", "latitude", "longitude"],
        keep="last",
    ).reset_index(drop=True)


def download_fmi_observations(config: SimulationConfig) -> Path:
    fmi_dir = config.paths.training_data / "fmi"
    ensure_directories(fmi_dir)
    weather_df = _download_fmi_frame(config.fmi.weather, config.bbox, config.time.start, config.time.end)
    air_quality_df = _download_fmi_frame(config.fmi.air_quality, config.bbox, config.time.start, config.time.end)

    merged = weather_df.merge(
        air_quality_df,
        on=["timestamp", "station_name", "station_id", "latitude", "longitude"],
        how="outer",
        suffixes=("", "_air"),
    )
    target = fmi_dir / "observations.parquet"
    merged.sort_values(["timestamp", "station_id"]).to_parquet(target, index=False)
    return target


def _acag_key(config: SimulationConfig, month_start: pd.Timestamp) -> str:
    return (
        f"{config.acag_pm25.version}-{config.acag_pm25.resolution}/"
        f"{config.acag_pm25.product_code}/{config.acag_pm25.cadence}/{month_start.year:04d}/"
        f"{config.acag_pm25.version}.CNNPM25.{config.acag_pm25.resolution}."
        f"{config.acag_pm25.product_code}.{month_start.year:04d}{month_start.month:02d}-"
        f"{month_start.year:04d}{month_start.month:02d}.nc"
    )


def download_acag_pm25(config: SimulationConfig) -> list[Path]:
    acag_dir = config.paths.training_data / "acag_pm25"
    ensure_directories(acag_dir)
    created: list[Path] = []

    for month_start in _month_starts(config.time.start, config.time.end):
        key = _acag_key(config, month_start)
        target = acag_dir / Path(key).name
        if target.exists():
            created.append(target)
            continue
        urlretrieve(f"{config.acag_pm25.base_url.rstrip('/')}/{key}", target)
        created.append(target)
    return created


def _select_asset(item: object, preferences: Iterable[str]) -> str:
    assets = getattr(item, "assets")
    for key in preferences:
        if key in assets:
            return assets[key].href
    first_key = next(iter(assets))
    return assets[first_key].href


def download_dem(config: SimulationConfig) -> Path:
    dem_dir = config.paths.training_data / "dem"
    ensure_directories(dem_dir)
    target = dem_dir / "cop_dem_30m.tif"
    if target.exists():
        print(f"DEM already present: {target}", flush=True)
        return target

    print("Searching Copernicus DEM tiles...", flush=True)
    client = Client.open(config.dem.stac_api, modifier=planetary_computer.sign_inplace)
    search = client.search(collections=[config.dem.collection], bbox=list(config.bbox.as_rasterio_bounds()))
    items = list(search.items())
    if not items:
        raise RuntimeError("No Copernicus DEM tiles found for configured bounding box.")

    datasets = []
    try:
        for item in items:
            href = _select_asset(item, config.dem.asset_preference)
            datasets.append(rasterio.open(href))
        mosaic, transform = merge(datasets, bounds=config.bbox.as_rasterio_bounds())
        profile = datasets[0].profile.copy()
        profile.update(
            driver="GTiff",
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=transform,
            count=1,
            compress="lzw",
        )
        with rasterio.open(target, "w", **profile) as dst:
            dst.write(mosaic[0], 1)
    finally:
        for dataset in datasets:
            dataset.close()

    return target


def download_silam_pm25(config: SimulationConfig, era5_files: list[Path]) -> tuple[Path, Path, Path]:
    silam_dir = config.paths.training_data / "fmi" / "silam"
    ensure_directories(silam_dir)
    reference_target = silam_dir / "era5_reference.nc"
    reference = _open_combined_dataset(era5_files)
    reference.to_netcdf(reference_target)

    raw_silam_target = silam_dir / (
        f"silam_pm25_{config.time.start:%Y%m%dT%H%M%SZ}_{config.time.end:%Y%m%dT%H%M%SZ}.nc"
    )
    fetch_silam_pm25(
        target=raw_silam_target,
        bbox=config.bbox,
        start=config.time.start,
        end=config.time.end,
        parameter="PM25",
    )
    return align_silam_to_ecmwf(
        silam_path=raw_silam_target,
        ecmwf_path=reference_target,
        bbox=config.bbox,
        output_dir=silam_dir,
        method="linear",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download training data for the downscaling pipeline.")
    parser.add_argument("--config", type=Path, default=None, help="Optional path to sim config TOML.")
    args = parser.parse_args()

    config = load_config(args.config)
    _load_dotenv_files(config)
    ensure_directories(config.paths.training_data, config.paths.processed, config.paths.model_registry, config.paths.output_dir)
    print("Starting ERA5-Land download step...", flush=True)
    era5_files = download_era5_land(config)
    print(f"ERA5-Land step complete: {len(era5_files)} hourly files targeted.", flush=True)
    if _requires_pm_targets(config):
        print("Starting CAMS Europe download step...", flush=True)
        download_cams_europe(config)
        print("CAMS Europe step complete.", flush=True)
    print("Starting FMI observations download step...", flush=True)
    download_fmi_observations(config)
    print("FMI observations step complete.", flush=True)
    print("Starting DEM step...", flush=True)
    download_dem(config)
    print("DEM step complete.", flush=True)
    if _requires_pm_targets(config):
        print("Starting SILAM PM2.5 step...", flush=True)
        download_silam_pm25(config, era5_files)
        print("SILAM PM2.5 step complete.", flush=True)


if __name__ == "__main__":
    main()