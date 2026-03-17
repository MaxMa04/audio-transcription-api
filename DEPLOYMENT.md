# Deployment

## Server

| | |
|---|---|
| **Server** | Server 2 - Sekundärserver (fsmucais2) |
| **IP** | 192.168.57.6 |
| **Port** | 8100 |
| **API URL** | `http://192.168.57.6:8100` |
| **SSH User** | mmannstein |
| **Pfad auf Server** | `~/audio-transcription-api` |
| **GPU** | NVIDIA RTX PRO 6000 Blackwell (98 GB VRAM) |
| **Whisper-Modell** | faster-whisper large-v3 (CUDA) |

**VPN erforderlich** um den Server zu erreichen.

## SSH-Verbindung

```bash
sshpass -p 'eLvTSOY06BzkOl0N' ssh mmannstein@192.168.57.6
```

## Deployment durchführen

```bash
# 1. Auf den Server verbinden
sshpass -p 'eLvTSOY06BzkOl0N' ssh mmannstein@192.168.57.6

# 2. In das Projektverzeichnis wechseln
cd ~/audio-transcription-api

# 3. Neuesten Code ziehen
git pull

# 4. Container neu bauen und starten
docker compose up -d --build
```

### One-Liner (vom lokalen Rechner)

```bash
sshpass -p 'eLvTSOY06BzkOl0N' ssh mmannstein@192.168.57.6 "cd ~/audio-transcription-api && git pull && docker compose up -d --build"
```

## Service

| Container | Image | Beschreibung |
|-----------|-------|--------------|
| `audio-transcription-api-api-1` | CUDA 12.4 / Python 3.11 / FastAPI | API auf Port 8100, faster-whisper mit GPU |

GPU-Zugriff erfolgt über direkte Device-Mounts (`/dev/nvidia0` etc.) + NVIDIA-Libraries.

## API testen

```bash
# Health Check
curl http://192.168.57.6:8100/v1/health

# Transcription
curl -X POST http://192.168.57.6:8100/v1/transcriptions \
  -H "X-API-Key: fuso-transcribe-2025" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @audio.wav
```

### Beispiel-Response

```json
{
  "text": "Hello, this is a test of the Audio Transcription API.",
  "language": "en",
  "duration": 3.06,
  "request_id": "req_31ca66f527c84c87b9c99257076bcc29"
}
```

## Konfiguration

Die `.env`-Datei auf dem Server enthält:

| Variable | Wert |
|----------|------|
| `APP_ENV` | production |
| `PORT` | 8100 |
| `API_KEYS` | fuso-transcribe-2025 |
| `WHISPER_MODEL_SIZE` | large-v3 |
| `WHISPER_DEVICE` | cuda |
| `WHISPER_COMPUTE_TYPE` | float16 |
| `MAX_AUDIO_SIZE_MB` | 10 |
| `REQUEST_TIMEOUT_SECONDS` | 30 |

## Logs

```bash
# Auf dem Server
docker compose -f ~/audio-transcription-api/docker-compose.yml logs -f

# Remote
sshpass -p 'eLvTSOY06BzkOl0N' ssh mmannstein@192.168.57.6 "docker compose -f ~/audio-transcription-api/docker-compose.yml logs -f"
```

## Stoppen / Neustarten

```bash
cd ~/audio-transcription-api

# Stoppen
docker compose down

# Neustarten
docker compose up -d
```

## Hinweise

- Beim ersten Start dauert es einige Minuten, da das Whisper-Modell (~3GB) von HuggingFace heruntergeladen wird
- Das Modell wird im Container gecached - bei Restart ohne Rebuild ist es sofort verfügbar
- Die API kürzt Transkriptionen auf die ersten 10 Wörter (Voice-Command Use-Case)
- Unterstützte Audio-Formate: WAV, MP3, FLAC, etc. (alles was ffmpeg verarbeiten kann)
