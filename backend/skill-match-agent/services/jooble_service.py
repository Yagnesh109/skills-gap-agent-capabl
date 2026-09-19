import time
import logging
from typing import List, Dict, Any, Optional
import httpx

try:
    from backend.config import settings
except (ImportError, ValueError):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from config import settings

logger = logging.getLogger(__name__)

# Request timeout in seconds
JOOBLE_REQUEST_TIMEOUT: float = 8.0

# Cache TTL in seconds (10 minutes)
CACHE_TTL_SECONDS: int = 600


class JoobleService:
    """
    Service client for Jooble Job Search API.
    Interacts with https://jooble.org/api/{JOOBLE_API_KEY} via HTTP POST.
    Includes in-memory TTL caching and safe error handling.
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key if api_key is not None else settings.JOOBLE_API_KEY
        self._cache: Dict[str, Dict[str, Any]] = {}

    @property
    def has_api_key(self) -> bool:
        """Returns True if a non-empty API key is configured."""
        return bool(self._api_key and self._api_key.strip())

    def _get_cache_key(self, keywords: str, location: str, page: int) -> str:
        """Generates cache key based on normalized query parameters."""
        k = (keywords or "").strip().lower()
        loc = (location or "").strip().lower()
        return f"{k}:::{loc}:::{page}"

    def _get_from_cache(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """Returns cached items if valid and not expired."""
        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if time.time() - entry["timestamp"] < CACHE_TTL_SECONDS:
                logger.debug(f"Serving Jooble search from memory cache for key: {cache_key}")
                return entry["data"]
            else:
                del self._cache[cache_key]
        return None

    def _set_cache(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """Saves search results in memory cache with current timestamp."""
        self._cache[cache_key] = {
            "timestamp": time.time(),
            "data": data
        }

    async def search_jobs(
        self,
        keywords: str,
        location: str = "",
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Executes a job search query against Jooble API.
        
        Args:
            keywords: Target keywords or skills (e.g. 'Python FastAPI')
            location: Target city or region (e.g. 'Pune')
            page: Page number for pagination (1-indexed)
            
        Returns:
            List of raw job dictionaries returned by Jooble, or empty list on failure.
        """
        if not self.has_api_key:
            logger.info("Jooble API key not configured. Skipping external request.")
            return []

        cache_key = self._get_cache_key(keywords, location, page)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        # Construct endpoint URL with API key
        endpoint_url = f"{settings.JOOBLE_API_BASE_URL}/{self._api_key}"
        payload = {
            "keywords": (keywords or "").strip(),
            "location": (location or "").strip(),
            "page": max(1, page)
        }

        masked_key = f"{self._api_key[:4]}...{self._api_key[-4:]}" if len(self._api_key) > 8 else "***"
        logger.info(f"Querying Jooble API (key: {masked_key}) with keywords='{payload['keywords']}', location='{payload['location']}'")

        try:
            async with httpx.AsyncClient(timeout=JOOBLE_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    endpoint_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])
                    if isinstance(jobs, list):
                        self._set_cache(cache_key, jobs)
                        return jobs
                    return []
                else:
                    logger.warning(
                        f"Jooble API returned non-200 status: {response.status_code}. "
                        "Falling back to local demo jobs."
                    )
                    return []

        except httpx.TimeoutException:
            logger.warning("Jooble API request timed out. Falling back to local demo jobs.")
            return []
        except httpx.HTTPError as err:
            logger.warning(f"Jooble API HTTP error occurred: {type(err).__name__}. Falling back to local demo jobs.")
            return []
        except Exception as ex:
            logger.error(f"Unexpected error during Jooble request: {type(ex).__name__}. Falling back to local demo jobs.")
            return []


# Global singleton client instance
jooble_service = JoobleService()
