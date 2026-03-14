"""Local Whisper provider using faster-whisper."""

import io
import tempfile

from pydantic import BaseModel

from providers.ollama import OllamaProviderError, OllamaProviderBadResponse


class WhisperTranscriptionResult(BaseModel):
    text: str
    language: str | None = None
    duration: float | None = None


class WhisperLocalProvider:
    """Transcription provider using faster-whisper running locally."""

    def __init__(self, model_size: str = "tiny", device: str = "cpu", compute_type: str = "int8") -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)

    async def healthcheck(self) -> bool:
        return True

    async def transcribe(self, audio_bytes: bytes) -> WhisperTranscriptionResult:
        try:
            with tempfile.NamedTemporaryFile(suffix=".audio", delete=True) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                segments, info = self.model.transcribe(tmp.name, beam_size=5)
                text = " ".join(seg.text.strip() for seg in segments)
        except Exception as exc:
            raise OllamaProviderBadResponse(f"Whisper transcription failed: {exc}") from exc

        return WhisperTranscriptionResult(
            text=text,
            language=info.language,
            duration=round(info.duration, 2),
        )
