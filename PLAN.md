# Technischer Plan: Audio Transcription API

## 1. Architektur-Entscheidungen

### Zielbild
- Lokale Audio-Transkriptions-API fuer Voice-Command-Erkennung
- Betrieb ausschliesslich ueber `FastAPI` + `Ollama` + Whisper-Modell
- Keine externe OpenAI-API, kein Fallback, kein Hybrid-Modus

### Empfohlener Stack
- **Backend:** `FastAPI` mit Python 3.11
- **Transkriptions-Engine:** `Ollama` mit `whisper`
- **Containerisierung:** `Docker` und `docker-compose.yml`
- **Warum:** Minimaler Stack, lokaler Betrieb, einfache API-Schicht, klare Deployments

### API-Design
- **Stil:** REST API mit synchroner Antwort
- **Versionierung:** `/v1/...`
- **Input:** Raw Audio Bytes im Request Body
- **Content-Type:** `application/octet-stream`
- **Output:** Gekuerzte Antwort mit nur den ersten 5-10 Woertern des vollständigen Whisper-Transkripts

### Provider-Entscheidung
- Es gibt genau einen Provider: `OllamaWhisperProvider`
- Keine Provider-Abstraktion fuer OpenAI
- Konfiguration nur ueber lokale Ollama-Parameter:
  - `OLLAMA_BASE_URL`
  - `OLLAMA_MODEL=whisper`

### Verarbeitungspipeline
1. Request authentifizieren
2. Request-ID erzeugen oder aus Header uebernehmen
3. `Content-Type` auf `application/octet-stream` validieren
4. Optional `Content-Length` fuer Groessenpruefung verwenden
5. Raw Audio Bytes aus dem Request Body lesen
6. Dateigroesse und leere Payload validieren
7. Audio temporaer speichern oder als Stream an Ollama uebergeben
8. Vollstaendige Whisper-Transkription von Ollama abrufen
9. Transcript auf ca. 5-10 Woerter kuerzen
10. Normalisierte JSON-Response zurueckgeben
11. Temporaere Ressourcen aufraeumen

### Sicherheits- und Betriebsaspekte
- API-Key Auth fuer produktive Endpoints
- Request-Size-Limits
- Timeouts fuer Ollama-Requests
- Strukturierte Logs mit `request_id`
- Healthcheck fuer API und Ollama-Erreichbarkeit

## 2. API-Spec

### Basis
- **Base URL:** `/v1`
- **Auth:** Header `X-API-Key: <key>`
- **Content-Type:** `application/octet-stream`

### Endpoints

#### `POST /v1/transcriptions`
Erzeugt eine Transkription aus rohen Audio-Bytes.

**Request**
- Request Body enthaelt direkt die Audio-Bytes
- Header `Content-Type: application/octet-stream`
- Header `Content-Length` optional, aber fuer fruehe Groessenvalidierung empfohlen
- Optionaler Query-Parameter oder Header fuer Sprache nur dann, wenn spaeter benoetigt; initial kann Sprache durch Whisper erkannt werden

**Response 200**
```json
{
  "text": "schalte bitte das licht im",
  "language": "de",
  "duration": 1.8,
  "request_id": "req_123"
}
```

### Response-Regeln
- `text` enthaelt nur die ersten ca. 5-10 Woerter des vollstaendigen Transkripts
- Whisper liefert intern weiterhin das komplette Transkript
- Die API schneidet die Rueckgabe fuer den Use Case Voice Command Detection gezielt ab

### Fehlerantworten

#### `400 Bad Request`
- Leerer Request Body
- Ungueltige Audio-Payload

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Audio payload is missing or invalid.",
    "request_id": "req_124"
  }
}
```

#### `401 Unauthorized`
```json
{
  "error": {
    "code": "unauthorized",
    "message": "Invalid API key.",
    "request_id": "req_125"
  }
}
```

#### `413 Payload Too Large`
```json
{
  "error": {
    "code": "payload_too_large",
    "message": "Audio payload exceeds the maximum allowed size.",
    "request_id": "req_126"
  }
}
```

#### `415 Unsupported Media Type`
```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "Content-Type must be application/octet-stream.",
    "request_id": "req_127"
  }
}
```

#### `502 Bad Gateway`
- Ollama/Whisper antwortet mit Fehler

#### `504 Gateway Timeout`
- Timeout beim Aufruf von Ollama

### Zusatzendpoints

#### `GET /v1/health`
- Liveness/Readiness Check fuer API und Ollama

**Response 200**
```json
{
  "status": "ok"
}
```

### OpenAPI-Anforderungen
- OpenAPI 3.1
- Security Scheme fuer API-Key Header
- Request Body als `application/octet-stream`
- Schema fuer gekuerzte Transkriptions-Response
- Fehler-Schemas fuer 400/401/413/415/502/504
- Beispiele fuer Binary-Requests dokumentieren

## 3. Implementation-Steps

### Phase 1: Grundgeruest
- Projektstruktur aufsetzen
- FastAPI App, Router, Konfiguration und Dependency Injection definieren
- Dockerfile und `docker-compose.yml` anlegen
- Ollama-Service im Compose definieren
- Basis-Healthcheck implementieren

### Phase 2: Binary-Ingest
- Endpoint `POST /v1/transcriptions` implementieren
- `application/octet-stream` als einzigen Input unterstuetzen
- `Content-Length` optional fuer Groessenvalidierung auswerten
- Raw Body sicher einlesen
- Validierung fuer leere oder zu grosse Payloads einbauen

### Phase 3: Ollama-Integration
- `OllamaWhisperProvider` implementieren
- Anbindung an `OLLAMA_BASE_URL`
- Default-Modell ueber `OLLAMA_MODEL=whisper`
- Fehler- und Timeout-Mapping sauber auf API-Responses abbilden

### Phase 4: Transcript-Kuerzung
- Vollstaendiges Transcript von Whisper entgegennehmen
- Auf erste 5-10 Woerter kuerzen
- Rueckgabeformat auf `{ text, language, duration, request_id }` festlegen
- Regeln fuer Tokenisierung und Abschneiden deterministisch definieren

### Phase 5: Sicherheit und Betriebsreife
- API-Key Auth als Middleware oder Dependency
- Request-ID Middleware
- Strukturierte Fehlerklassen und globaler Exception Handler
- Logging, Timeouts und Basis-Metriken
- `.env.example` fuer lokale Konfiguration bereitstellen

## 4. Testing-Strategie

### Unit Tests
- Validierung von `application/octet-stream`
- Verhalten bei leerem Request Body
- Verhalten bei fehlendem oder falschem `Content-Length`
- Kuerzungslogik fuer erste 5-10 Woerter
- Fehler-Mapping von Ollama-Fehlern

### Integration Tests
- End-to-End Test fuer Binary-Audio-Upload
- Test mit gueltigem Audio und erwarteter gekuerzter Antwort
- Tests fuer `413` bei zu grosser Payload
- Tests fuer `415` bei falschem `Content-Type`
- Tests fuer `504` bei Ollama-Timeout

### Contract Tests
- OpenAPI-Spec gegen Implementierung validieren
- Response-Schema fuer `{ text, language, duration, request_id }` pruefen
- Negative Testfaelle fuer 400/401/413/415/502/504

### Performance-Tests
- Kleine Audio-Payloads parallel senden
- Latenz fuer Voice-Command-Use-Case messen
- Speicherverbrauch beim Einlesen von Raw Bytes beobachten

## 5. Deployment-Setup

### Docker Compose
- Service `api` fuer FastAPI
- Service `ollama` fuer lokales Modell-Serving
- Gemeinsames Netzwerk ueber Compose
- Persistentes Volume fuer Ollama-Modelle optional

### Environment Variables
- `APP_ENV`
- `PORT`
- `API_KEYS`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `MAX_AUDIO_SIZE_MB`
- `REQUEST_TIMEOUT_SECONDS`

### Empfohlene Initialentscheidung
- FastAPI + Ollama Whisper lokal in Docker Compose
- Einziger Ingest-Pfad ueber `application/octet-stream`
- API optimiert fuer kurze Voice-Command-Erkennung statt Volltranskription
