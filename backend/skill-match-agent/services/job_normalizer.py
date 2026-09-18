import re
from typing import Dict, Any, List

try:
    from ..schemas import JobPosting
    from .skill_extractor import clean_html_text, extract_skills_from_text
except (ImportError, ValueError):
    from schemas import JobPosting
    from services.skill_extractor import clean_html_text, extract_skills_from_text


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
    raw_id = str(raw_item.get("id") or f"jbl_{index}")
    job_id = f"JOOBLE-{raw_id}" if not raw_id.startswith("JOOBLE-") else raw_id

    title = clean_html_text(raw_item.get("title") or "Untitled Position")
    company = clean_html_text(raw_item.get("company") or "Company Not Disclosed")
    location = clean_html_text(raw_item.get("location") or "Remote")
    snippet = clean_html_text(raw_item.get("snippet") or "")
    job_url = raw_item.get("link") or raw_item.get("url") or ""

    # Extract required skills from title + description snippet
    combined_text = f"{title}. {snippet}"
    extracted_skills = extract_skills_from_text(combined_text)

    # Fallback if no skills could be matched from vocabulary
    if not extracted_skills:
        # Extract title keywords as fallback skills
        tokens = [
            w for w in re.findall(r'[A-Za-z]+', title)
            if len(w) > 2 and w.lower() not in ("developer", "engineer", "senior", "junior", "lead", "intern", "manager", "associate", "role", "specialist")
        ]
        extracted_skills = tokens[:4] if tokens else ["General Software Engineering"]

    return JobPosting(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        required_skills=extracted_skills,
        description=snippet,
        job_url=job_url,
        source="jooble"
    )


def normalize_jooble_jobs(raw_jobs: List[Dict[str, Any]]) -> List[JobPosting]:
    """Converts a collection of raw Jooble JSON job items into normalized JobPosting objects."""
    normalized_list = []
    for idx, item in enumerate(raw_jobs, start=1):
        if isinstance(item, dict):
            normalized_list.append(normalize_jooble_job(item, index=idx))
    return normalized_list
