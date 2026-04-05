# Infinite Audio — AI Beat Launch System

FastAPI backend that takes beat metadata and returns a fully structured launch pack.

---

## Stack

- **FastAPI** — API framework
- **Pydantic v2** — request/response validation
- **pydantic-settings** — env-based config
- **OpenAI / Anthropic** — swappable AI provider
- **Uvicorn** — ASGI server

---

## Prerequisites

- Python 3.11+
- An OpenAI or Anthropic API key

---

## Local Setup

### 1. Clone and enter the project

```bash
git clone <your-repo>
cd infinite-audio-backend
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set your API key:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

To use Anthropic instead:

```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-opus-4-6
```

### 5. Run the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Server is live at: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

---

## API Reference

### `GET /health`

Confirms the server is running and shows the active provider/model.

```bash
curl http://localhost:8000/health
```

**Response**

```json
{
  "status": "ok",
  "provider": "openai",
  "model": "gpt-4o",
  "env": "development"
}
```

---

### `POST /generate-launch-pack`

Generates a full beat launch pack.

#### Request body

| Field | Type | Required | Description |
|---|---|---|---|
| `beat_name` | string | ✅ | Name of the beat |
| `bpm` | integer | ✅ | Tempo (40–300) |
| `mood` | string | ✅ | Mood descriptors, comma-separated |
| `genre` | string | ✅ | Primary genre |
| `subgenre` | string | ❌ | Optional subgenre |
| `target_artists` | string[] | ❌ | Up to 10 artist references |
| `description` | string | ❌ | Short free-text beat description |

#### curl

```bash
curl -X POST http://localhost:8000/generate-launch-pack \
  -H "Content-Type: application/json" \
  -d '{
    "beat_name": "Midnight Pressure",
    "bpm": 140,
    "mood": "dark, aggressive, cinematic",
    "genre": "drill",
    "subgenre": "UK drill",
    "target_artists": ["Central Cee", "Headie One"],
    "description": "Hard 808s, eerie strings, trap hi-hats"
  }'
```

#### Postman

1. Method: `POST`
2. URL: `http://localhost:8000/generate-launch-pack`
3. Headers: `Content-Type: application/json`
4. Body → Raw → JSON:

```json
{
  "beat_name": "Midnight Pressure",
  "bpm": 140,
  "mood": "dark, aggressive, cinematic",
  "genre": "drill",
  "subgenre": "UK drill",
  "target_artists": ["Central Cee", "Headie One"],
  "description": "Hard 808s, eerie strings, trap hi-hats"
}
```

#### Minimal request (required fields only)

```bash
curl -X POST http://localhost:8000/generate-launch-pack \
  -H "Content-Type: application/json" \
  -d '{
    "beat_name": "Golden Era",
    "bpm": 90,
    "mood": "nostalgic, soulful, boom bap",
    "genre": "hip-hop"
  }'
```

---

#### Response shape

```json
{
  "beat_name": "Midnight Pressure",
  "title_ideas": [
    "Midnight Pressure",
    "...",
    "...",
    "...",
    "..."
  ],
  "type_beat_positioning": {
    "primary_tag": "Central Cee Type Beat",
    "secondary_tags": ["Headie One Type Beat", "UK Drill Type Beat 2025"],
    "positioning_rationale": "..."
  },
  "youtube_pack": {
    "title": "Central Cee Type Beat - \"Midnight Pressure\" | UK Drill Instrumental 2025",
    "description": "...",
    "tags": ["central cee type beat", "uk drill type beat", "..."]
  },
  "short_form_content": {
    "tiktok": ["...", "...", "..."],
    "reels": ["...", "...", "..."],
    "shorts": ["...", "...", "..."]
  },
  "outreach_copy": {
    "artist_dm": "...",
    "collaborator_dm": "...",
    "email": {
      "subject": "...",
      "body": "..."
    }
  },
  "launch_plan": [
    { "day": 1, "title": "Upload day", "actions": ["...", "..."] },
    { "day": 2, "title": "...", "actions": ["...", "..."] },
    "..."
  ],
  "meta": {
    "model_used": "gpt-4o",
    "generated_at": "2026-03-19T10:00:00Z",
    "provider": "openai"
  }
}
```

---

## Project Structure

```
infinite-audio-backend/
├── app/
│   ├── main.py                        # App init, CORS, router registration
│   ├── config.py                      # Settings via pydantic-settings
│   ├── routes/
│   │   └── launch_pack.py             # POST /generate-launch-pack
│   ├── models/
│   │   ├── request.py                 # LaunchPackRequest
│   │   └── response.py                # LaunchPackResponse + sub-models
│   ├── services/
│   │   └── launch_pack_service.py     # Orchestration: prompt → AI → parse
│   ├── prompts/
│   │   └── launch_pack_prompt.py      # System prompt + user prompt builder
│   └── providers/
│       ├── base.py                    # Abstract AIProvider interface
│       ├── __init__.py                # Provider factory (get_provider())
│       ├── openai_provider.py         # OpenAI implementation
│       └── anthropic_provider.py      # Anthropic implementation
├── .env.example
├── requirements.txt
└── README.md
```

---

## Switching AI Providers

Change one line in `.env`:

```env
AI_PROVIDER=anthropic
```

No code changes needed. The factory in `app/providers/__init__.py` handles the rest.

To add a new provider (e.g. Google Gemini):

1. Create `app/providers/gemini_provider.py` subclassing `AIProvider`
2. Add an `elif provider == "gemini":` branch in `app/providers/__init__.py`
3. Add `GEMINI_API_KEY` and `GEMINI_MODEL` to `.env.example` and `config.py`

---

## Connecting a Lovable Frontend

The endpoint returns a single flat JSON object. In your Lovable React app:

```typescript
const res = await fetch("http://localhost:8000/generate-launch-pack", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(formData),
});
const launchPack = await res.json();
```

Map `launchPack.youtube_pack`, `launchPack.outreach_copy`, etc. directly to your UI sections.

For production, set `ALLOWED_ORIGINS` in `.env` to your Lovable deploy URL.

---

## Error Responses

| Status | Cause |
|---|---|
| `422` | Invalid request body (Pydantic validation failed) |
| `502` | AI provider API call failed (bad key, rate limit, etc.) |
| `500` | Unexpected server error |

---

## What's not in v1 (intentional)

- No auth — add `X-API-Key` middleware when moving to production
- No database — stateless by design
- No audio processing — text intelligence only
- No rate limiting — add `slowapi` when needed
- No queue — synchronous request/response is sufficient for MVP
