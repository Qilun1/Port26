from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from ecmwf.opendata import Client
import pandas as pd
import xarray as xr

from sim.common import coerce_pressure_to_hpa, ensure_directories, wind_speed_direction_to_uv
from sim.config import BoundingBox, FmiStoredQueryConfig
from sim.data_in.download_training_data import _download_fmi_frame


IFS_PARAMETER_MAP = {
    "2t": "coarse_temperature",
    "sp": "coarse_pressure",
    "10u": "coarse_u10",
    "10v": "coarse_v10",
}

IFS_VARIABLE_ALIASES = {
    "t2m": "coarse_temperature",
    "sp": "coarse_pressure",
    "u10": "coarse_u10",
    "v10": "coarse_v10",
    "2t": "coarse_temperature",
    "10u": "coarse_u10",
    "10v": "coarse_v10",
}

FMI_WEATHER_QUERY = FmiStoredQueryConfig(
    query_id="fmi::observations::weather::multipointcoverage",
    use_timeseries=True,
    parameter_mapping={
        "temperature": "Air temperature",
        "pressure": "Pressure",
        "wind_speed": "Wind speed",
        "wind_direction": "Wind direction",
    },
)


@dataclass(frozen=True)
class IfsSnapshotResult:
    run_timestamp: pd.Timestamp
    coarse_path: Path
    raw_grib_paths: list[Path]


@dataclass(frozen=True)
class FmiSnapshotResult:
    station_timestamp: pd.Timestamp
    station_path: Path


def _to_utc_timestamp(raw: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if raw is None:
        return None
    timestamp = pd.Timestamp(raw)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _normalize_longitudes(frame: pd.DataFrame) -> pd.DataFrame:
    if "longitude" not in frame.columns:
        return frame
    result = frame.copy()
    result["longitude"] = ((result["longitude"] + 180.0) % 360.0) - 180.0
    return result


def _subset_bbox(frame: pd.DataFrame, bbox: BoundingBox) -> pd.DataFrame:
    return frame.loc[
        frame["longitude"].between(bbox.min_lon, bbox.max_lon)
        & frame["latitude"].between(bbox.min_lat, bbox.max_lat)
    ].copy()


def _open_grib_field(path: Path) -> xr.Dataset:
    dataset = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    try:
        return dataset.load()
    finally:
        dataset.close()


def _field_to_frame(dataset: xr.Dataset) -> pd.DataFrame:
    data_var_name = next(iter(dataset.data_vars))
    data_var_name_str = str(data_var_name)
    rename_map = {
        str(name): IFS_VARIABLE_ALIASES[str(name)]
        for name in dataset.data_vars
        if str(name) in IFS_VARIABLE_ALIASES
    }
    frame = dataset.rename(rename_map).to_dataframe().reset_index()
    frame = _normalize_longitudes(frame)

    if "valid_time" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["valid_time"], utc=True)
    elif "time" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["time"], utc=True)
    else:
        raise ValueError(f"IFS field {data_var_name} had no time coordinate.")

    keep_columns = [
        column
        for column in ["timestamp", "latitude", "longitude", rename_map.get(data_var_name_str, data_var_name_str)]
        if column in frame.columns
    ]
    return frame[keep_columns]


def _resolve_run_timestamp(client: Client, *, date: str | None, time: int | None, step: int) -> pd.Timestamp:
    if date is not None and time is not None:
        return pd.Timestamp(f"{date}T{time:02d}:00:00Z")

    latest = pd.Timestamp(client.latest(type="fc", stream="oper", step=step), tz="UTC")
    return latest


def fetch_ifs_snapshot(
    target_dir: Path,
    bbox: BoundingBox,
    *,
    date: str | None = None,
    time: int | None = None,
    step: int = 0,
    source: str = "ecmwf",
    model: str = "ifs",
    resol: str = "0p25",
) -> IfsSnapshotResult:
    ensure_directories(target_dir)
    client = Client(source=source, model=model, resol=resol)
    run_timestamp = _resolve_run_timestamp(client, date=date, time=time, step=step)

    request_date = run_timestamp.strftime("%Y%m%d")
    request_time = int(run_timestamp.hour)
    raw_grib_paths: list[Path] = []
    merged: pd.DataFrame | None = None

    for parameter, output_column in IFS_PARAMETER_MAP.items():
        grib_path = target_dir / f"ifs_{parameter}_{run_timestamp:%Y%m%dT%H%M%SZ}_step{step}.grib2"
        client.retrieve(
            {
                "date": request_date,
                "time": request_time,
                "step": step,
                "stream": "oper",
                "type": "fc",
                "param": parameter,
            },
            target=grib_path,
        )
        raw_grib_paths.append(grib_path)
        field_frame = _field_to_frame(_open_grib_field(grib_path))
        field_frame = field_frame.rename(columns={field_frame.columns[-1]: output_column})
        merged = field_frame if merged is None else merged.merge(field_frame, on=["timestamp", "latitude", "longitude"], how="outer")

    if merged is None:
        raise RuntimeError("IFS snapshot fetch produced no fields.")

    merged = _subset_bbox(merged, bbox)
    if merged.empty:
        raise ValueError("IFS snapshot did not overlap the configured bounding box.")

    if "coarse_temperature" in merged.columns and merged["coarse_temperature"].dropna().median() > 150.0:
        merged["coarse_temperature"] = merged["coarse_temperature"] - 273.15
    if "coarse_pressure" in merged.columns:
        merged["coarse_pressure"] = coerce_pressure_to_hpa(merged["coarse_pressure"])

    coarse_path = target_dir / f"current_coarse_ifs_{run_timestamp:%Y%m%dT%H%M%SZ}.parquet"
    merged.sort_values(["timestamp", "latitude", "longitude"]).to_parquet(coarse_path, index=False)
    return IfsSnapshotResult(run_timestamp=run_timestamp, coarse_path=coarse_path, raw_grib_paths=raw_grib_paths)


def fetch_fmi_weather_snapshot(
    target_dir: Path,
    bbox: BoundingBox,
    *,
    target_time: str | pd.Timestamp,
    lookback_hours: int = 6,
) -> FmiSnapshotResult:
    ensure_directories(target_dir)
    target_timestamp = _to_utc_timestamp(target_time)
    if target_timestamp is None:
        raise ValueError("Target time is required for FMI snapshot fetch.")

    start = target_timestamp - pd.Timedelta(hours=lookback_hours)
    frame = _download_fmi_frame(FMI_WEATHER_QUERY, bbox, start, target_timestamp)
    if frame.empty:
        raise RuntimeError("FMI live weather fetch returned no stations in the configured area.")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    snapshot_timestamp = frame["timestamp"].max()
    snapshot = frame.loc[frame["timestamp"] == snapshot_timestamp].copy()
    snapshot["pressure"] = coerce_pressure_to_hpa(snapshot["pressure"])
    if "wind_speed" in snapshot.columns and "wind_direction" in snapshot.columns:
        station_u10, station_v10 = wind_speed_direction_to_uv(snapshot["wind_speed"], snapshot["wind_direction"])
        snapshot["station_u10"] = station_u10
        snapshot["station_v10"] = station_v10
        snapshot["u10"] = station_u10
        snapshot["v10"] = station_v10

    station_path = target_dir / f"current_stations_fmi_{snapshot_timestamp:%Y%m%dT%H%M%SZ}.parquet"
    snapshot.sort_values(["timestamp", "station_id"]).to_parquet(station_path, index=False)
    return FmiSnapshotResult(station_timestamp=snapshot_timestamp, station_path=station_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a single latest IFS coarse snapshot and FMI weather station snapshot for quick inference tests.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for downloaded live snapshot files.")
    parser.add_argument("--min-lon", type=float, required=True, help="Bounding box minimum longitude.")
    parser.add_argument("--max-lon", type=float, required=True, help="Bounding box maximum longitude.")
    parser.add_argument("--min-lat", type=float, required=True, help="Bounding box minimum latitude.")
    parser.add_argument("--max-lat", type=float, required=True, help="Bounding box maximum latitude.")
    parser.add_argument("--date", type=str, default=None, help="Optional IFS run date as YYYYMMDD. Defaults to latest available.")
    parser.add_argument("--time", type=int, default=None, help="Optional IFS run hour as 0, 6, 12, or 18. Defaults to latest available.")
    parser.add_argument("--step", type=int, default=0, help="Forecast step in hours. Defaults to 0.")
    parser.add_argument("--source", type=str, default="ecmwf", help="ECMWF open-data source key.")
    parser.add_argument("--model", type=str, default="ifs", help="Open-data model key.")
    parser.add_argument("--resol", type=str, default="0p25", help="Open-data resolution key.")
    parser.add_argument("--station-lookback-hours", type=int, default=6, help="How many hours to look back for FMI weather observations.")
    args = parser.parse_args()

    bbox = BoundingBox(
        min_lon=args.min_lon,
        max_lon=args.max_lon,
        min_lat=args.min_lat,
        max_lat=args.max_lat,
    )
    ifs_result = fetch_ifs_snapshot(
        args.output_dir,
        bbox,
        date=args.date,
        time=args.time,
        step=args.step,
        source=args.source,
        model=args.model,
        resol=args.resol,
    )
    fmi_result = fetch_fmi_weather_snapshot(
        args.output_dir,
        bbox,
        target_time=ifs_result.run_timestamp,
        lookback_hours=args.station_lookback_hours,
    )

    print(f"IFS coarse parquet: {ifs_result.coarse_path}")
    print(f"IFS run timestamp: {ifs_result.run_timestamp.isoformat()}")
    print(f"FMI station parquet: {fmi_result.station_path}")
    print(f"FMI station timestamp: {fmi_result.station_timestamp.isoformat()}")


if __name__ == "__main__":
    main()