# main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS setup so your Next.js frontend can call this
cors_origins = os.getenv("CORS_ORIGIN", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/steps/{step_id}/explanation")
def get_explanation(step_id: int):
    """
    Returns the magic number and explanation for a step.
    Shape matches what your frontend expects.
    """
    return {
        "step": step_id,
        "magicNumber": 42,
        "explanation": f"This is example server data for step {step_id}. The magic number is 42.",
    }