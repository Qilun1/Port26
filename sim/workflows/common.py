from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pandas as pd


@dataclass(frozen=True)
class WorkflowBoundingBox:
    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float


@dataclass(frozen=True)
class WorkflowDataConfig:
    start: pd.Timestamp
    end: pd.Timestamp
    frequency: str
    targets: list[str]


@dataclass(frozen=True)
class WorkflowPaths:
    training_data: Path
    processed: Path
    model_runs_root: Path
    inference_runs_root: Path


@dataclass(frozen=True)
class WorkflowPreprocessConfig:
    idw_k: int
    idw_power: float
    min_station_neighbors: int
    grid_stride: int
    dropna_targets: bool


@dataclass(frozen=True)
class WorkflowFilterConfig:
    station_name_prefixes: list[str]


@dataclass(frozen=True)
class WorkflowModelConfig:
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
class WorkflowInferenceConfig:
    station_file: Path
    coarse_file: Path
    dem_file: Path
    output_stem: str
    preview_grid_stride: int
    prediction_batch_size: int | None


@dataclass(frozen=True)
class WorkflowTrainConfig:
    run_name: str
    fetch_first: bool


@dataclass(frozen=True)
class WorkflowInferenceRequestConfig:
    run_name: str
    request_name: str
    station_file: Path | None
    coarse_file: Path | None
    dem_file: Path | None
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    min_lon: float | None
    max_lon: float | None
    min_lat: float | None
    max_lat: float | None
    grid_stride: int | None
    prediction_batch_size: int | None
    station_plot_hours: int | None
    station_plot_max_stations: int | None


@dataclass(frozen=True)
class WorkflowConfig:
    path: Path
    name: str
    bbox: WorkflowBoundingBox
    data: WorkflowDataConfig
    paths: WorkflowPaths
    preprocess: WorkflowPreprocessConfig
    filters: WorkflowFilterConfig
    model: WorkflowModelConfig
    inference: WorkflowInferenceConfig
    train: WorkflowTrainConfig
    request: WorkflowInferenceRequestConfig


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def sim_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(raw: str | Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else (repo_root() / path).resolve()


def resolve_optional_repo_path(raw: str | Path | None) -> Path | None:
    if raw is None or raw == "":
        return None
    return resolve_repo_path(raw)


def parse_optional_timestamp(raw: str | None) -> pd.Timestamp | None:
    if raw is None or raw == "":
        return None
    return pd.Timestamp(raw)


def load_workflow_config(config_path: str | Path | None = None) -> WorkflowConfig:
    target = Path(config_path) if config_path is not None else (sim_root() / "project.toml")
    payload = tomllib.loads(target.read_text(encoding="utf-8"))
    model_payload = dict(payload["model"])
    train_payload = dict(payload.get("train", {}))
    request_payload = dict(payload.get("inference_request", {}))
    default_run_name = str(train_payload.get("run_name", model_payload.pop("run_name", "weather_xgb_v1")))
    default_request_name = str(request_payload.get("request_name", f"{default_run_name}_request"))

    return WorkflowConfig(
        path=target.resolve(),
        name=payload["project"]["name"],
        bbox=WorkflowBoundingBox(**payload["domain"]),
        data=WorkflowDataConfig(
            start=pd.Timestamp(payload["data"]["start"]),
            end=pd.Timestamp(payload["data"]["end"]),
            frequency=payload["data"]["frequency"],
            targets=list(payload["data"]["targets"]),
        ),
        paths=WorkflowPaths(
            training_data=resolve_repo_path(payload["paths"]["training_data"]),
            processed=resolve_repo_path(payload["paths"]["processed"]),
            model_runs_root=resolve_repo_path(payload["paths"]["model_runs_root"]),
            inference_runs_root=resolve_repo_path(payload["paths"]["inference_runs_root"]),
        ),
        preprocess=WorkflowPreprocessConfig(**payload["preprocess"]),
        filters=WorkflowFilterConfig(
            station_name_prefixes=list(payload.get("filters", {}).get("station_name_prefixes", [])),
        ),
        model=WorkflowModelConfig(**model_payload),
        inference=WorkflowInferenceConfig(
            station_file=resolve_repo_path(payload["inference"]["station_file"]),
            coarse_file=resolve_repo_path(payload["inference"]["coarse_file"]),
            dem_file=resolve_repo_path(payload["inference"]["dem_file"]),
            output_stem=payload["inference"]["output_stem"],
            preview_grid_stride=int(payload["inference"]["preview_grid_stride"]),
            prediction_batch_size=(
                int(payload["inference"]["prediction_batch_size"])
                if payload["inference"].get("prediction_batch_size") is not None
                else None
            ),
        ),
        train=WorkflowTrainConfig(
            run_name=default_run_name,
            fetch_first=bool(train_payload.get("fetch_first", False)),
        ),
        request=WorkflowInferenceRequestConfig(
            run_name=str(request_payload.get("run_name", default_run_name)),
            request_name=default_request_name,
            station_file=resolve_optional_repo_path(request_payload.get("station_file")),
            coarse_file=resolve_optional_repo_path(request_payload.get("coarse_file")),
            dem_file=resolve_optional_repo_path(request_payload.get("dem_file")),
            start=parse_optional_timestamp(request_payload.get("start")),
            end=parse_optional_timestamp(request_payload.get("end")),
            min_lon=request_payload.get("min_lon"),
            max_lon=request_payload.get("max_lon"),
            min_lat=request_payload.get("min_lat"),
            max_lat=request_payload.get("max_lat"),
            grid_stride=int(request_payload["grid_stride"]) if "grid_stride" in request_payload else None,
            prediction_batch_size=(
                int(request_payload["prediction_batch_size"])
                if request_payload.get("prediction_batch_size") is not None
                else None
            ),
            station_plot_hours=(
                int(request_payload["station_plot_hours"])
                if request_payload.get("station_plot_hours") is not None
                else None
            ),
            station_plot_max_stations=(
                int(request_payload["station_plot_max_stations"])
                if request_payload.get("station_plot_max_stations") is not None
                else None
            ),
        ),
    )


def _base_payload() -> dict:
    return tomllib.loads((sim_root() / "config.toml").read_text(encoding="utf-8"))


def build_runtime_payload(
    workflow: WorkflowConfig,
    *,
    model_registry: Path,
    output_dir: Path,
    station_file: str | Path | None = None,
    coarse_file: str | Path | None = None,
    dem_file: str | Path | None = None,
    grid_stride: int | None = None,
    prediction_batch_size: int | None = None,
) -> dict:
    payload = _base_payload()
    payload["domain"] = {
        "min_lon": workflow.bbox.min_lon,
        "max_lon": workflow.bbox.max_lon,
        "min_lat": workflow.bbox.min_lat,
        "max_lat": workflow.bbox.max_lat,
    }
    payload["time"] = {
        "start": workflow.data.start.isoformat().replace("+00:00", "Z"),
        "end": workflow.data.end.isoformat().replace("+00:00", "Z"),
        "frequency": workflow.data.frequency,
    }
    payload["paths"] = {
        "training_data": _to_repo_relative(workflow.paths.training_data),
        "processed": _to_repo_relative(workflow.paths.processed),
        "model_registry": _to_repo_relative(model_registry),
        "output_dir": _to_repo_relative(output_dir),
    }
    payload["preprocess"] = {
        "idw_k": workflow.preprocess.idw_k,
        "idw_power": workflow.preprocess.idw_power,
        "min_station_neighbors": workflow.preprocess.min_station_neighbors,
        "grid_stride": grid_stride if grid_stride is not None else workflow.preprocess.grid_stride,
        "dropna_targets": workflow.preprocess.dropna_targets,
    }
    payload["filters"] = {
        "station_name_prefixes": workflow.filters.station_name_prefixes,
    }
    payload["model"] = {
        "targets": workflow.data.targets,
        "physics_lambda": workflow.model.physics_lambda,
        "temperature_lapse_rate_c_per_m": workflow.model.temperature_lapse_rate_c_per_m,
        "pressure_scale_height_m": workflow.model.pressure_scale_height_m,
        "learning_rate": workflow.model.learning_rate,
        "max_depth": workflow.model.max_depth,
        "subsample": workflow.model.subsample,
        "colsample_bytree": workflow.model.colsample_bytree,
        "num_boost_round": workflow.model.num_boost_round,
        "early_stopping_rounds": workflow.model.early_stopping_rounds,
        "validation_fraction": workflow.model.validation_fraction,
    }
    payload["inference"] = {
        "station_file": _to_repo_relative(station_file or workflow.inference.station_file),
        "coarse_file": _to_repo_relative(coarse_file or workflow.inference.coarse_file),
        "dem_file": _to_repo_relative(dem_file or workflow.inference.dem_file),
        "output_stem": workflow.inference.output_stem,
        "prediction_batch_size": (
            prediction_batch_size
            if prediction_batch_size is not None
            else workflow.inference.prediction_batch_size
        ),
    }
    return payload


def write_runtime_config(payload: dict, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_toml_dumps(payload).strip() + "\n", encoding="utf-8")
    return target


def run_module(module_name: str, config_path: Path, extra_args: list[str] | None = None) -> None:
    command = [sys.executable, "-m", module_name, "--config", str(config_path)]
    if extra_args:
        command.extend(extra_args)
    subprocess.run(command, check=True, cwd=repo_root())


def copy_workflow_config(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def write_run_summary(run_dir: Path) -> Path:
    registry_path = run_dir / "registry.json"
    summary_path = run_dir / "run_summary.json"
    payload = {
        "run_dir": str(run_dir),
        "registry_path": str(registry_path),
        "model_files": sorted(
            str(path)
            for path in run_dir.glob("*.json")
            if path.name not in {"registry.json", "run_summary.json"}
        ),
        "learning_curve_pngs": sorted(str(path) for path in run_dir.glob("*_learning_curve.png")),
        "learning_curve_csvs": sorted(str(path) for path in run_dir.glob("*_learning_curve.csv")),
        "validation_plot_dir": str(run_dir / "validation_plots"),
    }
    if registry_path.exists():
        payload["registry"] = json.loads(registry_path.read_text(encoding="utf-8"))
    validation_metrics = run_dir / "validation_plots" / "validation_metrics.csv"
    if validation_metrics.exists():
        payload["validation_metrics_csv"] = str(validation_metrics)
        payload["validation_metrics_preview"] = pd.read_csv(validation_metrics).to_dict(orient="records")
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return summary_path


def _to_repo_relative(path: str | Path) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(repo_root()).as_posix()
    except ValueError:
        return str(path)


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")


def _toml_dumps(payload: dict, prefix: list[str] | None = None) -> str:
    prefix = prefix or []
    lines: list[str] = []
    simple_items = [(key, value) for key, value in payload.items() if not isinstance(value, dict)]
    nested_items = [(key, value) for key, value in payload.items() if isinstance(value, dict)]

    if prefix:
        lines.append(f"[{'.'.join(prefix)}]")
    for key, value in simple_items:
        lines.append(f"{key} = {_format_toml_value(value)}")
    if simple_items and nested_items:
        lines.append("")
    for index, (key, value) in enumerate(nested_items):
        lines.append(_toml_dumps(value, [*prefix, key]))
        if index != len(nested_items) - 1:
            lines.append("")
    return "\n".join(lines)