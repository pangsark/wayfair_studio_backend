# Frontend Chat Integration Guide

Quick reference for integrating the AI assembly chat assistant into the frontend.

## Endpoint

```
POST /api/manuals/{manual_id}/steps/{step_id}/chat
```

**Base URL**: `http://localhost:4000` (development)

---

## TypeScript Types

```typescript
// Request types
interface ChatRequest {
  message: string;           // Required: user's question
  history?: ChatMessage[];   // Optional: previous messages for context
  image_url?: string;        // Optional: image URL for vision questions
}

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

// Response type
interface ChatResponse {
  response: string;      // AI's answer
  manual_id: number;     // Echoed back
  step_number: number;   // Echoed back
}
```

---

## Basic Fetch Example

```typescript
async function sendMessage(
  manualId: number,
  stepId: number,
  message: string,
  history: ChatMessage[] = []
): Promise<string> {
  const res = await fetch(
    `${API_BASE}/api/manuals/${manualId}/steps/${stepId}/chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history })
    }
  );

  if (!res.ok) throw new Error('Chat request failed');
  
  const data: ChatResponse = await res.json();
  return data.response;
}
```

---

## React Hook

```typescript
import { useState, useCallback } from 'react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export function useChat(manualId: number, stepId: number) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(async (text: string) => {
    setIsLoading(true);
    setError(null);

    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: text }]);

    try {
      const res = await fetch(
        `/api/manuals/${manualId}/steps/${stepId}/chat`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, history: messages })
        }
      );

      if (!res.ok) throw new Error('Request failed');

      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
      // Remove the user message on error
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setIsLoading(false);
    }
  }, [manualId, stepId, messages]);

  const clear = useCallback(() => setMessages([]), []);

  return { messages, send, isLoading, error, clear };
}
```

**Usage:**

```tsx
function ChatPanel({ manualId, stepId }: Props) {
  const { messages, send, isLoading, error, clear } = useChat(manualId, stepId);
  const [input, setInput] = useState('');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      send(input);
      setInput('');
    }
  };

  return (
    <div>
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={msg.role}>
            {msg.content}
          </div>
        ))}
        {isLoading && <div className="loading">Thinking...</div>}
        {error && <div className="error">{error}</div>}
      </div>

      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about this step..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>Send</button>
      </form>

      <button onClick={clear}>Clear chat</button>
    </div>
  );
}
```

---

## Important Notes

### 1. History Management

The backend does NOT store conversation history. You must:
- Track messages in component state
- Send the full `history` array with each request
- Clear history when user navigates to a different step

```typescript
// When step changes, clear the chat
useEffect(() => {
  clear();
}, [stepId, clear]);
```

### 2. Step Context

The AI automatically receives context about the current step (description, tools needed). You don't need to include this in your messages - just send the user's question.

### 3. Image/Vision Questions

To ask about an image (e.g., "What's wrong with my assembly?"):

```typescript
await fetch(`/api/manuals/${manualId}/steps/${stepId}/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "What's wrong with my assembly in this photo?",
    image_url: "https://your-cdn.com/user-upload.jpg",
    history: messages
  })
});
```

### 4. Error Handling

The endpoint returns `500` for server errors. Handle gracefully:

```typescript
if (!res.ok) {
  if (res.status === 500) {
    setError("Sorry, the assistant is unavailable. Please try again.");
  } else {
    setError("Something went wrong.");
  }
}
```

---

## Quick Test

```bash
curl -X POST http://localhost:4000/api/manuals/1/steps/1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What tools do I need?"}'
```

Expected response:

```json
{
  "response": "For this step, you will need...",
  "manual_id": 1,
  "step_number": 1
}
```
