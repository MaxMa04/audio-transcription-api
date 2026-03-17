import logging
import re
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic_settings import BaseSettings, SettingsConfigDict

from middleware.auth import validate_api_key
from models.transcription import ErrorDetail, ErrorResponse, HealthResponse, TranscriptionResponse
from providers.ollama import (
    OllamaProviderBadResponse,
    OllamaProviderError,
    OllamaProviderTimeout,
)
from providers.whisper_local import WhisperLocalProvider

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REQUEST_ID_HEADER = "X-Request-ID"
MAX_TRANSCRIPT_WORDS = 10


class Settings(BaseSettings):
    app_env: str = "development"
    port: int = 8000
    api_keys: str = "changeme"
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    max_audio_size_mb: int = 10
    request_timeout_seconds: float = 30.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    logger.info(
        "Loading Whisper model=%s device=%s compute=%s",
        settings.whisper_model_size,
        settings.whisper_device,
        settings.whisper_compute_type,
    )
    app.state.provider = WhisperLocalProvider(
        model_size=settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    logger.info("Whisper model loaded successfully")
    yield


app = FastAPI(
    title="Audio Transcription API",
    version="1.0.0",
    openapi_version="3.1.0",
    lifespan=lifespan,
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def truncate_transcript(text: str, max_words: int = MAX_TRANSCRIPT_WORDS) -> str:
    words = re.findall(r"\S+", text.strip())
    return " ".join(words[:max_words])


def get_provider(request: Request) -> WhisperLocalProvider:
    return request.app.state.provider


async def require_api_key(
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_header)],
) -> None:
    await validate_api_key(request=request, api_key=api_key)


@app.middleware("http")
async def attach_request_context(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid.uuid4().hex}"
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error", extra={"request_id": request_id})
        raise
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    code_map = {
        status.HTTP_400_BAD_REQUEST: "invalid_request",
        status.HTTP_401_UNAUTHORIZED: "unauthorized",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "payload_too_large",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
        status.HTTP_502_BAD_GATEWAY: "bad_gateway",
        status.HTTP_504_GATEWAY_TIMEOUT: "gateway_timeout",
    }
    return build_error_response(
        status_code=exc.status_code,
        code=code_map.get(exc.status_code, "request_failed"),
        message=detail,
        request_id=request_id,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_request",
        message="Audio payload is missing or invalid.",
        request_id=get_request_id(request),
    )


@app.exception_handler(OllamaProviderTimeout)
async def ollama_timeout_handler(
    request: Request, exc: OllamaProviderTimeout
) -> JSONResponse:
    return build_error_response(
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        code="gateway_timeout",
        message=str(exc),
        request_id=get_request_id(request),
    )


@app.exception_handler(OllamaProviderError)
async def ollama_error_handler(
    request: Request, exc: OllamaProviderError
) -> JSONResponse:
    status_code = (
        status.HTTP_400_BAD_REQUEST
        if isinstance(exc, OllamaProviderBadResponse)
        else status.HTTP_502_BAD_GATEWAY
    )
    code = "invalid_request" if status_code == status.HTTP_400_BAD_REQUEST else "bad_gateway"
    return build_error_response(
        status_code=status_code,
        code=code,
        message=str(exc),
        request_id=get_request_id(request),
    )


@app.get("/v1/health", response_model=HealthResponse, tags=["health"])
async def healthcheck() -> HealthResponse:
    provider = app.state.provider
    await provider.healthcheck()
    return HealthResponse(status="ok")


@app.post(
    "/v1/transcriptions",
    response_model=TranscriptionResponse,
    response_model_exclude_none=True,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    tags=["transcriptions"],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def create_transcription(
    request: Request,
    _: Annotated[None, Depends(require_api_key)],
    provider: Annotated[WhisperLocalProvider, Depends(get_provider)],
) -> TranscriptionResponse:
    request_id = get_request_id(request)
    content_type = request.headers.get("content-type", "")
    if content_type.lower() != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/octet-stream.",
        )

    max_size_bytes = request.app.state.settings.max_audio_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > max_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio payload exceeds the maximum allowed size.",
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Audio payload is missing or invalid.",
            ) from exc

    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio payload is missing or invalid.",
        )

    if len(audio_bytes) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio payload exceeds the maximum allowed size.",
        )

    result = await provider.transcribe(audio_bytes)
    return TranscriptionResponse(
        text=truncate_transcript(result.text),
        language=result.language,
        duration=result.duration,
        request_id=request_id,
    )
