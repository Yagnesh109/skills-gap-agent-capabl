import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend directory
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Application configuration settings."""

    # API Keys (loaded from environment)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    JOOBLE_API_KEY: str = os.getenv("JOOBLE_API_KEY", "")

    # Gemini LLM configuration
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    GEMINI_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))

    # Semantic Matching Model
    SENTENCE_TRANSFORMER_MODEL: str = os.getenv(
        "SENTENCE_TRANSFORMER_MODEL", "all-MiniLM-L6-v2"
    )

    # Jooble API Base URL
    JOOBLE_API_BASE_URL: str = "https://jooble.org/api"

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1")


settings = Settings()
