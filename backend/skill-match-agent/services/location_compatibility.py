import re
from typing import Optional


REMOTE_LOCATION_PATTERN = re.compile(
    r"\b(remote|work\s*from\s*home|wfh)\b",
    re.IGNORECASE,
)


def _clean_location(location: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(location or "")).strip()


def _city_key(location: str) -> str:
    """Use the first geographic segment for deterministic city comparison."""
    first_segment = re.split(r"[,|;/]", location, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]", "", first_segment.casefold())


def classify_location_compatibility(
    candidate_location: Optional[str],
    job_location: Optional[str],
) -> str:
    """Classify candidate/job location compatibility without external services."""
    candidate = _clean_location(candidate_location)
    job = _clean_location(job_location)

    if REMOTE_LOCATION_PATTERN.search(job):
        return "remote"
    if not candidate or not job:
        return "unknown"

    candidate_city = _city_key(candidate)
    job_city = _city_key(job)
    if not candidate_city or not job_city:
        return "unknown"
    return "same_city" if candidate_city == job_city else "different_city"