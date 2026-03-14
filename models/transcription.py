from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class TranscriptionResponse(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None
    request_id: str
