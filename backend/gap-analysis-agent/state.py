from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class GapAnalysisState(TypedDict):
    """
    LangGraph state schema for Gap Analysis Agent workflow.
    Tracks state across nodes: extract requirements -> compare skills -> evaluate via Gemini -> format roadmap.
    """
    candidate_skills: List[str]
    target_role: str
    target_job_description: Optional[str]
    extracted_required_skills: List[str]
    identified_gaps: List[Dict[str, Any]]
    readiness_score: float
    llm_recommendations: Optional[str]
    error: Optional[str]
