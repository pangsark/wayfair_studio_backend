# main.py
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from services.text_extraction import get_step_explanation  # 👈 import the service

load_dotenv()

app = FastAPI()

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
def explanation_endpoint(step_id: int):
    """
    FastAPI endpoint that delegates to the text_extraction service.
    The response shape matches what your frontend expects.
    """
    return get_step_explanation(step_id)
