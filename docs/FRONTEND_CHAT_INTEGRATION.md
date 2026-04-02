# Frontend integration: AI chat (Assembly Assistant)

This document is for the **frontend team**. It describes the **current backend contract**, what the backend was changed to support, and what you should implement in the UI.

**Problem this addresses:** Previously, chat could surface as a numbered “Steps” list for almost every question (including simple ones like “where do screws go?”). The backend now returns structured **`qa`** (plain prose) or **`procedural`** with an optional **`steps`** array, and the UI must **only** render a numbered list when `steps` exists and is non-empty—see items 5–6 below and [Payload schema](#payload-schema-what-you-render).

---

## Summary of backend behavior (what changed)

The chat API no longer returns a single markdown string. The backend:

1. **Structured JSON only** — The model is instructed to return **only JSON** matching one of two shapes: `type: "qa"` or `type: "procedural"`. The server **parses and validates** this JSON and retries (up to 3 attempts) if invalid.

2. **SSE for streaming** — `POST .../chat-stream` returns **Server-Sent Events** (`text/event-stream`). Each meaningful line is a JSON object on a `data:` line, ending with `data: [DONE]`.

3. **Optional `intent`** — Request body may include `intent` for preset quick actions: `explain_step` | `orientation` | `stuck`. The backend passes this into the system prompt and enforces some rules (see below).

4. **Conditional `common_mistakes`** — On `procedural` payloads, **`common_mistakes` is only allowed when `intent === "stuck"`**. If `intent` is anything else, the backend **rejects** payloads that include `common_mistakes`.

5. **Optional `steps` on `procedural`** — **`steps` is no longer required.** The model may return `procedural` with only `summary` (no `steps`) so the UI does not show a numbered list for every answer.

6. **`qa` vs `procedural`** — The backend prompt steers **short factual questions** (e.g. “where do screws go?”) to **`qa`** with a plain `answer` string. **Numbered `steps`** should appear only when the user needs a real sequence or uses intents that warrant a walkthrough.

7. **Word cap** — Total words across all string fields in the chosen payload are capped (see `STRUCTURED_WORD_CAP` in `services/chat_service.py`; currently **100** words). The prompt text matches this.

8. **Non-stream endpoint** — `POST .../chat` returns JSON with a top-level **`payload`** object (not `response` with raw markdown).

---

## Endpoints

| Method | Path | Use case |
|--------|------|----------|
| `POST` | `/api/manuals/{manual_id}/steps/{step_id}/chat` | Full response in one JSON body |
| `POST` | `/api/manuals/{manual_id}/steps/{step_number}/chat-stream` | SSE stream with final structured payload |

Base URL example: `http://localhost:4000` (or your deployed API origin).

---

## Request body (both endpoints)

Same shape for `/chat` and `/chat-stream`:

```json
{
  "message": "string (required)",
  "history": [
    { "role": "user" | "assistant", "content": "string" }
  ],
  "image_url": "optional URL",
  "secondary_image_url": "optional URL",
  "intent": "explain_step | orientation | stuck | omit"
}
```

- **`history`** — Optional; format is up to your app, but should match what you send for multi-turn context.
- **`intent`** — Optional. Use for **preset buttons** (see below). Omit or send any other value → treated as `none` on the backend.

---

## Response: non-stream (`/chat`)

```json
{
  "payload": {
    "type": "qa" | "procedural",
    ...
  },
  "manual_id": 1,
  "step_number": 4
}
```

Read the assistant message from **`payload`**, not `response`.

---

## Response: stream (`/chat-stream`)

- **Content-Type:** `text/event-stream`
- Each event line looks like: `data: <single-line JSON>\n\n`
- Stream ends with: `data: [DONE]\n\n`
- On failure: `data: [ERROR] <human-readable message>\n\n`

**Current behavior:** the backend typically emits **one** JSON object before `[DONE]`:

```json
{"event": "final", "payload": { ... }}
```

Parse each `data:` line as JSON when it starts with `{`. Ignore `data: [DONE]` and handle `data: [ERROR] ...` as a terminal error state.

---

## Payload schema (what you render)

### `type: "qa"`

Use for **paragraph-style** answers (no numbered list from the backend).

```json
{
  "type": "qa",
  "answer": "string (required)",
  "why": "string (optional)"
}
```

**UI:** Render `answer` (and optionally `why`) as **plain text or markdown paragraphs**, not as an ordered list.

---

### `type: "procedural"`

```json
{
  "type": "procedural",
  "summary": "string (required)",
  "steps": ["string", "..."],
  "common_mistakes": ["string", "..."]
}
```

- **`summary`** — Always present; use as title or lead text.
- **`steps`** — **Optional.** If **missing or empty**, do **not** render a numbered list. Show **`summary` only** (or summary + other sections you add).
- **`common_mistakes`** — Only present when allowed by backend rules; when `intent !== "stuck"`, the backend should not return this field.

**UI rules:**

1. **Numbered list:** Render `steps` as `<ol>` / numbered list **only if** `Array.isArray(payload.steps) && payload.steps.length > 0`.
2. **No fake list:** If there are no steps, do not synthesize “1.” from `summary`.
3. **Common mistakes:** If `common_mistakes` exists and has length, show as a bullet list (or your design system equivalent).

---

## Preset intents (quick actions)

Suggested mapping for the three buttons:

| Button label | `intent` value | Suggested `message` (example) |
|--------------|----------------|----------------------------------|
| Explain this step | `explain_step` | `"Explain this step"` |
| How should parts be oriented? | `orientation` | `"How should parts be oriented?"` |
| I'm stuck | `stuck` | `"I'm stuck"` or similar |

Send the same JSON body as a normal message, with **`intent` set** and **`message`** / **`history`** aligned with your chat state.

**Backend rules affecting UI:**

- For **`stuck`**, `common_mistakes` may appear on `procedural` responses.
- For **`explain_step`** and **`orientation`**, expect **no** `common_mistakes` from validated payloads.

---

## Images (optional)

If the user is asking about the diagram, pass:

- `image_url` — e.g. full URL to the step image served by this app (`/manuals/{id}/stepN.png` or your API’s image URL).
- `secondary_image_url` — e.g. lasso crop URL if your app supports it.

The backend resolves local URLs to files when possible.

---

## Voice (if applicable)

Separate endpoints exist (not part of chat payload parsing):

- `POST /api/transcribe` — speech → text
- `POST /api/tts` — text → audio URL

Chat still uses the same structured **`payload`** after transcription.

---

## Frontend implementation checklist

- [ ] **SSE client:** Parse `data:` lines as JSON; handle `event: "final"` and read `payload`.
- [ ] **Branch on `payload.type`:** `qa` vs `procedural` with different layouts.
- [ ] **Lists:** Numbered list **only** when `procedural.steps?.length > 0`.
- [ ] **Common mistakes:** Section visible only if `common_mistakes?.length > 0`.
- [ ] **Errors:** Show `data: [ERROR] ...` to the user.
- [ ] **Preset buttons:** Send `intent` + `message` (+ `history` per your app).
- [ ] **Non-stream:** If you use `/chat`, read **`response.payload`**, not `response.response`.

---

## Backend files (reference for engineers)

| Area | File |
|------|------|
| Request model, SSE route | `main.py` (`ChatRequest`, `chat-stream`) |
| Prompt, validation, Replicate | `services/chat_service.py` |

---

## Changelog (high level)

- **Structured JSON** responses with validation + retries.
- **SSE** `chat-stream` with single-line JSON `data:` frames and `[DONE]`.
- **`intent`** on requests for preset flows.
- **`procedural.steps`** optional; **`common_mistakes`** only with `intent === "stuck"` (enforced server-side).
- **Prompt** prefers **`qa`** for short factual questions to avoid numbered lists everywhere.
- **`/chat`** returns `{ payload, manual_id, step_number }` instead of a raw `response` string.

For a shorter API summary, see **AI Chat Assistant** in the repo root [`README.md`](../README.md).
