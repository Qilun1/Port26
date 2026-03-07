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
