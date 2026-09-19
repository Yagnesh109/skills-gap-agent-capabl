from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Body

try:
    from .schemas import (
        GapAnalysisRequest,
        GapAnalysisResponse,
        SingleJobGapAnalysis,
        GapAnalysisJobInput,
        LegacyGapAnalysisRequest,
        LegacyGapAnalysisResponse,
        SkillGapItem,
        AiReasoning,
    )
    from .services.gap_analysis_service import (
        gap_analysis_service,
        dedupe_skill_list,
        analyze_single_job_gap,
        compute_metadata,
    )
    from .services.analyzer_service import analyzer_service
    from .services.gemini_service import (
        GeminiService,
        gemini_service as _default_gemini_service,
    )
except (ImportError, ValueError):
    from schemas import (  # type: ignore
        GapAnalysisRequest,
        GapAnalysisResponse,
        SingleJobGapAnalysis,
        GapAnalysisJobInput,
        LegacyGapAnalysisRequest,
        LegacyGapAnalysisResponse,
        SkillGapItem,
        AiReasoning,
    )
    from services.gap_analysis_service import (  # type: ignore
        gap_analysis_service,
        dedupe_skill_list,
        analyze_single_job_gap,
        compute_metadata,
    )
    from services.analyzer_service import analyzer_service  # type: ignore
    from services.gemini_service import (  # type: ignore
        GeminiService,
        gemini_service as _default_gemini_service,
    )


router = APIRouter(
    prefix="/api/gap-analysis",
    tags=["Gap Analysis Agent"]
)

# Module-level override hook for tests.
# Set to a GeminiService instance to replace the default service during tests
# without leaking implementation details into HTTP endpoint signatures.
_GEMINI_SERVICE_OVERRIDE: Optional[GeminiService] = None


def _set_gemini_service_override(svc: Optional[GeminiService]) -> None:
    """Internal helper for tests: overrides the Gemini service used by endpoints.
    Pass None to return to the default env-configured singleton.
    """
    global _GEMINI_SERVICE_OVERRIDE
    _GEMINI_SERVICE_OVERRIDE = svc


def _get_gemini_service() -> GeminiService:
    """Return the active GeminiService instance to use."""
    if _GEMINI_SERVICE_OVERRIDE is not None:
        return _GEMINI_SERVICE_OVERRIDE
    return _default_gemini_service


def _extract_user_skills(request: GapAnalysisRequest) -> List[str]:
    """Resolve candidate_skills from request body (user_profile.skills wins tie)."""
    skills: List[str] = []
    if request.user_profile and isinstance(request.user_profile, dict):
        profile_skills = request.user_profile.get("skills")
        if isinstance(profile_skills, list):
            skills = list(profile_skills)
    if not skills and isinstance(request.candidate_skills, list):
        skills = list(request.candidate_skills)
    return dedupe_skill_list(skills)


async def _attach_ai_reasoning(
    *,
    user_profile: Optional[Dict[str, Any]],
    candidate_skills: List[str],
    location: Optional[str],
    job: GapAnalysisJobInput,
    deterministic_result: Dict[str, Any],
    gemini_svc: GeminiService,
) -> AiReasoning:
    """Call Gemini gap reasoning for a single job; always return a valid AiReasoning.

    On any failure (missing key, SDK errors, timeout, malformed JSON), the function
    falls back to a deterministic structured response — never raises.
    """
    fallback_profile = {
        "skills": candidate_skills,
        "location": location,
    }
    if isinstance(user_profile, dict):
        # Merge: user_profile values take precedence over fallback defaults
        merged_profile = {
            "education": user_profile.get("education"),
            "skills": list(user_profile.get("skills") or candidate_skills),
            "location": user_profile.get("location") or location,
            "interests": list(user_profile.get("interests") or []),
        }
    else:
        merged_profile = {
            "education": None,
            "skills": list(candidate_skills),
            "location": location,
            "interests": [],
        }

    job_dict = {
        "job_id": job.job_id,
        "title": job.job_title,
        "company": None,
        "required_skills": list(job.required_skills),
        "description": "",
    }
    matching_dict = {
        "match_score": deterministic_result.get("match_score"),
        "matched_skills": list(deterministic_result.get("matched_skills") or []),
        "missing_skills": list(deterministic_result.get("missing_skills") or []),
    }
    gap_dict = {
        "matched_skills": list(deterministic_result.get("matched_skills") or []),
        "missing_skills": list(deterministic_result.get("missing_skills") or []),
        "gap_priority": deterministic_result.get("gap_priority"),
    }

    ai_dict, _ok = await gemini_svc.analyze_gap_reasoning(
        user_profile=merged_profile,
        job=job_dict,
        matching=matching_dict,
        gap_analysis=gap_dict,
    )
    # ai_dict is always a valid dict per contract of analyze_gap_reasoning
    return AiReasoning(
        summary=str(ai_dict.get("summary") or ""),
        strengths=list(ai_dict.get("strengths") or []),
        priority_gaps=list(ai_dict.get("priority_gaps") or []),
        learning_focus=list(ai_dict.get("learning_focus") or []),
        source=str(ai_dict.get("source") or "deterministic_fallback"),
        note=ai_dict.get("note"),
    )


# ---------------------------------------------------------------------------
# Step 5 — Primary deterministic Gap Analysis endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GapAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Deterministic skill-gap analysis for one or more matched jobs",
)
@router.post(
    "/analyze-jobs",
    response_model=GapAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Alias endpoint for multi-job deterministic gap analysis",
)
async def run_gap_analysis(
    request: GapAnalysisRequest = Body(
        ...,
        description="User profile (or candidate_skills) + list of matched jobs to analyze",
    ),
) -> GapAnalysisResponse:
    """
    Step 5 deterministic Gap Analysis + Step 6 Gemini (AI) reasoning.

    For each matched job:
      - Validates required fields (job_id, job_title, required_skills)
      - Deduplicates user skills and required skills via project normalizer
      - Computes matched/missing skills (validates pre-computed Skill Matching
        results if provided, otherwise recomputes)
      - Assigns gap priority: None/Low/Medium/High/Critical
      - Generates a plain-language gap_explanation string
      - Calls Gemini reasoning (with deterministic fallback on any failure)
        and attaches structured ai_reasoning to each analysis.

    Returns: ordered list of per-job analyses + aggregate metadata.
    """
    user_skills = _extract_user_skills(request)
    user_profile_dict = request.user_profile if isinstance(request.user_profile, dict) else None
    location_from_profile = (
        user_profile_dict.get("location") if isinstance(user_profile_dict, dict) else None
    )

    # Validate jobs array before processing so errors are fast and clear
    if not request.jobs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one job must be provided in the 'jobs' list.",
        )

    gemini_svc = _get_gemini_service()
    use_ai = True

    analyses: List[SingleJobGapAnalysis] = []
    for idx, job in enumerate(request.jobs):
        if not isinstance(job, GapAnalysisJobInput):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Job at index {idx} has invalid format.",
            )
        if not job.job_id or not str(job.job_id).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Job at index {idx} is missing required 'job_id'.",
            )
        if not job.job_title or not str(job.job_title).strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Job at index {idx} is missing required 'job_title'.",
            )
        if not isinstance(job.required_skills, list):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Job at index {idx}: 'required_skills' must be a list of strings.",
            )

        result = analyze_single_job_gap(
            user_skills=user_skills,
            job_id=str(job.job_id).strip(),
            job_title=str(job.job_title).strip(),
            required_skills=list(job.required_skills),
            precomputed_matched=job.matched_skills,
            precomputed_missing=job.missing_skills,
            match_score=job.match_score,
        )

        ai_reasoning: Optional[AiReasoning] = None
        if use_ai:
            ai_reasoning = await _attach_ai_reasoning(
                user_profile=user_profile_dict,
                candidate_skills=user_skills,
                location=location_from_profile,
                job=job,
                deterministic_result=result,
                gemini_svc=gemini_svc,
            )

        result_with_ai = dict(result)
        result_with_ai["ai_reasoning"] = ai_reasoning
        analyses.append(SingleJobGapAnalysis(**result_with_ai))

    metadata = compute_metadata([a.model_dump() for a in analyses])
    metadata["ai_enabled"] = bool(use_ai)
    metadata["gemini_configured"] = bool(gemini_svc.is_configured)

    return GapAnalysisResponse(
        status="success",
        candidate_skills=user_skills,
        analyses=analyses,
        metadata=metadata,
    )


@router.post(
    "/single",
    response_model=SingleJobGapAnalysis,
    status_code=status.HTTP_200_OK,
    summary="Deterministic skill-gap analysis for a single job",
)
async def run_single_job_gap_analysis(
    job: GapAnalysisJobInput,
    candidate_skills: Optional[List[str]] = Body(default=None, embed=True),
) -> SingleJobGapAnalysis:
    """Run gap analysis for exactly one matched job + Gemini AI reasoning.

    For test-injection of a custom GeminiService, call the module-level
    _set_gemini_service_override(svc) before this endpoint.
    """
    skills = dedupe_skill_list(candidate_skills or [])
    result = analyze_single_job_gap(
        user_skills=skills,
        job_id=str(job.job_id).strip(),
        job_title=str(job.job_title).strip(),
        required_skills=list(job.required_skills),
        precomputed_matched=job.matched_skills,
        precomputed_missing=job.missing_skills,
        match_score=job.match_score,
    )
    gemini_svc = _get_gemini_service()
    ai = await _attach_ai_reasoning(
        user_profile=None,
        candidate_skills=skills,
        location=None,
        job=job,
        deterministic_result=result,
        gemini_svc=gemini_svc,
    )
    result_with_ai = dict(result)
    result_with_ai["ai_reasoning"] = ai
    return SingleJobGapAnalysis(**result_with_ai)


# ---------------------------------------------------------------------------
# Legacy skeleton endpoint preserved for backward compatibility
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=LegacyGapAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Legacy endpoint: analyze skill gaps against target role (skeleton, now deterministic)",
)
async def analyze_skill_gaps(request: LegacyGapAnalysisRequest) -> LegacyGapAnalysisResponse:
    """
    Legacy endpoint preserved for backward compatibility with earlier skeleton code.
    Now uses the deterministic Step 5 analyzer service when explicit required_skills
    are provided. Otherwise returns structured skeleton response with 0 gaps.
    """
    possessed = dedupe_skill_list(request.candidate_skills or [])
    required = dedupe_skill_list(request.required_skills or [])

    # Use analyzer service when we have explicit required_skills to compare against
    if required:
        gap_items = analyzer_service.identify_missing_skills(possessed, required)
        matched_count = max(0, len(required) - len(gap_items))
        readiness = analyzer_service.calculate_readiness_score(len(required), matched_count)
        missing_structured: List[SkillGapItem] = []
        for g in gap_items:
            missing_structured.append(SkillGapItem(
                skill_name=g["skill_name"],
                importance_level=g.get("importance_level", "High"),
                category=g.get("category", "Technical"),
                suggested_action=g.get("suggested_action", ""),
            ))
        summary_parts = []
        if matched_count == len(required) and len(required) > 0:
            summary_parts.append(
                f"All {len(required)} required skills for the {request.target_role} role are present."
            )
        elif missing_structured:
            names = [m.skill_name for m in missing_structured]
            summary_parts.append(
                f"To qualify as a {request.target_role}, focus on acquiring: "
                + ", ".join(names) + "."
            )
        recommendations_summary = " ".join(summary_parts)
        return LegacyGapAnalysisResponse(
            status="success",
            target_role=request.target_role,
            readiness_score=readiness,
            possessed_skills=possessed,
            missing_skills=missing_structured,
            recommendations_summary=recommendations_summary,
            metadata={"source": "deterministic-step5-analyzer"},
        )

    # Skeleton fallback when no explicit required_skills were provided
    return LegacyGapAnalysisResponse(
        status="success",
        target_role=request.target_role,
        readiness_score=0.0,
        possessed_skills=possessed,
        missing_skills=[],
        recommendations_summary="",
        metadata={
            "info": (
                "Gap analysis agent pipeline skeleton ready. Provide explicit "
                "required_skills for deterministic analysis output."
            ),
        },
    )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for Gap Analysis Agent",
)
async def health_check():
    """Health status check for the gap analysis agent module."""
    return {
        "status": "healthy",
        "agent": "gap-analysis-agent",
        "mode": "deterministic + Gemini (Step 6). Falls back to deterministic on Gemini errors.",
        "gemini_configured": bool(_default_gemini_service.is_configured),
        "gemini_model": _default_gemini_service.model_name,
    }
