# Simulation Pipeline Usage Guide

This guide contains the detailed setup and operating notes for the simulation workflow. The short entry point remains [sim/README.md](sim/README.md).

## Overview

The workflow is built around three main stages:

1. Fetch historical training data.
2. Preprocess and train one XGBoost model per target.
3. Run inference requests and save parquet outputs plus map plots.

The current practical weather-focused target set is:

- `temperature`
- `pressure`
- `u10`
- `v10`

## Environment Setup

Recommended option with `uv`:

```powershell
cd <repo-root>/sim
uv sync
```

Manual `venv` option:

```powershell
cd <repo-root>
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ./sim
```

Dependencies are declared in [sim/pyproject.toml](sim/pyproject.toml). The most important runtime packages are:

- `pandas`
- `pyarrow`
- `xarray`
- `netCDF4`
- `rasterio`
- `scikit-learn`
- `xgboost`
- `cdsapi`
- `fmiopendata`
- `planetary-computer`
- `pystac-client`
- `matplotlib`

For the live IFS snapshot workflow, also install:

- `ecmwf-opendata`
- `cfgrib`

If imports fail during fetch, preprocess, train, or inference, rerun `uv sync` or reinstall with `python -m pip install -e ./sim`.

`sim/port26_sim.egg-info/` is generated metadata created by packaging tools. It is not the dependency source of truth. The file you should trust and edit is [sim/pyproject.toml](sim/pyproject.toml).

## Credentials

Create `.env` in the repo root or in `sim` using [sim/.env.example](sim/.env.example) as the template.

```text
PORT26_CDS_URL=https://cds.climate.copernicus.eu/api
PORT26_CDS_KEY=your_cds_personal_access_token
PORT26_ADS_URL=https://ads.atmosphere.copernicus.eu/api
PORT26_ADS_KEY=your_ads_personal_access_token
```

You need:

- CDS access for ERA5-Land downloads
- ADS access for CAMS downloads
- network access to FMI Open Data
- network access to the Copernicus DEM STAC service

## Main Config

The main user-facing file is `sim/project.toml`. Start from [sim/project.example.toml](sim/project.example.toml).

The most important settings are:

- `[train]`: friendly training defaults used by `sim.workflows.train_model`
- `[inference_request]`: friendly inference defaults used by `sim.workflows.run_inference_request`
- `[project].name`: label for the project
- `[domain]`: training and inference bounding box
- `[data].start` and `[data].end`: training period
- `[data].targets`: target list
- `[paths]`: where downloaded data, processed data, model runs, and inference requests are written
- `[preprocess].grid_stride`: `1` for full grid, larger for faster previews
- `[filters].station_name_prefixes`: optional station-name filter
- `[model]` hyperparameters: learning rate, depth, boosting rounds, early stopping
- `[inference].station_file`: current station input for inference
- `[inference].coarse_file`: current coarse input for inference
- `[inference].dem_file`: DEM raster used during inference
- `[inference].prediction_batch_size`: optional number of grid rows to predict at once during inference
- `[inference_request].station_plot_hours`: optional sampled duration for post-run station comparison plots
- `[inference_request].station_plot_max_stations`: optional number of representative stations to plot per target

The practical intent is:

- edit `[train]` and `[inference_request]` for normal day-to-day use
- edit `[domain]`, `[data]`, and `[filters]` when you change the study area or training window
- leave most of `[model]`, `[preprocess]`, and `[inference]` alone unless you are tuning the pipeline itself

If you do not define `[inference_request].start` and `[inference_request].end`, the normal inference workflow falls back to `[data].start` and `[data].end`.

For a Helsinki-only run, use both:

- a tight `[domain]` box that avoids large sea areas
- `[filters].station_name_prefixes = ["Helsinki "]`

## Simplified Workflow Commands

The supported user-facing commands are:

- `sim.workflows.fetch_data`
- `sim.workflows.train_model`
- `sim.workflows.run_inference_request`
- `sim.workflows.run_ifs_snapshot`
- `sim.workflows.plot_maps`

If you are not debugging internals, stop at this list.

Recommended training flow from `sim`:

```powershell
uv run python -m sim.workflows.fetch_data --config project.toml
uv run python -m sim.workflows.train_model --config project.toml
```

Single command that fetches and then trains:

```powershell
uv run python -m sim.workflows.train_model --config project.toml --fetch-first
```

Inference request:

```powershell
uv run python -m sim.workflows.run_inference_request --config project.toml
```

Normal inference requests also save sampled station comparison plots under `data/inference_runs/<request_name>/plots/stations/`. These compare station observations, the coarse baseline, and the SR model over a shorter sample window from the request, which defaults to 24 hours.

Quick one-timestep live IFS snapshot inference:

```powershell
uv run python -m sim.workflows.run_ifs_snapshot --config project.toml
```

Plot or re-plot an existing inference result directory:

```powershell
uv run python -m sim.workflows.plot_maps --config project.toml --request-dir data/inference_runs/<request_name>
```

Plot a single parquet directly:

```powershell
uv run python -m sim.workflows.plot_maps --config project.toml --parquet data/inference_runs/<request_name>/data/downscaled_<timestamp>.parquet
```

Useful plot overrides:

- `--timestamp <utc_time>` to choose a specific parquet from a request directory
- `--targets temperature,pressure` to restrict the output set
- `--plot-dir <dir>` to write PNGs somewhere else
- `--baseline-label "IFS coarse"` when you want an explicit coarse-field label
- `--min-lon --max-lon --min-lat --max-lat` to clip the rendered area

Inference size controls in `project.toml`:

- `inference_request.start` and `inference_request.end`: limit how many timestamps are processed
- `inference_request.min_lon`, `max_lon`, `min_lat`, `max_lat`: limit spatial extent
- `inference_request.grid_stride`: thin the DEM grid for faster preview inference
- `inference_request.prediction_batch_size` or `inference.prediction_batch_size`: cap how many grid rows are predicted per model batch

Practical rule of thumb:

- lower `grid_stride` means denser output and more work
- lower `prediction_batch_size` means smaller memory spikes but slower inference
- if you want full-resolution output over a large area, keep `grid_stride = 1` and reduce `prediction_batch_size`

Useful overrides:

- `--run-name <trained_run>` to point at a different trained model folder
- `--request-name <folder_name>` to keep live tests separate
- `--date YYYYMMDD --time 0|6|12|18` to pin a specific IFS cycle instead of using the latest available one
- `--step <hours>` to fetch a forecast lead other than step 0

One-command paper/demo flow:

```powershell
uv run python -m sim.workflows.run_demo --config project.toml
```

`run_demo` uses the config-defined training defaults, writes validation metrics into the model run folder, and then executes the config-defined inference request so you get both metrics and visual inference outputs from one command.

If `project.toml` points to missing `current_stations` or `current_coarse` files, the workflow now falls back to the matching timestamp range in `sim/training_data/processed/station_training_raw.parquet` so you can run a smoke test without assembling real-time inputs first. For actual production inference, set `[inference].station_file` and `[inference].coarse_file` to your real current inputs.

`run_ifs_snapshot` is the simplest route for a real-time check: it fetches one coarse IFS field for `2t`, `sp`, `10u`, and `10v` at 0.25 degree resolution, fetches the latest FMI weather observations in the configured area, runs inference for that single timestamp, and saves both the downscaled parquet and quick coarse-vs-downscaled PNGs.

## Plotting Decision Tree

Use this instead of guessing between scripts:

1. You want a normal inference run plus plots.
	Run `uv run python -m sim.workflows.run_inference_request --config project.toml`
2. You want a live one-timestep IFS comparison.
	Run `uv run python -m sim.workflows.run_ifs_snapshot --config project.toml`
3. You already have a downscaled parquet or request folder and only want plots.
	Run `uv run python -m sim.workflows.plot_maps ...`
4. You are changing internals or debugging the pipeline implementation.
	Only then use `sim.inference.*`

## Internal Module Commands

These lower-level commands still work when needed, but they are not the normal interface:

```powershell
uv run python -m sim.data_in.download_training_data
uv run python -m sim.data_in.fmi_fetcher --ecmwf-file data/current_coarse.nc
uv run python -m sim.preprocess.build_dataset
uv run python -m sim.models.train_xgboost
uv run python -m sim.inference.run_downscaling
uv run python -m sim.inference.run_inference_and_map
```

In particular:

- `sim.inference.run_downscaling` is the low-level parquet writer
- `sim.inference.run_inference_and_map` is the low-level helper that writes first/last maps
- `sim.inference.map_plots` is a library module, not a command

## How To Verify Outputs

After training, the main artifacts are under `sim/models/runs/<run_name>/`.

Check these first:

- `registry.json`
- `run_summary.json`
- `*_learning_curve.png`
- `validation_plots/validation_metrics.csv`
- `validation_plots/validation_metrics.png`

Each run folder should also contain:

- trained model JSON files
- copied workflow config
- resolved runtime config
- per-target learning-curve CSV files
- detailed validation plots

After inference, the main outputs are under `data/inference_runs/<request_name>/`.

Check:

- `data/`: parquet outputs
- `plots/`: first and last timestamp maps
- `plots/stations/`: sampled station-versus-baseline-versus-model timeseries plots

For live IFS snapshot runs, also check:

- `live_inputs/`: downloaded GRIB files and converted live input parquet files
- `plots/ifs_compare_<target>_<timestamp>.png`: coarse versus downscaled comparison plots

## Expected Data Layout

Core downloaded and processed data commonly appears under:

- `sim/training_data/era5_land/*.nc`
- `sim/training_data/cams_europe/*.nc`
- `sim/training_data/fmi/observations.parquet`
- `sim/training_data/fmi/silam/*.nc`
- `sim/training_data/dem/cop_dem_30m.tif`
- `sim/training_data/processed/*.parquet`

Legacy model and inference outputs can also appear under:

- `sim/models/artifacts/*.json`
- `sim/models/artifacts/registry.json`
- `data/downscaled/*.parquet`

## Cleanup Before Re-Runs

If you change any of the following, do not trust old downloaded or processed artifacts:

- bounding box
- date range
- station filters
- target list

Clear stale outputs first, especially under:

- `sim/training_data/era5_land/`
- `sim/training_data/cams_europe/`
- `sim/training_data/fmi/`
- `sim/training_data/dem/`
- `sim/training_data/processed/`
- `sim/models/runs/<run_name>/`

If you skip cleanup after changing the spatial or temporal setup, it is easy to mix incompatible artifacts into one run.

## Inference Inputs

For the current weather-only configuration, station input should contain at least:

- `timestamp`
- `latitude`
- `longitude`
- `temperature`
- `pressure`

For wind-aware inference, provide either:

- `wind_speed` and `wind_direction`

or:

- `station_u10` and `station_v10`

Coarse input should contain at least:

- `latitude`
- `longitude`
- `coarse_temperature` or `temperature`
- `coarse_pressure` or `pressure`
- `coarse_u10` or `u10`
- `coarse_v10` or `v10`

The workflow writes one downscaled parquet per output timestamp and saves first and last prediction maps. Those plots use the DEM as a grayscale terrain underlay for spatial reference.

## Common Failure Modes

- Missing package import: rerun `uv sync` or reinstall the environment.
- Missing Parquet engine: install `pyarrow`.
- Old area still shows in outputs: clear old training and processed data before rerunning with a new bbox.
- Too much sea in the frame: tighten `[domain]` and use `[filters].station_name_prefixes`.
- Missing model files during inference: train successfully first and point `--run-name` to the correct run folder.
- Fetch failures from Copernicus: verify `.env` credentials and service access.

## Operational Notes

- ERA5-Land is used for the normal training and smoke-test meteorology baseline, roughly 9 km native resolution.
- The live snapshot workflow uses IFS open data at 0.25 degree resolution, roughly 25 to 30 km.
- CAMS Europe is used where coarse air-quality history is still needed.
- FMI observations are aligned to coarse fields and local DEM-derived features.
- Wind observations are converted into meteorological `u` and `v` components.
- Training is per target using XGBoost residual models.