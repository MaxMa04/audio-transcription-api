"""End-to-end test using local Whisper provider with a real audio file."""

import sys
from unittest.mock import patch

from fastapi.testclient import TestClient
from providers.whisper_local import WhisperLocalProvider


def main():
    # Create a local whisper provider
    print("Loading Whisper tiny model...")
    provider = WhisperLocalProvider(model_size="tiny")

    # Patch the app to use local whisper instead of ollama
    from main import app, settings

    with TestClient(app) as client:
        # Override the provider
        app.state.ollama_provider = provider

        # Read the audio file
        with open("/Users/maxmannstein/Downloads/male_0_kmh.mp3", "rb") as f:
            audio_bytes = f.read()

        print(f"Audio file size: {len(audio_bytes)} bytes")
        print("Sending transcription request...")

        resp = client.post(
            "/v1/transcriptions",
            content=audio_bytes,
            headers={
                "X-API-Key": "changeme",
                "Content-Type": "application/octet-stream",
            },
        )

        print(f"\nStatus: {resp.status_code}")
        print(f"Response: {resp.json()}")

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert "text" in data
        assert "language" in data
        assert "request_id" in data
        assert data["language"] == "de"
        # Text should be truncated to max 10 words
        words = data["text"].split()
        assert len(words) <= 10, f"Expected <= 10 words, got {len(words)}: {data['text']}"

        print(f"\nTranscription (truncated): {data['text']}")
        print(f"Language: {data['language']}")
        print(f"Duration: {data.get('duration')}s")
        print(f"Request ID: {data['request_id']}")
        print("\nAll assertions passed!")


if __name__ == "__main__":
    main()
