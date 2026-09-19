import re
from typing import Dict, Any, List, Union

try:
    from ..schemas import JobPosting
    from .skill_extractor import clean_html_text, extract_skills_from_text
except (ImportError, ValueError):
    from schemas import JobPosting
    from services.skill_extractor import clean_html_text, extract_skills_from_text


def normalize_job(
    raw_item: Union[Dict[str, Any], JobPosting],
    source: str = "demo",
    index: int = 1,
) -> JobPosting:
    """Normalize Jooble and local jobs into the same JobPosting contract."""
    if isinstance(raw_item, JobPosting):
        data = raw_item.model_dump(mode="python")
    elif isinstance(raw_item, dict):
        data = dict(raw_item)
    else:
        return None  # type: ignore[return-value]

    normalized_source = "jooble" if source == "jooble" else "demo"
    raw_id = str(data.get("id") or data.get("job_id") or f"job_{index}")
    if normalized_source == "jooble":
        job_id = f"JOOBLE-{raw_id}" if not raw_id.startswith("JOOBLE-") else raw_id
    else:
        job_id = raw_id

    title = clean_html_text(data.get("title") or data.get("job_title") or "Untitled Position")
    company = clean_html_text(data.get("company") or "Company Not Disclosed")
    location = clean_html_text(data.get("location") or "")
    description = clean_html_text(data.get("description") or data.get("snippet") or "")
    job_url = data.get("job_url") or data.get("link") or data.get("url") or ""

    required_skills = data.get("required_skills") or []
    if not isinstance(required_skills, list):
        required_skills = []
    required_skills = [str(skill).strip() for skill in required_skills if str(skill).strip()]
    if not required_skills:
        required_skills = extract_skills_from_text(f"{title}. {description}")

    if not required_skills and normalized_source == "jooble":
        required_skills = [
            token for token in re.findall(r"[A-Za-z]+", title)
            if len(token) > 2 and token.lower() not in {
                "developer", "engineer", "senior", "junior", "lead", "intern",
                "manager", "associate", "role", "specialist",
            }
        ][:4]

    return JobPosting(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        required_skills=required_skills,
        description=description,
        job_url=str(job_url or ""),
        source=normalized_source,
    )


def normalize_jobs(
    raw_jobs: List[Union[Dict[str, Any], JobPosting]],
    source: str = "demo",
) -> List[JobPosting]:
    """Normalize any supported source through one deterministic pipeline."""
    normalized = []
    for index, item in enumerate(raw_jobs or [], start=1):
        job = normalize_job(item, source=source, index=index)
        if job is not None:
            normalized.append(job)
    return normalized


def normalize_jooble_job(raw_item: Dict[str, Any], index: int = 1) -> JobPosting:
    """
    Transforms a single raw Jooble JSON item into standard JobPosting.
    
    Expected Jooble fields:
    - id: str or int
    - title: str
    - company: str
    - location: str
    - snippet: str
    - link: str
    """
    return normalize_job(raw_item, source="jooble", index=index)


def normalize_jooble_jobs(raw_jobs: List[Dict[str, Any]]) -> List[JobPosting]:
    """Converts a collection of raw Jooble JSON job items into normalized JobPosting objects."""
    return normalize_jobs(raw_jobs, source="jooble")


def normalize_demo_jobs(raw_jobs: List[Union[Dict[str, Any], JobPosting]]) -> List[JobPosting]:
    """Normalize local/demo jobs through the same pipeline as Jooble jobs."""
    return normalize_jobs(raw_jobs, source="demo")
