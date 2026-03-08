# Simulation Pipeline

This folder contains the downscaling workflow for training weather residual models and running dense-grid inference over a chosen area.

This README is intentionally short. For detailed setup, configuration, input formats, cleanup rules, and troubleshooting, use [sim/USAGE.md](sim/USAGE.md).

## Quick Start

1. Create one Python environment for the repo.
2. Install the dependencies from [sim/pyproject.toml](sim/pyproject.toml).
3. Treat `sim/port26_sim.egg-info/` as generated packaging metadata, not as a config file you should edit.
4. Add Copernicus credentials in `.env`.
5. Copy [sim/project.example.toml](sim/project.example.toml) to `sim/project.toml` and set your area, dates, targets, and run name.
6. Fetch training data.
7. Train the model.
8. Run one of the supported inference workflows.
9. Use the dedicated plot command to regenerate or re-style plots from an existing parquet output.
10. Check the run folder for metrics and plots.

Recommended setup with `uv`:

```powershell
cd <repo-root>/sim
uv sync
```

Manual `venv` setup:

```powershell
cd <repo-root>
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ./sim
```

## Minimal Config

Start from [sim/project.example.toml](sim/project.example.toml) and set at least:

- `[train]`: main training run name and whether to fetch first
- `[inference_request]`: the paper/demo request name, dates, bbox, preview stride, and optional prediction batch size override
- `[domain]`: bounding box
- `[data].start` and `[data].end`: training period
- `[data].targets`: usually `temperature`, `pressure`, `u10`, `v10`
- `[filters].station_name_prefixes`: optional municipality filter such as `Helsinki `
- `[inference].prediction_batch_size`: optional row batch size for large inference grids; lower it if inference uses too much memory

## Run

Supported user-facing commands:

- `sim.workflows.fetch_data`: fetch training inputs
- `sim.workflows.train_model`: preprocess, train, and validate
- `sim.workflows.run_inference_request`: run a normal config-driven inference request
- `sim.workflows.run_ifs_snapshot`: run one live IFS + FMI snapshot
- `sim.workflows.plot_maps`: make or remake plots from an existing downscaled parquet

From `sim`:

```powershell
uv run python -m sim.workflows.fetch_data --config sim/project.toml
uv run python -m sim.workflows.train_model --config project.toml
```

Optional inference request after training:

```powershell
uv run python -m sim.workflows.run_inference_request --config project.toml
```

This writes gridded parquet outputs, first and last map PNGs, and sampled station comparison plots under `data/inference_runs/<request_name>/plots/stations/`.

Quick live IFS snapshot inference for one latest timestep:

```powershell
uv run python -m sim.workflows.run_ifs_snapshot --config project.toml
```

This downloads one live IFS step-0 coarse field at 0.25 degree resolution plus the latest matching FMI weather stations, runs a single inference timestamp, and writes quick comparison plots under `data/inference_runs/<request_name>/plots/`.

Plot or re-plot an existing request output:

```powershell
uv run python -m sim.workflows.plot_maps --config project.toml --request-dir data/inference_runs/<request_name>
```

Plot a single parquet directly:

```powershell
uv run python -m sim.workflows.plot_maps --config project.toml --parquet data/inference_runs/<request_name>/data/downscaled_<timestamp>.parquet
```

If `[inference_request]` is omitted, `run_inference_request` defaults to the `[data].start` and `[data].end` window from `project.toml`.

One-command demo for a paper-ready example run:

```powershell
uv run python -m sim.workflows.run_demo --config project.toml
```

If the configured current station or coarse files do not exist yet, the inference workflow uses the matching range from `sim/training_data/processed/station_training_raw.parquet` as a smoke test source.

Low-level modules under `sim.inference.*` are internal building blocks. Use them only for debugging or development work.

## How To Check It Worked

After training, inspect:

- `sim/models/runs/<run_name>/registry.json`
- `sim/models/runs/<run_name>/run_summary.json`
- `sim/models/runs/<run_name>/*_learning_curve.png`
- `sim/models/runs/<run_name>/validation_plots/validation_metrics.csv`
- `sim/models/runs/<run_name>/validation_plots/validation_metrics.png`

After inference, inspect:

- `data/inference_runs/<request_name>/data/`
- `data/inference_runs/<request_name>/plots/`

For the live IFS snapshot workflow, inspect:

- `data/inference_runs/<request_name>/live_inputs/`
- `data/inference_runs/<request_name>/data/`
- `data/inference_runs/<request_name>/plots/`

If you want a Helsinki-only run, use both:

- A tight `[domain]` box
- `[filters].station_name_prefixes = ["Helsinki "]`

## Detailed Guide

Use [sim/USAGE.md](sim/USAGE.md) for:

- credentials and package details
- full `project.toml` guidance
- cleanup rules before reruns
- direct module commands
- inference input format details
- common failure modes