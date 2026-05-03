# Wayfair Studio — Backend

FastAPI backend powering the Wayfair Studio furniture assembly assistant.

## Overview

This service provides:
- REST API for manuals, steps, and AI-powered assembly assistance
- PDF ingestion pipeline: upload a PDF → AI segments it into per-step images
- AI chat assistant (GPT-4.1-mini via Replicate) with structured JSON output and SSE streaming
- Voice transcription (Whisper large-v3) and text-to-speech (Kokoro-82m)
- Lasso screenshot analysis with contextual question generation
- 3D model viewer served as a static Three.js page
- Orientation-change detection between consecutive assembly steps

---

## Architecture

```
main.py                        FastAPI app, all routes, startup preloading
services/
  db.py                        PostgreSQL via psycopg2; safe no-ops when DB is absent
  db_columns.py                StepColumn enum (cacheable per-step columns)
  chat_service.py              GPT-4.1-mini chat with validated qa / procedural JSON output
  text_extraction.py           GPT-4o vision → step descriptions; preloaded at startup
  manual_processor.py          PDF → page PNGs → Nano Banana AI → bounding boxes → step crops
  orientation_generator.py     GPT-4.1-mini compares consecutive step images for rotation cues
  step_checklist.py            GPT-4o → per-step action checklist
  step_colorizer.py            Nano Banana reference-based diagram colorization
  lasso.py                     Saves lasso crops; GPT-4o analyzes the selection in context
  transcription.py             Replicate Whisper large-v3 audio transcription
  tts.py                       Kokoro-82m text-to-speech via Replicate
  spatial-viewer/index.html    Three.js GLB viewer, served as static files at /spatial_viewer/
scripts/
  seed_manual.py               One-off DB seed script for initial test data
public/manuals/                Step images served at /manuals/<id>/stepN.png
lasso_screenshots/             Lasso screenshot storage
static/images/                 Reference product images for colorization
docs/
  FRONTEND_CHAT_INTEGRATION.md Chat contract docs
```

---

## Prerequisites

- Python 3.10+
- Docker (for PostgreSQL)
- **Poppler** — required by `pdf2image` for the PDF ingestion pipeline
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `apt install poppler-utils`

---

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root (never commit this file):

```env
PORT=4000
CORS_ORIGIN=http://localhost:3000
REPLICATE_API_TOKEN=your-replicate-api-token
DATABASE_URL=postgresql://wayfair:wayfair123@localhost:5433/wayfairstudio
APP_URL=http://localhost:4000
```

| Variable | Description | Default |
|---|---|---|
| `PORT` | Port the server listens on | `4000` |
| `CORS_ORIGIN` | Comma-separated allowed origins | `http://localhost:3000` |
| `REPLICATE_API_TOKEN` | Replicate API key — required for all AI features | — |
| `DATABASE_URL` | PostgreSQL connection string | — |
| `APP_URL` | Public base URL used when constructing image URLs stored in the DB | `http://localhost:4000` |

> **Security note:** The `.gitignore` excludes `.env`. Ensure a fresh token is issued before handover — any token previously committed must be considered compromised.

---

## Database Setup

Start the bundled PostgreSQL 15 container (once only):

```bash
docker compose up -d
```

The app automatically creates all required tables on startup via `_ensure_table_exists()` in `services/db.py`. No manual migrations are needed.

The Docker Compose file maps the container's port 5432 to host port **5433**, so the connection string uses port 5433:

```
DATABASE_URL=postgresql://wayfair:wayfair123@localhost:5433/wayfairstudio
```

To seed initial test data:

```bash
python scripts/seed_manual.py
```

Or manually via psql:

```bash
psql -h localhost -p 5433 -U wayfair -d wayfairstudio
```

```sql
INSERT INTO manuals (name, slug) VALUES ('Test Manual', 'test-manual');
INSERT INTO steps (manual_id, step_number, image_url)
VALUES (1, 1, 'http://localhost:4000/manuals/1/step1.png');
```

---

## Run

```bash
uvicorn main:app --reload --port 4000
```

Visit `http://localhost:4000/health` to confirm the server is up.

---

## API Reference

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` |

---

### Manuals

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/manuals` | List all manuals `[{id, name, slug}]` |
| `GET` | `/api/manuals/{id}` | Get a single manual by ID |
| `POST` | `/api/manuals/process` | Upload PDF (`multipart/form-data`), start background ingestion. Returns `{job_id, status}` |
| `GET` | `/api/manuals/process/{job_id}` | Poll ingestion job status |
| `GET` | `/api/manuals/{id}/pages` | List pages with suggested and confirmed bounding boxes |
| `POST` | `/api/manuals/{id}/confirm-segmentation` | Submit confirmed/edited bounding boxes → triggers Phase 2 (crop step images) |

**POST `/api/manuals/process` fields (multipart/form-data):**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | PDF file | Yes | The PDF manual to process |
| `name` | string | No | Human-readable name |
| `slug` | string | No | URL slug |
| `description` | string | No | Free-text description |

---

### Steps

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/manuals/{id}/steps` | List steps. Uses DB if available, falls back to filesystem scan |
| `GET` | `/api/manuals/{id}/steps/{step}/explanation` | AI-generated step description (cached in DB) |
| `GET` | `/api/manuals/{id}/steps/{step}/checklist` | AI-generated action checklist (not cached — regenerated each call) |
| `GET` | `/api/manuals/{id}/steps/{step}/tools` | Tool list from DB cache |
| `GET` | `/api/manuals/{id}/steps/{step}/image` | Step image URL. Add `?colorized=true` for AI-colorized version |

---

### Chat

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/manuals/{id}/steps/{step}/chat` | Non-streaming chat response |
| `POST` | `/api/manuals/{id}/steps/{step}/chat-stream` | SSE streaming chat response |

**Request body (both endpoints):**

```json
{
  "message": "string (required)",
  "history": [{"role": "user|assistant", "content": "string"}],
  "image_url": "string (optional — step image URL for vision context)",
  "secondary_image_url": "string (optional — lasso crop URL for focused context)",
  "intent": "explain_step | orientation | stuck (optional)"
}
```

**Response payload — two shapes:**

```json
// Q&A (short factual answer)
{"type": "qa", "answer": "string", "why": "string (optional)"}

// Procedural (step-by-step guidance)
{
  "type": "procedural",
  "summary": "string",
  "steps": ["string"],          // optional — omit for prose-only answers
  "common_mistakes": ["string"] // optional — only included when intent is "stuck"
}
```

Non-streaming response envelope:

```json
{"payload": {...}, "manual_id": 1, "step_number": 1}
```

SSE stream format:

```
data: {"event":"final","payload":{...}}\n\n
data: [DONE]\n\n
data: [ERROR] <message>\n\n  (on failure)
```

**Word cap:** All string fields combined must not exceed 100 words (enforced by `STRUCTURED_WORD_CAP` in `chat_service.py`).

**Intent behavior:**
- `explain_step` — prefers a concise procedural summary or prose paragraph; no `common_mistakes`
- `orientation` — orientation-focused guidance
- `stuck` — procedural with `common_mistakes` when helpful
- `none` (default) — model's best judgment; `common_mistakes` omitted unless clearly helpful

---

### Orientation

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/orientation/generate` | Start background orientation analysis. Query params: `manual_id`, `from_step`, `to_step`. Returns `{status: "started"|"completed"}` |
| `GET` | `/api/orientation/text` | Retrieve cached orientation JSON. Query params: `manual_id`, `step`. Returns `{text: null}` or `{text: "{\"show_popup\":true,\"message\":\"...\"}"}` |

---

### Lasso

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/lasso/upload` | Upload a lasso crop and analyze it |

**Request body:**

```json
{"image_data": "base64 PNG string", "step": 1, "manual_id": 1}
```

**Response:**

```json
{"success": true, "summary": "string", "questions": ["string", "string"], "image_url": "string"}
```

---

### Voice

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/transcribe` | Transcribe audio. Body: `{"audio": "base64 string (data URI or raw)"}`. Returns `{"text": "string"}` |
| `POST` | `/api/tts` | Text-to-speech. Body: `{"text": "string", "voice": "af_nova"}`. Returns `{"audio_url": "string"}` |

Available TTS voices follow the Kokoro-82m voice naming convention (e.g. `af_nova`, `af_bella`).

---

### Static File Mounts

| URL prefix | Source directory | Contents |
|---|---|---|
| `/manuals/*` | `public/manuals/` | Step images (`stepN.png`) and 3D models (`stepN.glb`) |
| `/lasso_screenshots/*` | `lasso_screenshots/` | Saved lasso crop screenshots |
| `/spatial_viewer/*` | `services/spatial-viewer/` | Three.js GLB viewer page |

---

## PDF Ingestion Pipeline

Uploading a manual runs a two-phase pipeline:

### Phase 1 — PDF → Page Images + Bounding Box Suggestions

Triggered by `POST /api/manuals/process`. Runs in a background thread.

1. Convert each PDF page to a 300 DPI PNG via `pdf2image`
2. Send each page image to **Nano Banana 2** (`google/nano-banana-2`) on Replicate with a prompt instructing it to draw magenta rectangles around each assembly step
3. Use OpenCV to diff the annotated image against the original, detect magenta contours, extract `(x, y, w, h)` bounding boxes, and filter overlapping/noise boxes
4. Store page PNGs and suggested boxes in the `pages` table (status: `SUGGESTED`)
5. Job status transitions to `pending_segmentation`

If `REPLICATE_API_TOKEN` is not set, the model call is skipped and each page becomes a single step.

### Phase 2 — Confirmed Boxes → Cropped Step Images

Triggered by `POST /api/manuals/{id}/confirm-segmentation` after the user reviews/edits boxes in the frontend Segmentation Editor.

1. Frontend POSTs the confirmed bounding boxes (one set per page)
2. Backend crops each box from the original page PNG, saves `stepN.png` files under `public/manuals/<id>/`
3. Inserts step records into the `steps` table

---

## AI Models Used

| Model | Provider | Usage |
|---|---|---|
| `openai/gpt-4o` | Replicate | Step explanation (vision), lasso crop analysis, checklist generation |
| `openai/gpt-4.1-mini` | Replicate | Chat assistant, orientation change detection |
| `google/nano-banana-2` | Replicate | PDF segmentation — annotates page images with step bounding boxes |
| `google/nano-banana` | Replicate | Reference-based diagram colorization |
| `openai/whisper` (large-v3) | Replicate | Audio transcription |
| `jaaari/kokoro-82m` | Replicate | Text-to-speech synthesis |

All models are called via the [Replicate Python client](https://github.com/replicate/replicate-python) using either `replicate.run()` (blocking) or `replicate.stream()` (streaming).

---

## Database Schema

```sql
manuals (
  id               SERIAL PRIMARY KEY,
  name             TEXT NOT NULL,
  slug             TEXT UNIQUE NOT NULL,
  description      TEXT,
  product_image_url TEXT,   -- reference image used for colorization
  status           TEXT     -- PROCESSING | PENDING_SEGMENTATION | COMPLETED
)

steps (
  id               SERIAL PRIMARY KEY,
  manual_id        INTEGER REFERENCES manuals(id) ON DELETE CASCADE,
  step_number      INTEGER NOT NULL,
  description      TEXT,          -- AI-generated description, cached after first call
  tools            TEXT[],        -- tool list, cached
  image_url        TEXT NOT NULL,
  orientation_text JSONB,         -- {show_popup: bool, message: string}, cached
  UNIQUE(manual_id, step_number)
)

pages (
  id               SERIAL PRIMARY KEY,
  manual_id        INTEGER REFERENCES manuals(id) ON DELETE CASCADE,
  page_number      INTEGER NOT NULL,
  image_url        TEXT NOT NULL,
  suggested_boxes  JSONB,  -- AI-suggested [{x,y,w,h}]
  final_boxes      JSONB,  -- user-confirmed [{x,y,w,h}]
  status           TEXT,   -- SUGGESTED | CONFIRMED
  UNIQUE(manual_id, page_number)
)
```

The `db.py` module follows a "safe no-op" pattern: every function catches `RuntimeError` from `_get_connection()` and returns a sensible default (`None`, `[]`, or silently skips) when no `DATABASE_URL` is configured.

---

## Known Issues / Technical Debt

| Issue | Location | Impact |
|---|---|---|
| Hardcoded debug log path (`/Users/aaronzhang/Desktop/...`) | `services/db.py` — `_dbg_log` function and call sites | No functional impact (wrapped in try/except), but should be removed before production |
| In-memory job tracker | `manual_processor.py` — `JOBS` dict | Job state is lost on server restart; workers that survive a restart will have no visible status |
| Lasso file overwrite | `services/lasso.py` — always writes `lasso_screenshots/lasso.png` | Concurrent users overwrite each other's lasso screenshots |
| Colorization caching disabled | `services/step_colorizer.py` — `get_colorized_image_from_db` always returns `None` | Every `/image?colorized=true` request regenerates via Replicate; can be slow and costly |

---

## Project Structure

```
wayfair_studio_backend/
├── main.py                         FastAPI application, all routes, startup
├── requirements.txt                Python dependencies
├── docker-compose.yml              PostgreSQL 15 container (port 5433 on host)
├── .env                            Environment variables (gitignored — do not commit)
├── services/
│   ├── __init__.py
│   ├── db.py                       Database CRUD operations via psycopg2
│   ├── db_columns.py               StepColumn enum for cacheable DB columns
│   ├── chat_service.py             AI chat: prompt building, Replicate call, JSON validation
│   ├── text_extraction.py          Vision-based step description generation and caching
│   ├── manual_processor.py         PDF ingestion pipeline (Phase 1 + Phase 2)
│   ├── orientation_generator.py    Consecutive-step orientation analysis
│   ├── step_checklist.py           AI-generated per-step action checklist
│   ├── step_colorizer.py           Reference-based diagram colorization
│   ├── lasso.py                    Lasso crop upload, storage, and GPT-4o analysis
│   ├── transcription.py            Whisper audio-to-text transcription
│   ├── tts.py                      Kokoro-82m text-to-speech synthesis
│   └── spatial-viewer/
│       └── index.html              Standalone Three.js GLB viewer
├── scripts/
│   └── seed_manual.py              One-off database seed script
├── public/
│   └── manuals/                    Per-manual step images and 3D models
│       ├── 1/                      step1.png … stepN.png, step1.glb … stepN.glb
│       └── 2/
├── lasso_screenshots/              Saved lasso crop screenshots
├── static/
│   └── images/                     Reference product images (colored_drawer.png, etc.)
└── docs/
    └── FRONTEND_CHAT_INTEGRATION.md  Chat API contract documentation
```
