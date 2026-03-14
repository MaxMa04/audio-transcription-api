from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    port: int = 8000
    api_keys: str = "changeme"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "whisper"
    max_audio_size_mb: int = 10
    request_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


class HealthResponse(BaseModel):
    status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    yield


app = FastAPI(
    title="Audio Transcription API",
    version="1.0.0",
    openapi_version="3.1.0",
    lifespan=lifespan,
)


@app.get("/v1/health", response_model=HealthResponse, tags=["health"])
async def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")
