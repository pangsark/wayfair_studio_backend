# main.py (in your backend root)

import os
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from services.text_extraction import get_step_explanation, get_checklist, get_text, get_tools
from services.step_colorizer import get_step_image_path

load_dotenv()

app = FastAPI()

cors_origins = os.getenv("CORS_ORIGIN", "http://localhost:3000").split(",")

TEMPORARY_RESULTS = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Optional: if you still want static serving
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/steps/{step_id}/explanation")
def explanation_endpoint(step_id: int, background_tasks: BackgroundTasks):
    """
    Return default hardcoded explanation immediately.
    Launch background task to compute the real explanation.
    """
    default_data = get_step_explanation(step_id)

    # Run the replicate job in the background
    background_tasks.add_task(run_replicate_for_step, step_id)

    return {
        "status": "pending",
        "data": default_data      # returned instantly
    }


@app.get("/api/steps/{step_id}/tools")
def tools_endpoint(step_id: int, background_tasks: BackgroundTasks):
    """
    Return default hardcoded checklist immediately.
    Launch background task for real tool detection.
    """
    default_tools = get_checklist(step_id)

    background_tasks.add_task(run_replicate_for_step, step_id)

    return {
        "status": "pending",
        "data": default_tools
    }


@app.get("/api/steps/{step_id}/results")
def poll_results(step_id: int):
    """
    Frontend polls this to see whether Replicate has finished.
    """
    result = TEMPORARY_RESULTS.get(step_id)
    if result is None:
        return {"status": "pending"}

    return {
        "status": "ready",
        "data": result
    }


# ------------------------------------------------------------
# Background task (runs AFTER response is sent!)
# ------------------------------------------------------------

def run_replicate_for_step(step_id: int):
    """
    This runs in a background thread.
    Calls replicate, then stores results for the frontend to fetch.
    """
    try:
        explanation = get_text(step_id)
        tools = get_tools(step_id)

        TEMPORARY_RESULTS[step_id] = {
            "explanation": explanation,
            "tools": tools,
        }

    except Exception as e:
        TEMPORARY_RESULTS[step_id] = {
            "error": str(e)
        }

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
