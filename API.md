# API Dokumentation – Audio Transcription API

## Übersicht

Die Audio Transcription API transkribiert Audio-Dateien und gibt die ersten 10 Wörter des Transkripts zurück. Der Use-Case ist Voice-Command-Erkennung: kurze Sprachbefehle schnell und zuverlässig auswerten.

**Base URL:** `http://192.168.57.6:8100`

> VPN-Verbindung erforderlich (siehe Setup-Docs).

---

## Voraussetzungen

### Netzwerk
- VPN muss aktiv sein (Subnetz `192.168.57.x`)
- Ohne VPN ist der Server nicht erreichbar

### Authentifizierung
- Jeder Request an `/v1/transcriptions` benötigt einen API-Key
- Der Key wird als HTTP-Header mitgeschickt: `X-API-Key: <key>`

### Audio-Format
- **Content-Type:** `application/octet-stream` (zwingend)
- **Unterstützte Formate:** WAV, MP3, FLAC, OGG, M4A – alles was ffmpeg verarbeiten kann
- **Maximale Dateigröße:** 10 MB
- **Empfohlene Einstellungen:** 16 kHz Sample Rate, Mono – für optimale Erkennungsqualität

---

## Endpoints

### `GET /v1/health`

Prüft ob die API und das Whisper-Modell betriebsbereit sind.

**Authentifizierung:** nicht erforderlich

**Request**
```bash
curl http://192.168.57.6:8100/v1/health
```

**Response 200**
```json
{
  "status": "ok"
}
```

---

### `POST /v1/transcriptions`

Transkribiert eine Audio-Datei. Gibt die ersten 10 Wörter des erkannten Textes zurück.

**Authentifizierung:** erforderlich (`X-API-Key` Header)

**Request Headers**

| Header | Wert | Pflicht |
|--------|------|---------|
| `X-API-Key` | API-Schlüssel | ja |
| `Content-Type` | `application/octet-stream` | ja |
| `Content-Length` | Dateigröße in Bytes | empfohlen |
| `X-Request-ID` | Eigene Request-ID | nein |

**Request Body**

Rohe Audio-Bytes (kein Multipart, kein JSON – direkt die Binärdaten).

**Beispiel mit curl**
```bash
curl -X POST http://192.168.57.6:8100/v1/transcriptions \
  -H "X-API-Key: fuso-transcribe-2025" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @aufnahme.wav
```

**Beispiel mit Python**
```python
import requests

with open("aufnahme.wav", "rb") as f:
    audio_bytes = f.read()

response = requests.post(
    "http://192.168.57.6:8100/v1/transcriptions",
    headers={
        "X-API-Key": "fuso-transcribe-2025",
        "Content-Type": "application/octet-stream",
    },
    data=audio_bytes,
)

print(response.json())
```

**Beispiel mit JavaScript (fetch)**
```javascript
const fs = require("fs");

const audioBytes = fs.readFileSync("aufnahme.wav");

const response = await fetch("http://192.168.57.6:8100/v1/transcriptions", {
  method: "POST",
  headers: {
    "X-API-Key": "fuso-transcribe-2025",
    "Content-Type": "application/octet-stream",
  },
  body: audioBytes,
});

const result = await response.json();
console.log(result);
```

**Response 200**
```json
{
  "text": "schalte bitte das licht im",
  "language": "de",
  "duration": 1.8,
  "request_id": "req_abc123"
}
```

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `text` | string | Transkription, auf 10 Wörter gekürzt |
| `language` | string | Erkannte Sprache (ISO 639-1, z.B. `de`, `en`) |
| `duration` | number | Audio-Länge in Sekunden |
| `request_id` | string | Eindeutige ID des Requests (für Debugging) |

---

## Fehlercodes

| HTTP Status | Code | Ursache |
|-------------|------|---------|
| `400` | `invalid_request` | Leerer Body oder ungültige Audio-Payload |
| `401` | `unauthorized` | Fehlender oder falscher API-Key |
| `413` | `payload_too_large` | Audio-Datei größer als 10 MB |
| `415` | `unsupported_media_type` | `Content-Type` ist nicht `application/octet-stream` |
| `502` | `bad_gateway` | Whisper-Modell hat einen Fehler zurückgegeben |
| `504` | `gateway_timeout` | Transkription hat zu lange gedauert (Timeout: 30s) |

**Fehler-Response Format**
```json
{
  "error": {
    "code": "unauthorized",
    "message": "Invalid API key.",
    "request_id": "req_abc123"
  }
}
```

---

## Tipps

**Audio vorbereiten für beste Ergebnisse**
```bash
# WAV konvertieren (16 kHz, Mono)
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

**Request-ID für Debugging mitschicken**
```bash
curl -X POST http://192.168.57.6:8100/v1/transcriptions \
  -H "X-API-Key: fuso-transcribe-2025" \
  -H "Content-Type: application/octet-stream" \
  -H "X-Request-ID: mein-custom-id-123" \
  --data-binary @aufnahme.wav
```
Die gleiche ID taucht in der Response und in den Server-Logs auf – nützlich um einzelne Requests nachzuverfolgen.
