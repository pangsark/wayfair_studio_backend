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
INSERT INTO steps (manual_id, step_number, image_url, image_alt)
VALUES 
(1, 1, 'https://example.com/step1.jpg', 'Step 1 image'),
(1, 2, 'https://example.com/step2.jpg', 'Step 2 image');
```

---

## API Endpoints

### Health Check

```
GET /health
```

Returns `{"status": "ok"}` if the server is running.

### Step Explanation

```
GET /api/steps/{step_id}/explanation
```

Returns the description/explanation for a given step.

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