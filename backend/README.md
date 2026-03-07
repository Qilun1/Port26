# Backend

FastAPI backend managed with `uv`.

## Quick Start

1. Open a terminal in `backend/`.
2. Install and sync dependencies:

```bash
uv sync
```

3. Create local environment variables:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

4. Run the API (once `main.py` exposes `app`):

```bash
uv run uvicorn main:app --reload
```

5. Open Supabase dashboard SQL editor and run:

```sql
-- from backend/sql/001_create_sensors_table.sql
```

6. To enable historical time-series readings, also run:

```sql
-- backend/sql/004_add_enabled_column.sql
-- backend/sql/005_create_sensor_readings_table.sql
-- backend/sql/006_sync_latest_fields_from_readings.sql
```

## Project Layout

- `main.py`: FastAPI app entrypoint and router registration.
- `config.py`: configuration and environment loading.
- `endpoints/`: API route handlers.
- `services/`: business logic and integrations.
- `schemas/`: Pydantic request/response models.

## Add Features

1. Create/update schemas in `schemas/`.
2. Implement business logic in `services/`.
3. Expose endpoints in `endpoints/`.
4. Register routers in `main.py`.
5. Add any new dependency with:

```bash
uv add <package>
```

## Generate Simulated Sensor Readings

Generate one day of synthetic AQI and temperature series for all enabled sensors.

```bash
uv run python services/scripts/generate_sensor_readings_day.py --date 2026-03-07
```

Useful options:
- `--dry-run`: preview generated rows without writing
- `--timezone Europe/Helsinki`: local cycle and rush-hour anchoring (default)
- `--interval-minutes 15`: 96 rows per sensor per day
- `--seed 26026`: deterministic output

## Generate Precomputed Interpolation Timeline (Offline)

Generate one-day interpolation frames (96 x 15-minute frames) and store them on disk for playback.

```bash
uv run python services/scripts/generate_interpolation_timeline_day.py \
	--metric aqi \
	--date 2026-03-07 \
	--grid-size-meters 100
```

Output location (default): `backend/data/interpolation_timelines/`

Filename convention: `{metric}_{date}_{grid_size}m.json` (example: `aqi_2026-03-07_100m.json`)

## Implemented Endpoints

### `GET /sensors`
Returns all sensors with coordinates and latest metrics.

Example response:
```json
{
	"sensors": [
		{
			"id": 1,
			"sensor_code": "SEN-001",
			"name": "City Center",
			"latitude": 50.087451,
			"longitude": 14.420671,
			"latest_temperature_c": 11.3,
			"latest_air_pressure_hpa": 1015.2,
			"latest_aqi": 34
		}
	],
	"count": 1
}
```

### `GET /interpolation/grid`
Returns IDW-interpolated grid values for a selected metric over the sensor area.

Query parameters:
- `metric` (required): `"temperature"` or `"aqi"`
- `grid_size_meters` (optional): 50–200, default 100
- `min_latitude`, `min_longitude`, `max_latitude`, `max_longitude` (optional): explicit bbox

Example response:
```json
{
	"metric": "temperature",
	"grid_size_meters": 100.0,
	"count": 156,
	"bounding_box": {
		"min_latitude": 60.05,
		"min_longitude": 24.72,
		"max_latitude": 60.29,
		"max_longitude": 25.16
	},
	"points": [
		{
			"row": 0,
			"col": 0,
			"latitude": 60.28,
			"longitude": 24.73,
			"interpolated_value": 8.7
		}
	]
}
```

Transfer limit: 20,000 points. Returns 422 if grid is too large.

### `GET /interpolation/timeline`
Returns one day of precomputed interpolation frames loaded from local backend storage.

Query parameters:
- `metric` (required): `"temperature"` or `"aqi"`
- `date` (required): day in `YYYY-MM-DD`
- `grid_size_meters` (optional): default `100`, range `50`-`200`

Behavior:
- Reads precomputed artifact from disk (no request-time interpolation recompute)
- Returns 404 when the artifact file is missing
- Keeps fixed grid geometry (`rows`, `cols`, `bounding_box`) across frames
- Uses sparse playback payload: `active_indices` + frame `values` aligned to those indices

### `GET /sensors/{sensor_id}/readings`
Returns historical time-series data for a specific sensor.

Example response:
```json
{
	"data": [
		{
			"timestamp": "2026-03-07T00:00:00+02:00",
			"aqi": 32,
			"temperature_c": 8.5
		}
	],
	"count": 96
}
```

Returns 404 if sensor does not exist. Currently returns all available readings (MVP scope: single day, no date filtering).

## Recent Changes

- **Time-Series Data**: Added `sensor_readings` table with trigger-based sync to `sensors.latest_*` fields
- **Historical Endpoint**: New `GET /sensors/{sensor_id}/readings` for time-series queries
- **Data Simulator**: `generate_sensor_readings_day.py` script with spatial smoothing, diurnal oscillation, and rush-hour AQI peaks
- **Sensor Filtering**: Added `enabled` column to filter active sensors
- **Interpolation Timeline MVP**: Added offline timeline generator and `GET /interpolation/timeline` disk loader for 96-frame daily playback
- **Sparse Timeline Optimization**: Timeline artifacts now store stable `active_indices` plus per-frame sparse values (dense null-padded arrays removed)

## Endpoint Extension Pattern

When adding a new endpoint, follow this order:

1. Add or update response/request models in `schemas/`.
2. Implement business/data access logic in `services/`.
3. Create endpoint handlers in `endpoints/` with `APIRouter`.
4. Register the router in `main.py`.
5. Add/adjust SQL contract under `sql/` and validate in Supabase.
