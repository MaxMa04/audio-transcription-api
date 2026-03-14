import base64
import json

import httpx
from pydantic import BaseModel


class OllamaProviderError(Exception):
    pass


class OllamaProviderBadResponse(OllamaProviderError):
    pass


class OllamaProviderTimeout(OllamaProviderError):
    pass


class OllamaTranscriptionResult(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


class OllamaWhisperProvider:
    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def healthcheck(self) -> bool:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaProviderTimeout("Ollama healthcheck timed out.") from exc
        except httpx.HTTPError as exc:
            raise OllamaProviderError("Ollama healthcheck failed.") from exc
        return True

    async def transcribe(self, audio_bytes: bytes) -> OllamaTranscriptionResult:
        payload = {
            "model": self.model,
            "prompt": (
                "Transcribe this audio and respond as JSON with keys "
                "text, language, duration."
            ),
            "stream": False,
            "format": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "language": {"type": ["string", "null"]},
                    "duration": {"type": ["number", "null"]},
                },
                "required": ["text"],
            },
            "audio": base64.b64encode(audio_bytes).decode("ascii"),
        }

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise OllamaProviderTimeout("Ollama request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaProviderError("Ollama returned an upstream error.") from exc
        except httpx.HTTPError as exc:
            raise OllamaProviderError("Failed to reach Ollama.") from exc

        data = response.json()
        raw_response = data.get("response")
        if not isinstance(raw_response, str) or not raw_response.strip():
            raise OllamaProviderBadResponse("Ollama returned an invalid transcription payload.")

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError:
            return OllamaTranscriptionResult(text=raw_response.strip())

        try:
            return OllamaTranscriptionResult.model_validate(parsed)
        except Exception as exc:
            raise OllamaProviderBadResponse(
                "Ollama returned an invalid transcription payload."
            ) from exc
