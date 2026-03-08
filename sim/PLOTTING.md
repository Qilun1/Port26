# Plotting Commands

Use these commands. Ignore `sim.inference.*` unless you are debugging internals.

## 1. Normal Inference + Plots

Run a config-defined inference request and write parquet outputs plus maps:

```powershell
cd sim
uv run python -m sim.workflows.run_inference_request --config project.toml
```

Outputs go under `data/inference_runs/<request_name>/`.

## 2. Live IFS Snapshot + Plots

Fetch one live IFS timestep, fetch matching FMI stations, run inference, and write comparison plots:

```powershell
cd sim
uv run python -m sim.workflows.run_ifs_snapshot --config project.toml
```

## 3. Re-Plot Existing Outputs

Rebuild plots from an existing request directory:

```powershell
cd sim
uv run python -m sim.workflows.plot_maps --config project.toml --request-dir ../data/inference_runs/<request_name>
```

Plot one specific parquet directly:

```powershell
cd sim
uv run python -m sim.workflows.plot_maps --config project.toml --parquet ../data/inference_runs/<request_name>/data/downscaled_<timestamp>.parquet
```

## Useful Overrides

- `--timestamp 2026-03-07T12:00:00Z`
- `--targets temperature,pressure`
- `--baseline-label "IFS coarse"`
- `--plot-dir ../some/output/folder`
- `--min-lon 24.95 --max-lon 25.18 --min-lat 60.17 --max-lat 60.28`

## Output Pattern

- Normal request plots: `data/inference_runs/<request_name>/plots/`
- Manual re-plots: `data/inference_runs/<request_name>/plots/manual/`
- Live IFS comparison plots: `data/inference_runs/<request_name>/plots/`

## Rule Of Thumb

- Want fresh inference and maps: `run_inference_request`
- Want one live comparison: `run_ifs_snapshot`
- Already have parquet, only need maps: `plot_maps`