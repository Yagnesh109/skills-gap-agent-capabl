import os
from pathlib import Path

from dotenv import load_dotenv

# Load the backend .env file before reading environment variables.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_gemini_api_key() -> str:
    """Return the Gemini API key from the environment."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY. Add it to backend/.env")
    return api_key


def get_gemini_model() -> str:
    """Return the Gemini model, allowing deployments to override the default."""
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
