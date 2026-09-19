from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class PriorityGap(BaseModel):
    """Structured per-missing-skill reasoning entry produced by Gemini."""
    skill: str = Field(
        ...,
        description="Name of a required skill that the user is missing (matches deterministic missing_skills entries).",
        example="Django"
    )
    reason: str = Field(
        default="",
        description="Practical explanation of why this skill matters for the specific role.",
        example="Django is required for Python web development in this role."
    )
    source_ids: List[str] = Field(
        default_factory=list,
        description="Retrieved RAG source IDs supporting this priority gap.",
        example=["JOB-003", "JOB-011"],
    )


class AiReasoning(BaseModel):
    """Structured AI-generated explanation and context (Gemini). Falls back to deterministic content when unavailable."""
    summary: str = Field(
        ...,
        description="Natural-language summary of the gap situation.",
        example="The candidate has a strong foundation in Python and SQL but needs Django and Git to qualify."
    )
    strengths: List[Any] = Field(
        default_factory=list,
        description="Subset of matched_skills the AI highlights as strengths, optionally with source_ids.",
        example=[{"skill": "Python", "source_ids": ["JOB-003"]}]
    )
    priority_gaps: List[PriorityGap] = Field(
        default_factory=list,
        description="Ordered list of priority gaps the AI recommends addressing first.",
    )
    learning_focus: List[Any] = Field(
        default_factory=list,
        description="Short practical learning goals ordered by priority, optionally with source_ids.",
        example=[{"topic": "Django fundamentals", "source_ids": ["CRS-103"]}]
    )
    source: str = Field(
        default="deterministic_fallback",
        description="'gemini' when produced by Gemini; 'deterministic_fallback' when AI is unavailable.",
    )
    note: Optional[str] = Field(
        default=None,
        description="Optional note, e.g. reason for fallback (never contains API keys or secrets).",
    )


class SingleJobGapAnalysis(BaseModel):
    """Per-job deterministic skill gap analysis report + optional Gemini AI reasoning.

    Matches Step 2 contract:
      job_id, job_title, user_skills, required_skills, missing_skills, gap_explanation
    plus ai_reasoning (Step 6).
    """
    job_id: str = Field(
        ...,
        description="Unique job identifier matching the JobPosting schema",
        example="JOB-001"
    )
    job_title: str = Field(
        ...,
        description="Job title / role name",
        example="Python Developer"
    )
    user_skills: List[str] = Field(
        ...,
        description="Skills reported by the candidate (deduplicated and normalized)",
        example=["Python", "SQL"]
    )
    required_skills: List[str] = Field(
        ...,
        description="Skills required for the role (deduplicated and normalized)",
        example=["Python", "Django", "SQL", "Git"]
    )
    matched_skills: List[str] = Field(
        default_factory=list,
        description="Skills the user already has that are required for the job",
        example=["Python", "SQL"]
    )
    missing_skills: List[str] = Field(
        ...,
        description="Skills required for the role that the user currently lacks",
        example=["Django", "Git"]
    )
    match_score: Optional[float] = Field(
        default=None,
        description="Overall Skill Matching score for this job (0.0 - 100.0), if provided",
        example=78.5,
        ge=0.0,
        le=100.0
    )
    gap_explanation: str = Field(
        ...,
        description="Deterministic plain-language summary of the skill gaps",
        example="The candidate already has Python and SQL, but Django and Git are required for this role and are currently missing."
    )
    gap_priority: str = Field(
        default="Medium",
        description="Overall gap priority: Critical, High, Medium, Low, or None"
    )
    ai_reasoning: Optional[AiReasoning] = Field(
        default=None,
        description="Gemini-generated structured reasoning/explanation. Always present when enabled; falls back to deterministic content if Gemini unavailable."
    )


class GapAnalysisJobInput(BaseModel):
    """Per-job input for the gap analysis request.

    Minimum required fields: job_id, job_title, required_skills.
    Supports optional Skill Matching result fields (matched_skills, missing_skills, match_score)
    but falls back to recomputing them deterministically when absent.
    """
    job_id: str = Field(
        ...,
        description="Unique job identifier",
        example="JOB-001"
    )
    job_title: str = Field(
        ...,
        description="Job title / role name",
        example="Python Developer"
    )
    required_skills: List[str] = Field(
        ...,
        description="Skills required for this job posting",
        example=["Python", "Django", "SQL", "Git"]
    )
    matched_skills: Optional[List[str]] = Field(
        default=None,
        description="Optional: pre-computed matched skills from the Skill Matching Agent"
    )
    missing_skills: Optional[List[str]] = Field(
        default=None,
        description="Optional: pre-computed missing skills from the Skill Matching Agent"
    )
    match_score: Optional[float] = Field(
        default=None,
        description="Optional: pre-computed match score (0.0 - 100.0)",
        ge=0.0,
        le=100.0
    )


class GapAnalysisRequest(BaseModel):
    """Input payload for the deterministic Gap Analysis Agent (Step 5).

    Accepts either:
      - A single UserProfile + list of matched Job inputs
      - Or explicit candidate_skills + list of matched Job inputs
    """
    candidate_skills: Optional[List[str]] = Field(
        default=None,
        description="Candidate skills list (alternatively provide user_profile.skills)",
        example=["Python", "SQL", "React"]
    )
    user_profile: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional UserProfile dictionary (skills will be extracted from 'skills' key)"
    )
    jobs: List[GapAnalysisJobInput] = Field(
        ...,
        description="One or more matched job postings to analyze for skill gaps",
        min_length=1
    )


class GapAnalysisResponse(BaseModel):
    """Output response payload for the deterministic Gap Analysis Agent."""
    status: str = Field(
        ...,
        description="Request status: 'success' or 'error'",
        example="success"
    )
    candidate_skills: List[str] = Field(
        default_factory=list,
        description="Deduplicated user skills used for analysis"
    )
    analyses: List[SingleJobGapAnalysis] = Field(
        default_factory=list,
        description="Per-job gap analysis results, ordered to match the input job list"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra diagnostic info (e.g. total_missing_skills, count_jobs_analyzed)"
    )


# ---------------------------------------------------------------------------
# Legacy schemas (kept for backward compatibility with prior skeleton code)
# ---------------------------------------------------------------------------


class LegacyGapAnalysisRequest(BaseModel):
    """Legacy input payload preserved for backward compatibility."""
    candidate_skills: List[str] = Field(
        ...,
        description="List of skills candidate currently possesses",
        example=["Python", "HTML", "CSS"]
    )
    target_role: str = Field(
        ...,
        description="Target job title or role name",
        example="Senior Fullstack Engineer"
    )
    target_job_description: Optional[str] = Field(
        default="",
        description="Full text or requirements snippet of the target job",
        example="Requires Python, React, PostgreSQL, Docker, and Kubernetes"
    )
    required_skills: Optional[List[str]] = Field(
        default_factory=list,
        description="Explicit required skills if already extracted"
    )


class SkillGapItem(BaseModel):
    """Legacy per-skill gap detail preserved for backward compatibility."""
    skill_name: str
    importance_level: str = Field(
        ...,
        description="Importance for the target role: High, Medium, or Low"
    )
    category: Optional[str] = Field(
        default="Technical",
        description="Skill category (e.g. Core, Tool, Soft Skill)"
    )
    suggested_action: Optional[str] = Field(
        default="",
        description="Recommended action to bridge the gap"
    )


class LegacyGapAnalysisResponse(BaseModel):
    """Legacy output response preserved for backward compatibility with skeleton."""
    status: str
    target_role: str
    readiness_score: float = Field(
        default=0.0,
        description="Readiness score from 0.0 to 100.0"
    )
    possessed_skills: List[str] = Field(default_factory=list)
    missing_skills: List[SkillGapItem] = Field(default_factory=list)
    recommendations_summary: str = Field(
        default="",
        description="LLM-generated roadmap and recommendations summary"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
