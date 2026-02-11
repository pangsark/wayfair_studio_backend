# main.py (in your backend root)

import os
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path
from services.text_extraction import get_step_explanation, preload_manual_step_explanations
from services.db import _ensure_table_exists
from services.chat_service import get_chat_response


# Request model for chat endpoint
class ChatRequest(BaseModel):
    message: str
    history: Optional[list[dict]] = None
    image_url: Optional[str] = None  # Optional image for vision-based questions

load_dotenv()

app = FastAPI()

@app.on_event("startup")
def startup_event():
    _ensure_table_exists()
    thread = threading.Thread(
        target=preload_manual_step_explanations,
        kwargs={"manual_id": 1},
        daemon=True,
    )
    thread.start()

cors_origins = os.getenv("CORS_ORIGIN", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (images)
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "public" / "images"
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/steps/{step_id}/explanation")
def explanation_endpoint(step_id: int):
    return get_step_explanation(step_number = step_id)

@app.get("/api/steps/{step_id}/image")
def step_image_endpoint(step_id: int, colorized: bool = False):
    """
    Returns the image URL for this manual step.
    
    - If colorized=False: returns the base diagram from DB
    - If colorized=True: checks DB cache, falls back to Replicate API
    
    Example test URLs:
      http://localhost:4000/api/manuals/1/steps/1/image
      http://localhost:4000/api/manuals/1/steps/1/image?colorized=true
    """
    try:
        image_url = get_step_image_url(manual_id, step_id, colorized=colorized)
        return {"image_url": image_url, "colorized": colorized}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/manuals/{manual_id}/steps/{step_id}/chat")
def chat_endpoint(manual_id: int, step_id: int, request: ChatRequest):
    """
    AI chatbot endpoint for assembly assistance.
    
    Accepts a user message and optional conversation history,
    returns an AI response with context from the current step.
    
    Request body:
        - message: The user's question (required)
        - history: Optional list of previous messages for multi-turn chat
                   Format: [{"role": "user"|"assistant", "content": "..."}]
        - image_url: Optional image URL for vision-based questions
    
    Example:
        POST /api/manuals/1/steps/1/chat
        {"message": "What tools do I need for this step?"}
    """
    try:
        result = get_chat_response(
            manual_id=manual_id,
            step_number=step_id,
            user_message=request.message,
            conversation_history=request.history,
            image_url=request.image_url
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
