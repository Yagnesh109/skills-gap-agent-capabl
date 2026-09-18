import sys
from pathlib import Path
import importlib
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, status, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Add backend directory to sys.path to allow imports of hyphenated module folders
# and to make "orchestration" importable regardless of where uvicorn is launched.
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
# Also add the project-root parent so "from backend.config import settings" works
# when launching the app from inside backend/ via `uvicorn main:app --reload`.
_PROJECT_ROOT = BACKEND_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load settings — resilient to whether the app is imported as `backend.main`
# (test / top-level invocation) or as `main` (uvicorn from inside backend/).
try:
    from backend.config import settings
except ImportError:  # pragma: no cover - depends on launch CWD
    from config import settings

# Dynamically import routers from modular agent directories
skill_match_module = importlib.import_module("skill-match-agent.router")
skill_match_router = skill_match_module.router

gap_analysis_module = importlib.import_module("gap-analysis-agent.router")
gap_analysis_router = gap_analysis_module.router


# ---------------------------------------------------------------------------
# Step 7 — LangGraph Orchestration endpoint schema + wiring
# ---------------------------------------------------------------------------

class LangGraphUserProfile(BaseModel):
    """Schema accepted by the end-to-end LangGraph orchestration endpoint.

    Mirrors the UserProfile contract from skill-match-agent without forcing
    a tight import coupling; validation here ensures that required fields are
    present and correctly typed before the graph is invoked.
    """
    education: Optional[str] = Field(default=None, description="Candidate education / qualification")
    skills: List[str] = Field(..., description="Candidate's current skills — at minimum an empty list must be provided", min_length=0)
    location: Optional[str] = Field(default=None, description="Preferred job location")
    interests: Optional[List[str]] = Field(default_factory=list, description="Candidate's interest domains")
    target_role: Optional[str] = Field(default=None, description="Target role / keywords to search for")
    user_id: Optional[str] = Field(default="user_001", description="Optional user identifier")
    name: Optional[str] = Field(default="Candidate", description="Optional candidate name")


def _import_orchestration():
    """Lazily import the LangGraph orchestration module so FastAPI startup
    doesn't fail if LangGraph is somehow missing (though requirements.txt pins it).
    """
    return importlib.import_module("orchestration")


# Initialize FastAPI application
app = FastAPI(
    title="Skill Match & Gap Analysis Multi-Agent API",
    description="Multi-agent platform for Job Skill Matching and Gap Analysis using LangGraph, Gemini, and Sentence Transformers.",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register agent routers
app.include_router(skill_match_router)
app.include_router(gap_analysis_router)


@app.post(
    "/api/skill-gap/analyze",
    status_code=status.HTTP_200_OK,
    summary="Step 7 — Full end-to-end Skill-Gap workflow via LangGraph orchestration",
)
async def run_skill_gap_graph(
    profile: LangGraphUserProfile = Body(
        ...,
        description="Structured user profile to run through Job Search → Matching → Gap Analysis → Gemini reasoning",
        examples=[{
            "education": "B.Tech Computer Science",
            "skills": ["Python", "SQL", "React"],
            "location": "Pune",
            "interests": ["AI", "Web Development"],
            "target_role": "Python Developer",
        }],
    ),
) -> Dict[str, Any]:
    """Execute the complete 4-node LangGraph workflow.

    Flow:
      1. job_search_node        → existing JobSourceService (Jooble primary, demo fallback)
      2. skill_matching_node    → existing SkillMatchingService (deterministic 70/30 score)
      3. gap_analysis_node      → existing GapAnalysisService (deterministic missing skills)
      4. gemini_reasoning_node  → existing GeminiService + deterministic fallback

    Existing endpoint contracts are **preserved**: this endpoint simply exposes
    the orchestrated workflow as a new convenience API.
    """
    try:
        orch = _import_orchestration()
    except Exception as exc:  # pragma: no cover - deployment safety net
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangGraph orchestration module could not be loaded.",
        )

    profile_dict: Dict[str, Any] = profile.model_dump(mode="python")

    try:
        final_state: Dict[str, Any] = orch.run_skill_gap_workflow(profile_dict)
    except Exception as exc:
        # Never leak stack traces or internal errors to the client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Skill-gap workflow execution failed unexpectedly.",
        )

    # Strip any internal-only sentinel keys before returning to the client
    ai_list: List[Dict[str, Any]] = []
    for entry in final_state.get("ai_reasoning") or []:
        cleaned = {k: v for k, v in entry.items() if not k.startswith("_")}
        ai_list.append(cleaned)

    return {
        "user_profile": final_state.get("user_profile", profile_dict),
        "jobs": final_state.get("jobs", []),
        "job_source": final_state.get("job_source", "unknown"),
        "matching_results": final_state.get("matching_results", []),
        "gap_analyses": final_state.get("gap_analyses", []),
        "ai_reasoning": ai_list,
        "errors": final_state.get("errors", []),
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint verifying API service status."""
    return {
        "message": "Skill Match & Gap Analysis Multi-Agent API is running",
        "active_modules": [
            "skill-match-agent",
            "gap-analysis-agent",
            "orchestration (Step 7 — LangGraph)",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
