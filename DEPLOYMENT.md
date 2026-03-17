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

## Services

| Container | Image | Beschreibung |
|-----------|-------|--------------|
| `audio-transcription-api-api-1` | Python 3.11 / FastAPI | API auf Port 8100 (intern 8000) |
| `audio-transcription-api-ollama-1` | ollama/ollama | Whisper-Modell (nur intern erreichbar) |

## API testen

```bash
# Health Check
curl http://192.168.57.6:8100/v1/health

# Transcription (Beispiel)
curl -X POST http://192.168.57.6:8100/v1/transcriptions \
  -H "X-API-Key: fuso-transcribe-2025" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @audio.wav
```

## Konfiguration

Die `.env`-Datei auf dem Server enthält:

| Variable | Wert |
|----------|------|
| `APP_ENV` | production |
| `PORT` | 8100 |
| `API_KEYS` | fuso-transcribe-2025 |
| `OLLAMA_MODEL` | whisper |
| `MAX_AUDIO_SIZE_MB` | 10 |
| `REQUEST_TIMEOUT_SECONDS` | 30 |

## Logs

```bash
# Alle Logs
docker compose -f ~/audio-transcription-api/docker-compose.yml logs -f

# Nur API
docker compose -f ~/audio-transcription-api/docker-compose.yml logs -f api

# Nur Ollama
docker compose -f ~/audio-transcription-api/docker-compose.yml logs -f ollama
```

## Stoppen / Neustarten

```bash
cd ~/audio-transcription-api

# Stoppen
docker compose down

# Neustarten
docker compose up -d
```
