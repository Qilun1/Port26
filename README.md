# Port26

Port26 is a multi-part weather and environmental sensing project developed during the Port26 hackathon at Aalto University. The project investigates how sparse real-world weather observations and coarse meteorological fields can be combined to produce denser, more locally meaningful environmental information for urban areas.

In practical terms, the repository brings together three connected components:

- a FastAPI backend for sensor and interpolation APIs
- a React frontend for map-based visualization
- a simulation and inference pipeline for downscaling coarse meteorological data into dense local grids

The repository is structured so the modelling workflow, serving layer, and visualization layer can evolve independently while still addressing the same core problem: how to estimate fine-scale urban weather conditions from limited direct measurements and broader-scale numerical weather data.

## Project Context

Urban weather and environmental conditions can vary substantially across short distances due to built form, land cover, proximity to water, traffic, and other local effects. However, direct observations are typically available only at a limited number of sensor or station locations, while numerical weather products often operate at a coarser spatial resolution than is useful for neighborhood-level analysis.

Port26 addresses this gap by exploring a workflow in which:

- station and sensor observations provide local ground-truth signals
- coarse meteorological fields provide broader spatial and temporal context
- statistical or machine-learning downscaling methods estimate denser near-surface conditions
- APIs and visualization tools make those outputs easier to inspect and communicate

The current repository focuses on the Helsinki region, but the structure is general enough to support similar workflows in other bounded urban areas.

## Problem Statement

The central technical problem is one of spatial resolution and local representativeness. A city-scale application may need weather estimates at many more locations than are directly observed, yet naive interpolation alone may fail to capture broader meteorological structure, while coarse forecast products alone may miss local urban variation.

This project therefore studies a combined approach:

- use coarse meteorological data as the large-scale baseline
- use observed station data to learn or estimate local residual structure
- generate dense inference outputs over a spatial grid
- expose these results through an API and interactive map interface

From an academic or prototyping perspective, the repository can be viewed as an applied experiment in urban environmental modelling, spatial interpolation, and practical decision-support tooling.

## Project Origin

Port26 was created in the context of the Port26 hackathon at Aalto University. That origin matters to the structure of the repository: it combines rapid prototyping with a research-style workflow, where data acquisition, modelling, evaluation, API serving, and visualization are all developed together in a single working codebase.

## Repository Overview

### Backend

The backend exposes sensor and interpolation endpoints with FastAPI. It serves as the interface layer between the underlying data products and downstream consumers such as the frontend or external applications.

Key responsibilities:

- sensor metadata and latest values
- historical sensor time series
- inverse-distance-weighted interpolation over a spatial grid
- API integration for the frontend or external consumers

See `backend/README.md` for implementation details and SQL setup notes.

### Frontend

The frontend is a Vite + React + TypeScript application for map-based exploration of the sensor network and spatial weather outputs. Its role is not only presentation, but also interpretability: it makes dense predictions and measured observations easier to compare in geographic context.

Key responsibilities:

- interactive map rendering
- sensor visualization and tooltips
- frontend integration layer for sensor/weather data
- presentation of dense spatial outputs

See `frontend/README.md` for frontend-specific usage.

### Simulation Pipeline

The `sim/` package contains the modelling and inference workflow used to fetch source data, train residual models, run dense-grid inference, and generate diagnostic plots. This is the most research-oriented part of the repository and forms the methodological core of the project.

Key responsibilities:

- fetching and preprocessing meteorological data
- training residual models
- running dense-grid inference requests
- live IFS snapshot inference
- producing maps and validation plots

See `sim/README.md` and `sim/USAGE.md` for the full workflow.

## Research Framing

Although the repository is organized as an engineering project, its internal logic is close to a compact research pipeline:

- data acquisition from external meteorological and observational sources
- preprocessing and feature construction
- model training and validation
- dense spatial inference over a target domain
- visual and API-based inspection of the resulting fields

This makes the project relevant to questions in urban climate informatics, spatial data science, environmental monitoring, and weather-aware digital services.

## High-Level Architecture

```text
coarse weather data + station observations
		    |
		    v
	  sim/ training + inference
		    |
		    v
   dense outputs, plots, and derived products
		    |
		    +-------------------+
		    |                   |
		    v                   v
	    backend API          stored artifacts
		    |
		    v
	   frontend visualization
```

## Project Layout

```text
backend/    FastAPI API, schemas, services, SQL, tests
frontend/   React + TypeScript client application
sim/        Model training, inference, plotting, workflows
data/       Generated inference outputs and model artifacts
sim/PLOTTING.md Plotting command reference
```

## Quick Start

This repo does not have a single one-command bootstrap. Start the parts you need.

### 1. Backend

From `backend/`:

```powershell
uv sync
uv run uvicorn main:app --reload
```

Before using the API against a real database, run the SQL files in `backend/sql/` in your Supabase project and create the expected environment variables.

### 2. Frontend

From `frontend/`:

```powershell
npm install
npm run dev
```

### 3. Simulation Pipeline

From `sim/`:

```powershell
uv sync
uv run python -m sim.workflows.fetch_data --config project.toml
uv run python -m sim.workflows.train_model --config project.toml
```

Optional inference workflows:

```powershell
uv run python -m sim.workflows.run_inference_request --config project.toml
uv run python -m sim.workflows.run_ifs_snapshot --config project.toml
```

## Common Workflows

### Run the API locally

```powershell
cd backend
uv sync
uv run uvicorn main:app --reload
```

### Run the frontend locally

```powershell
cd frontend
npm install
npm run dev
```

### Train a model

```powershell
cd sim
uv sync
uv run python -m sim.workflows.train_model --config project.toml
```

### Run one live IFS inference snapshot

```powershell
cd sim
uv run python -m sim.workflows.run_ifs_snapshot --config project.toml
```

### Rebuild maps from existing outputs

```powershell
cd sim
uv run python -m sim.workflows.plot_maps --config project.toml --request-dir ../data/inference_runs/<request_name>
```

## Requirements

The exact requirements vary by subproject, but the repo currently expects:

- Python 3.13 for the backend and simulation code
- `uv` for Python dependency management
- Node.js for the frontend
- Supabase for backend persistence
- external weather/data credentials for parts of the simulation workflow

## Data And Generated Outputs

The repo contains generated and derived outputs under locations such as:

- `data/inference_runs/`
- `sim/models/runs/`
- `sim/port26_sim.egg-info/`

Treat these as outputs or packaging artifacts unless a specific workflow tells you to edit them.

## Testing

Backend tests live under `backend/tests/`.

Typical test command:

```powershell
cd backend
uv run pytest tests
```

## Documentation Index

- `backend/README.md`: API setup and endpoint notes
- `frontend/README.md`: frontend setup and structure
- `sim/README.md`: simulation pipeline quick reference
- `sim/USAGE.md`: detailed simulation usage
- `sim/PLOTTING.md`: plotting command cheatsheet

## License

This repository uses split licensing:

- everything outside `sim/` is proprietary and all rights are reserved under `LICENSE`
- `sim/` is licensed separately under the MIT License in `sim/LICENSE`