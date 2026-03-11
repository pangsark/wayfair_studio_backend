# Wayfair Studio Backend

Backend API for the Wayfair Studio assembly assistant application.

## Getting Started

First, set up the python env:

```bash
python3 -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

If fastapi is not installed, run:
```bash
pip install "fastapi" "uvicorn[standard]" "python-dotenv"
```

Then to start the backend services:
```bash
uvicorn main:app --reload --port 4000
```

## Environment Variables

Create a `.env` file in the project root:

```env
PORT=4000
CORS_ORIGIN=http://localhost:3000
REPLICATE_API_TOKEN=your-replicate-api-token
DATABASE_URL=postgresql://wayfair:wayfair123@localhost:5432/wayfairstudio
```

## Database Setup

This only has to be done once

```bash
docker compose up -d
```

Update the `.env`:

```
DATABASE_URL=postgresql://wayfair:wayfair123@localhost:5432/wayfairstudio
```

Add some dummy data:

```bash
psql -h localhost -U wayfair -d wayfairstudio
```

```sql
INSERT INTO manuals (name, slug, description)
VALUES ('Test Manual', 'test-manual', 'This is a sample manual.');
```

```sql
INSERT INTO steps (manual_id, step_number, image_url)
VALUES 
(1, 1, 'https://example.com/step1.jpg'),
(1, 2, 'https://example.com/step2.jpg');
```

---

## API Endpoints

### Health Check

```
GET /health
```

Returns `{"status": "ok"}` if the server is running.

### List Manuals

```
GET /api/manuals
```

Returns a list of manuals for the switch-manual UI: `[{ "id", "name", "slug" }, ...]`.

### Step Explanation

```
GET /api/manuals/{manual_id}/steps/{step_id}/explanation
```

Returns the description/explanation for a given step in the specified manual.

### Step Tools

```
GET /api/steps/{step_id}/tools
```

Returns the list of tools needed for a given step.

### Step Image

```
GET /api/manuals/{manual_id}/steps/{step_id}/image?colorized=false
```

Returns the image URL for a step. Set `colorized=true` to get an AI-colorized version.

---
### Manual Segmentation API

This project now includes a POST endpoint that can ingest a PDF furniture
assembly manual and automatically break it into individual step images using
an AI model (Nano Banana Pro) and computer vision logic.

#### Endpoint

```
POST /api/v1/manuals/process
```

- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `file` (required) – the PDF file to process
  - `name` (optional) – human‑readable manual name
  - `slug` (optional) – URL slug for the manual
  - `description` (optional) – free‑text description

#### Response

Immediately returns a job identifier:

```json
{ "job_id": "<uuid>", "status": "processing" }
```

The frontend can poll `/api/v1/manuals/process/{job_id}` to check the job
status; the final payload includes the associated `manual_id` and
`step_count` once the work is complete.

#### Workflow (backend)

1. Save raw PDF to a temporary location
2. Convert pages to 300 DPI PNGs using `pdf2image`
3. Call the Nano Banana Pro model via Replicate; the model returns an
   "annotated" page with colored bounding boxes around each assembly step
4. Use OpenCV to subtract the annotated image from the clean image, find
   contours, and compute precise `(x,y,w,h)` crops
5. Crop the clean page and store each step in `public/manuals/<id>/stepN.png`
6. Insert step records into the database and mark the manual `COMPLETED`

If the AI fails to detect any boxes on a page the whole page becomes a single
step.  A missing `REPLICATE_API_TOKEN` is tolerated – the service will fall
back to treating each page as one step without calling the model.

> **Prerequisites:** The segmentation code depends on `pdf2image` which in
> turn requires Poppler (`poppler-utils` on Debian/Ubuntu).  Make sure
> `apt install poppler-utils` is run in the container or host.

---
## AI Chat Assistant

The chat endpoint provides an AI-powered assistant to help users with assembly questions. It uses OpenAI's GPT-4.1-mini model via Replicate.

### Endpoint

```
POST /api/manuals/{manual_id}/steps/{step_id}/chat
```

### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The user's question |
| `history` | array | No | Previous conversation messages for multi-turn chat |
| `image_url` | string | No | Image URL for vision-based questions |

### Response

```json
{
  "response": "AI-generated answer...",
  "manual_id": 1,
  "step_number": 1
}
```

### Examples

**Basic question:**

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What tools do I need for this step?"}'
```

**Multi-turn conversation:**

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you explain that in more detail?",
    "history": [
      {"role": "user", "content": "How do I attach the panels?"},
      {"role": "assistant", "content": "Insert panel 02 into the slots on panels 01..."}
    ]
  }'
```

**With image (vision):**

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What part is highlighted in this diagram?",
    "image_url": "https://example.com/step1-diagram.jpg"
  }'
```

### How It Works

1. The chat service gathers context from the current step:
   - Step description from `text_extraction.py`
   - Required tools list
2. Builds a system prompt with assembly assistant guidelines
3. Sends the user's question + context to GPT-4.1-mini via Replicate
4. Returns the AI's response

### Context Provided to AI

The AI receives:
- Current manual ID and step number
- Step description (what the user should do)
- Tools needed for the step
- Guidelines for being a helpful assembly assistant

---

## Project Structure

```
wayfair_studio_backend/
├── main.py                 # FastAPI app and endpoints
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # PostgreSQL database
├── .env                    # Environment variables
├── services/
│   ├── chat_service.py     # AI chat assistant logic
│   ├── text_extraction.py  # Step descriptions and tools
│   ├── step_colorizer.py   # Image colorization via Replicate
│   ├── db.py               # Database operations
│   └── db_columns.py       # Database column enums
└── static/
    └── images/             # Static image assets
```