from typing import List, Union, Optional
from fastapi import APIRouter, HTTPException, status, Body, Query, Response

try:
    from .schemas import (
        SkillMatchRequest,
        SkillMatchResponse,
        JobMatchResult,
        UserProfile,
        JobPosting
    )
    from .services.matching_service import matching_service
    from .services.job_source_service import job_source_service
    from .services.jooble_service import jooble_service
    from .data.demo_jobs import get_demo_jobs
except (ImportError, ValueError):
    from schemas import (
        SkillMatchRequest,
        SkillMatchResponse,
        JobMatchResult,
        UserProfile,
        JobPosting
    )
    from services.matching_service import matching_service
    from services.job_source_service import job_source_service
    from services.jooble_service import jooble_service
    from data.demo_jobs import get_demo_jobs

router = APIRouter(
    prefix="/api/skill-match",
    tags=["Skill Match Agent"]
)


@router.post(
    "",
    response_model=List[JobMatchResult],
    status_code=status.HTTP_200_OK,
    summary="Match user profile skills against jobs (Jooble primary with Demo fallback)"
)
@router.post(
    "/match",
    response_model=List[JobMatchResult],
    status_code=status.HTTP_200_OK,
    summary="Match user profile skills against jobs (alias endpoint)"
)
async def match_skills(
    response: Response,
    payload: Union[UserProfile, SkillMatchRequest] = Body(
        ...,
        description="Candidate profile or skill match request"
    )
) -> List[JobMatchResult]:
    """
    Skill Matching Agent Endpoint with Jooble Integration & Demo Fallback.
    1. Validates incoming user profile / candidate skills.
    2. Queries Jooble API using user's skills/role and location.
    3. Seamlessly falls back to 50 local demo jobs if Jooble is unavailable or empty.
    4. Normalizes jobs into canonical JobPosting models.
    5. Computes exact overlap and semantic similarity scores.
    6. Tags each result with the data origin ('jooble' or 'demo').
    7. Returns jobs ranked in descending order of match score.
    """
    # Extract query parameters from payload
    if isinstance(payload, UserProfile):
        skills = payload.skills
        keywords = payload.target_role or ""
        location = payload.location or ""
        interests = payload.interests or []
        top_k = None
    elif isinstance(payload, SkillMatchRequest):
        skills = payload.candidate_skills or []
        keywords = payload.job_title or ""
        location = payload.location or ""
        interests = payload.user_profile.interests if payload.user_profile and payload.user_profile.interests else []
        top_k = payload.top_k
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid request payload. Expected UserProfile or SkillMatchRequest."
        )

    # 1. Fetch jobs from Jooble (primary) or local demo jobs (fallback)
    jobs, source = await job_source_service.get_jobs(
        keywords=keywords,
        location=location,
        candidate_skills=skills,
        interests=interests
    )

    # Inform client of job data source via HTTP header
    response.headers["X-Job-Source"] = source

    # 2. Rank jobs using matching engine
    ranked_results = matching_service.rank_jobs(
        candidate_skills=skills,
        jobs=jobs,
        top_k=top_k
    )

    # 3. Ensure source attribute is tagged on each result
    for res in ranked_results:
        res.source = source

    return ranked_results


@router.get(
    "/jobs",
    response_model=List[JobPosting],
    status_code=status.HTTP_200_OK,
    summary="Retrieve jobs directly from Job Source (Jooble primary, demo fallback)"
)
async def get_jobs_endpoint(
    response: Response,
    keywords: Optional[str] = Query(default="", description="Search keywords or job title"),
    location: Optional[str] = Query(default="", description="Search location or city"),
    force_demo: bool = Query(default=False, description="Force fallback to demo dataset")
) -> List[JobPosting]:
    """
    Direct endpoint for testing the job-source layer independently.
    Retrieves normalized JobPosting objects from Jooble or Demo fallback.
    """
    jobs, source = await job_source_service.get_jobs(
        keywords=keywords,
        location=location,
        force_demo=force_demo
    )
    response.headers["X-Job-Source"] = source
    return jobs


@router.get(
    "/demo-jobs",
    response_model=List[JobPosting],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all demo job postings"
)
async def list_demo_jobs():
    """Returns the complete dataset of 50 local demo job postings."""
    return get_demo_jobs()


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for Skill Match Agent"
)
async def health_check():
    """Health status check for the skill match agent module."""
    return {
        "status": "healthy",
        "agent": "skill-match-agent",
        "embedding_model": "all-MiniLM-L6-v2",
        "jooble_configured": jooble_service.has_api_key,
        "demo_jobs_count": len(get_demo_jobs())
    }
