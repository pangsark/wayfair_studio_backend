# main.py (in your backend root)

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pathlib import Path

from services.text_extraction import get_step_explanation, get_tools
from services.step_colorizer import get_step_image_path
from services.db import _ensure_table_exists

load_dotenv()

app = FastAPI()

@app.on_event("startup")
def startup_event():
    _ensure_table_exists()

cors_origins = os.getenv("CORS_ORIGIN", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mounting a static directory to serve images

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "public" / "images"

app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/steps/{step_id}/explanation")
def explanation_endpoint(step_id: int):
    return get_step_explanation(step_number = step_id)

@app.get("/api/steps/{step_id}/tools")
def checklist(step_id: int):
    return get_tools(step_number = step_id)

@app.get("/api/steps/{step_id}/image")
def step_image_endpoint(step_id: int, colorized: bool = False):
    """
    Returns the actual image file for this step and toggle state.
    Example test URL (in browser):
      http://localhost:4000/api/steps/1/image?colorized=true
    """
    try:
        image_path = get_step_image_path(step_id, colorized=colorized)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Image file not found on disk: {image_path}",
        )

    return FileResponse(path=str(image_path))
