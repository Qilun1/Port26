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

## Endpoint Extension Pattern

When adding a new endpoint, follow this order:

1. Add or update response/request models in `schemas/`.
2. Implement business/data access logic in `services/`.
3. Create endpoint handlers in `endpoints/` with `APIRouter`.
4. Register the router in `main.py`.
5. Add/adjust SQL contract under `sql/` and validate in Supabase.
