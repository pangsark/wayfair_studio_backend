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
from services.db import _ensure_table_exists, get_cached_value
from services.db_columns import StepColumn
from services.chat_service import get_chat_response
from services.orientation_generator import start_orientation_generation
from services.step_colorizer import get_step_image_url
from services.lasso import save_lasso_screenshot, LassoImageData
from services.step_checklist import generate_checklist

BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / "public" / "images"

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
    expose_headers=["*"],
)

# custom middleware for image CORS headers
@app.middleware("http")
async def add_image_cors_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/images/"):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        response.headers["Cache-Control"] = "public, max-age=3600"
    return response

# Serve static files (images)
BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "public" / "images"
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/manuals/{manual_id}/steps/{step_id}/explanation")
def explanation_endpoint(manual_id: int, step_id: int):
    return get_step_explanation(
        manual_id=manual_id,
        step_number = step_id
    )


@app.get("/api/manuals/{manual_id}/steps/{step_id}/checklist")
def checklist_endpoint(manual_id: int, step_id: int):
    """
    Returns a dynamically generated checklist of actions for a specific step.
    """
    try:
        # Call the logic from services/step_checklist.py
        result = generate_checklist(manual_id=manual_id, step_number=step_id)
        return result
    except ValueError as e:
        # If the AI fails or the description is missing
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # For any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
    

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
    manual_id = 1  # Assuming single manual for now
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


def get_step_image_path(manual_id: int = 1, step_number: int = None):
    """
    Helper to get local file path for a given step
    """

    image_path = IMAGES_DIR / f"step{step_number}.png"
    if not image_path.exists():
        raise FileNotFoundError(f"Step image not found: {image_path}")
    return image_path


@app.post("/api/orientation/generate")
def generate_orientation_endpoint(manual_id: int, from_step: int, to_step: int):
    """
    Start background generation of orientation text for a step transition.
    Returns immediately without waiting for analysis to complete.
    
    Response: { "status": "started" or "completed" }
    """

    # Check cache
    cached_text = get_cached_value(
        manual_id,
        from_step,
        StepColumn.ORIENTATION_TEXT,
        returnMetadata=False
    )

    # If exists in db, return parsed JSON
    if cached_text:
        return {"status": "completed"}
    
    start_orientation_generation(
        manual_id=manual_id,
        from_step=from_step,
        to_step=to_step
    )
    return {"status": "started"}


@app.get("/api/orientation/text")
def get_orientation_text_endpoint(manual_id: int, step: int):
    """
    Get cached orientation text for a step.
    
    Response: { "text": null } or { "text": "{\"show_popup\": true, \"message\": \"...\"}" }
    """
    text = get_cached_value(manual_id, step, StepColumn.ORIENTATION_TEXT, returnMetadata=False)
    return {"text": text}

@app.post("/api/lasso/upload")
def lasso_upload_endpoint(data: LassoImageData):
    """Save lasso screenshot as lasso.png"""
    try:
        return save_lasso_screenshot(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

