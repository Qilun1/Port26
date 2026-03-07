from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
	"""Application settings loaded from .env and environment variables."""

	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

	app_name: str = "Port26 Weather API"
	app_version: str = "0.1.0"
	app_env: str = "development"

	frontend_origin: str = "http://localhost:5173"

	supabase_project_url: str = Field(alias="SUPABASE_PROJECT_URL")
	supabase_api_key: str = Field(alias="SUPABASE_API_KEY")
	supabase_sensors_table: str = "sensors"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	return Settings()


settings = get_settings()
