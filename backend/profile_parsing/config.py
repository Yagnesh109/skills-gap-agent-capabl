import os
from pathlib import Path

from dotenv import load_dotenv

# Load the backend .env file before reading environment variables.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_gemini_api_key() -> str:
    """Return the Gemini API key for profile parsing (supports dedicated key or fallback)."""
    return (
        os.getenv("GEMINI_API_KEY_PROFILE_PARSING")
        or os.getenv("GEMINI_API_KEY_PARSER")
        or os.getenv("GEMINI_API_KEY_1")
        or os.getenv("GEMINI_API_KEY", "")
    ).strip()


def get_gemini_model() -> str:
    """Return the Gemini model, allowing deployments to override the default."""
    return os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()


def get_fallback_gemini_models() -> list[str]:
    """Return ordered list of Gemini models (only gemini-3.6-flash)."""
    primary = get_gemini_model()
    candidates = ["gemini-3.6-flash"]
    models = [primary] + [m for m in candidates if m != primary]
    return models

