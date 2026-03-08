from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from endpoints import interpolation_router, sensors_router

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
	CORSMiddleware,
	allow_origins=[settings.frontend_origin],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/", tags=["health"])
def healthcheck() -> dict[str, str]:
	return {"status": "ok", "environment": settings.app_env}


app.include_router(sensors_router)
app.include_router(interpolation_router)
