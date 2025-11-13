import os
from dotenv import load_dotenv

load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL")

if not REPLICATE_API_TOKEN:
    raise EnvironmentError("Missing REPLICATE_API_TOKEN in .env file.")

if not REPLICATE_MODEL:
    raise EnvironmentError("Missing REPLICATE_MODEL in .env file")