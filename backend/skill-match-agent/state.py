from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class SkillMatchState(TypedDict):
    """
    LangGraph state schema for Skill Matching Agent workflow.
    Tracks state across graph nodes: input skills -> fetch jobs -> semantic score -> format results.
    """
    candidate_skills: List[str]
    job_title: str
    location: Optional[str]
    top_k: int
    raw_jobs: List[Dict[str, Any]]
    embeddings: Dict[str, Any]
    matched_results: List[Dict[str, Any]]
    error: Optional[str]
