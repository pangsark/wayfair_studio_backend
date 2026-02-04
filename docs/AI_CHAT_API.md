# AI Chat Assistant API Documentation

The AI Chat Assistant helps users who are stuck during furniture assembly by providing contextual guidance based on the current step they're working on.

## Overview

- **Model**: OpenAI GPT-4.1-mini (hosted via Replicate)
- **Endpoint**: `POST /api/manuals/{manual_id}/steps/{step_id}/chat`
- **Features**: Text chat, multi-turn conversations, vision/image understanding

---

## API Reference

### POST `/api/manuals/{manual_id}/steps/{step_id}/chat`

Send a message to the AI assistant with context from the current assembly step.

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `manual_id` | integer | The ID of the assembly manual |
| `step_id` | integer | The current step number within the manual |

#### Request Body

```json
{
  "message": "string (required)",
  "history": "array (optional)",
  "image_url": "string (optional)"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | **Yes** | The user's question or message |
| `history` | array | No | Previous messages for multi-turn conversation |
| `image_url` | string | No | URL of an image for vision-based questions |

##### History Format

Each item in the `history` array should have:

```json
{
  "role": "user" | "assistant",
  "content": "The message content"
}
```

#### Response

```json
{
  "response": "The AI-generated answer",
  "manual_id": 1,
  "step_number": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `response` | string | The AI assistant's response |
| `manual_id` | integer | The manual ID (echoed back) |
| `step_number` | integer | The step number (echoed back) |

#### Error Responses

| Status Code | Description |
|-------------|-------------|
| 500 | Internal server error (API failure, missing config, etc.) |

---

## Usage Examples

### Basic Question

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What tools do I need for this step?"}'
```

### Multi-Turn Conversation

To maintain conversation context, include previous messages in the `history` array:

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you be more specific about the screws?",
    "history": [
      {"role": "user", "content": "What tools do I need?"},
      {"role": "assistant", "content": "For this step, you will need an Allen Wrench (A13) to insert and tighten screws."}
    ]
  }'
```

### Vision-Based Question

Pass an image URL to ask questions about a diagram or photo:

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Which panel is labeled 02 in this image?",
    "image_url": "https://your-storage.com/step1-diagram.png"
  }'
```

---

## Frontend Integration

### JavaScript/TypeScript Example

```typescript
interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ChatRequest {
  message: string;
  history?: ChatMessage[];
  image_url?: string;
}

interface ChatResponse {
  response: string;
  manual_id: number;
  step_number: number;
}

async function sendChatMessage(
  manualId: number,
  stepId: number,
  message: string,
  history: ChatMessage[] = []
): Promise<ChatResponse> {
  const response = await fetch(
    `http://localhost:4000/api/manuals/${manualId}/steps/${stepId}/chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history })
    }
  );
  
  if (!response.ok) {
    throw new Error(`Chat API error: ${response.status}`);
  }
  
  return response.json();
}

// Usage
const history: ChatMessage[] = [];

// First message
const response1 = await sendChatMessage(1, 1, "What tools do I need?", history);
console.log(response1.response);

// Add to history for follow-up
history.push({ role: 'user', content: "What tools do I need?" });
history.push({ role: 'assistant', content: response1.response });

// Follow-up message
const response2 = await sendChatMessage(1, 1, "Where do I find the Allen wrench?", history);
console.log(response2.response);
```

### React Hook Example

```typescript
import { useState, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export function useAssemblyChat(manualId: number, stepId: number) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (userMessage: string) => {
    setIsLoading(true);
    setError(null);

    // Add user message to UI immediately
    const newUserMessage: Message = { role: 'user', content: userMessage };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      const response = await fetch(
        `/api/manuals/${manualId}/steps/${stepId}/chat`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userMessage,
            history: messages
          })
        }
      );

      if (!response.ok) throw new Error('Failed to get response');

      const data = await response.json();
      
      // Add assistant response
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [manualId, stepId, messages]);

  const clearHistory = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, sendMessage, isLoading, error, clearHistory };
}
```

---

## Architecture

### Data Flow

```
┌──────────────┐     POST /chat      ┌──────────────────┐
│   Frontend   │ ──────────────────► │   FastAPI        │
│   (React)    │                     │   main.py        │
└──────────────┘                     └────────┬─────────┘
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │  chat_service.py │
                                     └────────┬─────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
                    ▼                         ▼                         ▼
           ┌────────────────┐       ┌────────────────┐       ┌────────────────┐
           │ text_extraction│       │   PostgreSQL   │       │   Replicate    │
           │ (step context) │       │   (DB cache)   │       │   (GPT-4.1)    │
           └────────────────┘       └────────────────┘       └────────────────┘
```

### Context Building

The chat service automatically enriches requests with step context:

1. **Step Description**: Retrieved from `text_extraction.get_step_explanation()`
2. **Tools List**: Retrieved from `text_extraction.get_tools()`
3. **System Prompt**: Combines context with assistant guidelines

### System Prompt Template

The AI receives a system prompt containing:

```
You are a helpful assembly assistant for Wayfair furniture...

You are currently helping with:
- Manual ID: {manual_id}
- Step {step_number}

## Current Step Information

**Description:**
{step_description}

**Tools needed for this step:**
{tools_list}

## Guidelines
1. Be clear, concise, and encouraging
2. Reference the specific step details when answering
3. If the user seems confused, break down the instructions into smaller sub-steps
4. Warn about common mistakes when relevant
5. If you don't have enough information to answer, say so honestly
6. Keep safety in mind - remind users to be careful with tools when appropriate
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REPLICATE_API_TOKEN` | Yes | Your Replicate API token for accessing GPT-4.1-mini |

### Model Configuration

The model is configured in `services/chat_service.py`:

```python
MODEL = "openai/gpt-4.1-mini"
```

---

## Limitations & Future Improvements

### Current Limitations

- **No streaming**: Responses are collected fully before returning (no real-time token streaming)
- **No persistence**: Conversation history must be managed client-side
- **Hardcoded context**: `text_extraction.py` uses hardcoded step descriptions (not real OCR/ML)

### Potential Enhancements

1. **Streaming responses**: Add SSE/WebSocket endpoint for real-time token delivery
2. **Session persistence**: Store conversations in PostgreSQL with session IDs
3. **Auto-include step images**: Automatically pass the current step's diagram to the vision model
4. **Rate limiting**: Add per-user rate limits to prevent abuse
5. **Analytics**: Log questions to understand common user pain points
