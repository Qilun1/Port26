from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

import pandas as pd


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float

    def as_cds_area(self) -> list[float]:
        return [self.max_lat, self.min_lon, self.min_lat, self.max_lon]

    def as_fmi_bbox(self) -> str:
        return f"{self.min_lon},{self.min_lat},{self.max_lon},{self.max_lat}"

    def as_rasterio_bounds(self) -> tuple[float, float, float, float]:
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


@dataclass(frozen=True)
class TimeConfig:
    start: pd.Timestamp
    end: pd.Timestamp
    frequency: str


@dataclass(frozen=True)
class PathConfig:
    training_data: Path
    processed: Path
    model_registry: Path
    output_dir: Path


@dataclass(frozen=True)
class Era5LandConfig:
    dataset: str
    variables: list[str]


@dataclass(frozen=True)
class CamsEuropeConfig:
    dataset: str
    url: str
    model: str
    level: str
    type: str
    data_format: str
    variables: list[str]


@dataclass(frozen=True)
class AcagPm25Config:
    base_url: str
    resolution: str
    product_code: str
    cadence: str
    version: str


@dataclass(frozen=True)
class FmiStoredQueryConfig:
    query_id: str
    parameter_mapping: dict[str, str]
    use_timeseries: bool = True


@dataclass(frozen=True)
class FmiConfig:
    weather: FmiStoredQueryConfig
    air_quality: FmiStoredQueryConfig


@dataclass(frozen=True)
class DemConfig:
    stac_api: str
    collection: str
    asset_preference: list[str]


@dataclass(frozen=True)
class PreprocessConfig:
    idw_k: int
    idw_power: float
    min_station_neighbors: int
    grid_stride: int
    dropna_targets: bool


@dataclass(frozen=True)
class FilterConfig:
    station_name_prefixes: list[str]


@dataclass(frozen=True)
class ModelConfig:
    targets: list[str]
    physics_lambda: float
    temperature_lapse_rate_c_per_m: float
    pressure_scale_height_m: float
    learning_rate: float
    max_depth: int
    subsample: float
    colsample_bytree: float
    num_boost_round: int
    early_stopping_rounds: int
    validation_fraction: float


@dataclass(frozen=True)
class InferenceConfig:
    station_file: Path
    coarse_file: Path
    dem_file: Path
    output_stem: str
    prediction_batch_size: int | None


@dataclass(frozen=True)
class SimulationConfig:
    repo_root: Path
    sim_root: Path
    bbox: BoundingBox
    time: TimeConfig
    paths: PathConfig
    era5_land: Era5LandConfig
    cams_europe: CamsEuropeConfig
    acag_pm25: AcagPm25Config
    fmi: FmiConfig
    dem: DemConfig
    preprocess: PreprocessConfig
    filters: FilterConfig
    model: ModelConfig
    inference: InferenceConfig


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sim_root() -> Path:
    return Path(__file__).resolve().parent


def _resolve_relative(root: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (root / path).resolve()


def _default_runtime_payload() -> dict:
    return tomllib.loads((_sim_root() / "config.toml").read_text(encoding="utf-8"))


def _merge_payload(base: dict, overrides: dict) -> dict:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_payload(merged[key], value)
        else:
            merged[key] = value
    return merged


def _coerce_runtime_payload(payload: dict) -> dict:
    base_payload = _default_runtime_payload()
    if "time" in payload:
        return _merge_payload(base_payload, payload)

    if "data" not in payload:
        return payload

    model_payload = dict(payload.get("model", {}))
    train_payload = dict(payload.get("train", {}))
    request_payload = dict(payload.get("inference_request", {}))
    path_payload = dict(payload["paths"])
    default_run_name = str(train_payload.get("run_name", model_payload.pop("run_name", "weather_xgb_v1")))
    default_request_name = str(request_payload.get("request_name", f"{default_run_name}_request"))

    model_registry = path_payload.get("model_registry")
    if model_registry is None:
        model_registry = str(Path(path_payload["model_runs_root"]) / default_run_name)

    output_dir = path_payload.get("output_dir")
    if output_dir is None:
        output_dir = str(Path(path_payload["inference_runs_root"]) / default_request_name / "data")

    runtime_overrides = {
        "domain": dict(payload["domain"]),
        "time": {
            "start": payload["data"]["start"],
            "end": payload["data"]["end"],
            "frequency": payload["data"]["frequency"],
        },
        "paths": {
            "training_data": path_payload["training_data"],
            "processed": path_payload["processed"],
            "model_registry": model_registry,
            "output_dir": output_dir,
        },
        "preprocess": dict(payload["preprocess"]),
        "filters": dict(payload.get("filters", {})),
        "model": {
            **model_payload,
            "targets": list(payload["data"]["targets"]),
        },
        "inference": {
            "station_file": payload["inference"]["station_file"],
            "coarse_file": payload["inference"]["coarse_file"],
            "dem_file": payload["inference"]["dem_file"],
            "output_stem": payload["inference"]["output_stem"],
            "prediction_batch_size": payload["inference"].get("prediction_batch_size"),
        },
    }
    return _merge_payload(base_payload, runtime_overrides)


def load_config(config_path: str | Path | None = None) -> SimulationConfig:
    sim_root = _sim_root()
    repo_root = _repo_root()
    target = Path(config_path) if config_path is not None else sim_root / "config.toml"
    payload = _coerce_runtime_payload(tomllib.loads(target.read_text(encoding="utf-8")))

    bbox = BoundingBox(**payload["domain"])
    time = TimeConfig(
        start=pd.Timestamp(payload["time"]["start"]),
        end=pd.Timestamp(payload["time"]["end"]),
        frequency=payload["time"]["frequency"],
    )
    paths = PathConfig(
        training_data=_resolve_relative(repo_root, payload["paths"]["training_data"]),
        processed=_resolve_relative(repo_root, payload["paths"]["processed"]),
        model_registry=_resolve_relative(repo_root, payload["paths"]["model_registry"]),
        output_dir=_resolve_relative(repo_root, payload["paths"]["output_dir"]),
    )
    era5_land = Era5LandConfig(**payload["era5_land"])
    cams_europe = CamsEuropeConfig(**payload["cams_europe"])
    acag_pm25 = AcagPm25Config(**payload["acag_pm25"])
    fmi = FmiConfig(
        weather=FmiStoredQueryConfig(**payload["fmi"]["weather"]),
        air_quality=FmiStoredQueryConfig(**payload["fmi"]["air_quality"]),
    )
    dem = DemConfig(**payload["dem"])
    preprocess = PreprocessConfig(**payload["preprocess"])
    filters = FilterConfig(
        station_name_prefixes=list(payload.get("filters", {}).get("station_name_prefixes", [])),
    )
    model = ModelConfig(**payload["model"])
    inference = InferenceConfig(
        station_file=_resolve_relative(repo_root, payload["inference"]["station_file"]),
        coarse_file=_resolve_relative(repo_root, payload["inference"]["coarse_file"]),
        dem_file=_resolve_relative(repo_root, payload["inference"]["dem_file"]),
        output_stem=payload["inference"]["output_stem"],
        prediction_batch_size=(
            int(payload["inference"]["prediction_batch_size"])
            if payload["inference"].get("prediction_batch_size") is not None
            else None
        ),
    )
    return SimulationConfig(
        repo_root=repo_root,
        sim_root=sim_root,
        bbox=bbox,
        time=time,
        paths=paths,
        era5_land=era5_land,
        cams_europe=cams_europe,
        acag_pm25=acag_pm25,
        fmi=fmi,
        dem=dem,
        preprocess=preprocess,
        filters=filters,
        model=model,
        inference=inference,
    )