from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator

try:
    from profile_parsing.schemas import UserProfile
except (ImportError, ValueError):
    from backend.profile_parsing.schemas import UserProfile


class JobPosting(BaseModel):
    """Schema representing a job vacancy posting."""
    job_id: str = Field(..., description="Unique job identifier")
    title: str = Field(..., description="Job title / role")
    company: str = Field(..., description="Company name offering the role")
    location: str = Field(..., description="Job location")
    required_skills: List[str] = Field(
        ...,
        description="List of essential skills required for the job"
    )
    description: str = Field(
        default="",
        description="Detailed job role description"
    )
    job_url: str = Field(
        default="",
        description="Link to the original job posting"
    )
    source: Optional[str] = Field(
        default="demo",
        description="Job origin source: 'jooble' or 'demo'"
    )


class SkillMatchRequest(BaseModel):
    """Input payload for skill matching request (supports both direct and user_profile format)."""
    candidate_skills: Optional[List[str]] = Field(
        default=None,
        description="List of skills parsed from candidate's profile"
    )
    job_title: Optional[str] = Field(
        default=None,
        description="Target job title or keywords to match against"
    )
    location: Optional[str] = Field(
        default="",
        description="Target job location"
    )
    top_k: int = Field(
        default=10,
        description="Number of top matching jobs to return",
        ge=1,
        le=100
    )
    user_profile: Optional[UserProfile] = Field(
        default=None,
        description="Optional full user profile object"
    )

    @model_validator(mode="after")
    def validate_and_sync_skills(self):
        """Ensure skills are properly populated from either user_profile or candidate_skills."""
        if self.user_profile:
            if not self.candidate_skills:
                self.candidate_skills = self.user_profile.skills
            if not self.job_title and self.user_profile.target_role:
                self.job_title = self.user_profile.target_role
            if not self.location and self.user_profile.location:
                self.location = self.user_profile.location

        if self.candidate_skills is None:
            self.candidate_skills = []
        if self.job_title is None:
            self.job_title = ""
        return self


class JobMatchResult(BaseModel):
    """Individual job match result schema matching Step 2 contract."""
    job_id: str
    title: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    snippet: Optional[str] = None
    url: Optional[str] = None
    match_score: float = Field(
        ...,
        description="Combined match score between candidate skills and job requirements (0.0 - 100.0)"
    )
    explicit_score: Optional[float] = Field(
        default=0.0,
        description="Explicit skill overlap percentage score (0.0 - 100.0)"
    )
    semantic_score: Optional[float] = Field(
        default=0.0,
        description="Semantic similarity percentage score (0.0 - 100.0)"
    )
    matched_skills: List[str] = Field(default_factory=list)
    unmatched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    semantic_matched_skills: List[str] = Field(
        default_factory=list,
        description="Required skills matched only through accepted semantic similarity",
    )
    source: Optional[str] = Field(
        default="demo",
        description="Origin source of matched job: 'jooble' or 'demo'"
    )
    location_compatibility: str = Field(
        default="unknown",
        description="Deterministic candidate/job location classification"
    )

    @model_validator(mode="after")
    def synchronize_aliases(self):
        """Synchronize job_title with title, and missing_skills with unmatched_skills."""
        if not self.job_title and self.title:
            self.job_title = self.title
        elif not self.title and self.job_title:
            self.title = self.job_title

        if not self.missing_skills and self.unmatched_skills:
            self.missing_skills = list(self.unmatched_skills)
        elif not self.unmatched_skills and self.missing_skills:
            self.unmatched_skills = list(self.missing_skills)
        return self


class SkillMatchResponse(BaseModel):
    """Output response payload for skill matching."""
    status: str
    target_job: str
    candidate_skills: List[str]
    matches: List[JobMatchResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
