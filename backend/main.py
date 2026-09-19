import os
import sys
import asyncio
from pathlib import Path

# Disable TensorFlow in transformers to avoid global Protobuf gencode/runtime conflicts
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import importlib
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, UploadFile, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Add backend directory to sys.path to allow imports of hyphenated module folders
# and to make "orchestration" importable regardless of where uvicorn is launched.
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
_PROJECT_ROOT = BACKEND_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Load settings
try:
    from backend.config import settings
except ImportError:  # pragma: no cover
    from config import settings

# Import Profile Parsing services
from profile_parsing.document_extractor import IMAGE_EXTENSIONS, extract_text_from_file
from profile_parsing.gemini_client import parse_resume_image_with_gemini, parse_resume_with_gemini
from profile_parsing.schemas import UserProfile

# Dynamically import routers from modular agent directories
skill_match_module = importlib.import_module("skill-match-agent.router")
skill_match_router = skill_match_module.router

gap_analysis_module = importlib.import_module("gap-analysis-agent.router")
gap_analysis_router = gap_analysis_module.router

training_agent_module = importlib.import_module("training-agent.agent")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TextParseRequest(BaseModel):
    text: str


class TrainingRecommendRequest(BaseModel):
    missing_skills: List[str] = Field(default_factory=list, description="List of missing skills to query training recommendations for")
    free_only: bool = Field(default=False, description="When true, select only free courses")


class SkillCombinationOptimizerRequest(BaseModel):
    """Constraints for the deterministic skill-combination optimizer."""

    user_profile: Dict[str, Any] = Field(default_factory=dict)
    max_weeks: float = Field(..., ge=0, description="Maximum learning time in weeks")
    budget_inr: float = Field(..., ge=0, description="Maximum learning budget in INR")


class LangGraphUserProfile(UserProfile):
    """Canonical profile accepted by the end-to-end LangGraph endpoint."""
    skills: List[str] = Field(..., description="Candidate's current skills", min_length=0)
    user_id: Optional[str] = Field(default="user_001", description="Optional user identifier")
    free_only: bool = Field(default=False, description="When true, calculate learning plans using only free courses")


def _import_orchestration():
    return importlib.import_module("orchestration")


def _build_career_intelligence(final_state: Dict[str, Any]) -> Dict[str, Any]:
    """Expose chart projections from the existing workflow results."""
    chart_module = importlib.import_module("orchestration.chart_data")
    return chart_module.build_career_intelligence_charts(
        gap_analyses=final_state.get("gap_analyses", []),
        opportunity_analysis=final_state.get("opportunity_analysis", {}),
    )


# Initialize FastAPI application
app = FastAPI(
    title="Skill Match & Gap Analysis Multi-Agent API",
    description="Multi-agent platform for profile parsing, matching, gap analysis, opportunity simulation, RAG, and training using LangGraph and Gemini.",
    version="0.1.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register agent routers
app.include_router(skill_match_router)
app.include_router(gap_analysis_router)


# ---------------------------------------------------------------------------
# 1. Profile Parsing Agent Endpoints
# ---------------------------------------------------------------------------

VALID_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".txt",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/profile/parse")
async def parse_profile(file: UploadFile = File(...)):
    """Parse a PDF, DOC, DOCX, TXT, or Image resume and return structured profile data."""
    if not file:
        raise HTTPException(status_code=400, detail="No resume uploaded.")

    filename = file.filename or ""
    if not filename.lower().endswith(VALID_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF, DOC, DOCX, TXT, or Image file.",
        )

    try:
        pdf_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file.") from exc

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No resume uploaded.")

    ext = "." + filename.lower().split(".")[-1] if "." in filename else ""
    if ext in IMAGE_EXTENSIONS:
        try:
            parsed_profile = parse_resume_image_with_gemini(pdf_bytes, filename)
        except ValueError as exc:
            raise HTTPException(
                status_code=400 if "empty" in str(exc).lower() or "invalid" in str(exc).lower() else 502,
                detail=str(exc)
            ) from exc
    else:
        try:
            resume_text = extract_text_from_file(pdf_bytes, filename)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            parsed_profile = parse_resume_with_gemini(resume_text)
        except ValueError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"success": True, "profile": parsed_profile}


@app.post("/api/profile/parse-text")
async def parse_profile_text(request: TextParseRequest):
    """Parse raw text resume input and return structured profile data."""
    raw_text = (request.text or "").strip()
    if not raw_text:
        raise HTTPException(status_code=400, detail="Resume text cannot be empty.")

    try:
        parsed_profile = parse_resume_with_gemini(raw_text)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"success": True, "profile": parsed_profile}


@app.post("/api/training/recommend")
async def recommend_training_courses(request: TrainingRecommendRequest):
    """Recommend high-ROI courses matching missing skills using Training Recommendation Agent."""
    missing_skills = request.missing_skills or []
    try:
        recommendations = training_agent_module.recommend_training(
            missing_skills,
            free_only=request.free_only,
        )
        return {"success": True, **recommendations}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training recommendation failed: {str(exc)}"
        ) from exc


@app.post("/api/skill-combination-optimizer")
async def optimize_skill_combinations(request: SkillCombinationOptimizerRequest):
    """Compare data-backed skill combinations under time and budget limits."""
    try:
        skill_services = importlib.import_module("skill-match-agent.services.job_source_service")
        matching_module = importlib.import_module("skill-match-agent.services.matching_service")
        training_module = importlib.import_module("training-agent.agent")
        time_module = importlib.import_module("training-agent.time_to_ready")
        optimizer_module = importlib.import_module("orchestration.skill_combination_optimizer")

        profile = dict(request.user_profile or {})
        jobs, job_source = await skill_services.job_source_service.get_jobs(
            keywords=profile.get("target_role") or "",
            location=profile.get("location") or "",
            candidate_skills=profile.get("skills") or [],
            interests=profile.get("interests") or [],
        )
        courses = training_module.load_courses()
        rag_sources: List[Dict[str, Any]] = []
        try:
            rag_module = importlib.import_module("orchestration.rag")
            rag_result = rag_module.rag_retriever.retrieve(
                user_profile=profile,
                jobs=[job.model_dump(mode="python") if hasattr(job, "model_dump") else dict(job) for job in jobs],
                courses=courses,
                missing_skills=[],
            )
            rag_sources = list(rag_result.get("retrieved_sources") or [])
        except Exception:
            # RAG is an evidence enhancement, not a dependency of the optimizer.
            rag_sources = []

        result = optimizer_module.optimize_skill_combinations(
            user_profile=profile,
            jobs=jobs,
            courses=courses,
            matching_service=matching_module.matching_service,
            calculate_time_to_ready=time_module.calculate_time_to_ready,
            max_weeks=request.max_weeks,
            budget_inr=request.budget_inr,
            rag_sources=rag_sources,
        )
        result["job_source"] = job_source
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Skill combination optimization failed: {str(exc)}",
        ) from exc


# ---------------------------------------------------------------------------
# 2. Skill Gap Orchestration Endpoint (LangGraph)
# ---------------------------------------------------------------------------

@app.post(
    "/api/skill-gap/analyze",
    status_code=status.HTTP_200_OK,
    summary="Full end-to-end Skill-Gap workflow via LangGraph orchestration",
)
async def run_skill_gap_graph(
    profile: LangGraphUserProfile = Body(
        ...,
        description="Structured user profile to run through Job Search -> Matching -> Gap Analysis -> Gemini reasoning",
        examples=[{
            "education": "B.Tech Computer Science",
            "skills": ["Python", "SQL", "React"],
            "location": "Pune",
            "interests": ["AI", "Web Development"],
            "target_role": "Python Developer",
        }],
    ),
) -> Dict[str, Any]:
    """Execute the complete lifecycle LangGraph workflow."""
    try:
        orch = _import_orchestration()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangGraph orchestration module could not be loaded.",
        )

    profile_dict: Dict[str, Any] = profile.model_dump(mode="python")

    try:
        final_state: Dict[str, Any] = orch.run_skill_gap_workflow(
            profile_dict,
            free_only=profile.free_only,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Skill-gap workflow execution failed unexpectedly.",
        )

    ai_list: List[Dict[str, Any]] = []
    for entry in final_state.get("ai_reasoning") or []:
        cleaned = {k: v for k, v in entry.items() if not k.startswith("_")}
        ai_list.append(cleaned)

    final_profile = final_state.get("user_profile", profile)
    if hasattr(final_profile, "model_dump"):
        final_profile = final_profile.model_dump(mode="json")

    return {
        "user_profile": final_profile,
        "profile": final_profile,
        "jobs": final_state.get("jobs", []),
        "job_source": final_state.get("job_source", "unknown"),
        "matching_results": final_state.get("matching_results", []),
        "matched_jobs": final_state.get("matched_jobs", final_state.get("matching_results", [])),
        "gap_analyses": final_state.get("gap_analyses", []),
        "skill_gaps": final_state.get("skill_gaps", final_state.get("gap_analyses", [])),
        "current_jobs": final_state.get("current_jobs", 0),
        "opportunity_analysis": final_state.get(
            "opportunity_analysis",
            {"current_jobs": 0, "opportunities": [], "combinations": []},
        ),
        "career_intelligence": _build_career_intelligence(final_state),
        "training_recommendations": final_state.get("training_recommendations", []),
        "time_to_ready": final_state.get("time_to_ready", {}),
        "retrieved_jobs": final_state.get("retrieved_jobs", []),
        "retrieved_courses": final_state.get("retrieved_courses", []),
        "retrieved_sources": final_state.get("retrieved_sources", []),
        "rag_available": final_state.get("rag_available", False),
        "rag_query": final_state.get("rag_query", ""),
        "rag_index": final_state.get("rag_index", {}),
        "free_only": final_state.get("free_only", profile.free_only),
        "ai_reasoning": ai_list,
        "errors": final_state.get("errors", []),
        "warnings": final_state.get("warnings", []),
        "status": final_state.get("status", "completed"),
        "current_node": final_state.get("current_node", "report"),
        "failed_node": final_state.get("failed_node", ""),
        "node_status": final_state.get("node_status", {}),
        "report": final_state.get("report", {}),
        "tool_calls": final_state.get("tool_calls", []),
        "tool_results": final_state.get("tool_results", []),
        "tool_errors": final_state.get("tool_errors", []),
        "tool_trace": final_state.get("tool_trace", []),
    }


def _serialize_skill_gap_result(final_state: Dict[str, Any], default_profile: LangGraphUserProfile) -> Dict[str, Any]:
    """Keep synchronous and streaming workflow responses identical."""
    ai_list = [
        {k: v for k, v in entry.items() if not k.startswith("_")}
        for entry in (final_state.get("ai_reasoning") or [])
    ]
    final_profile = final_state.get("user_profile", default_profile)
    if hasattr(final_profile, "model_dump"):
        final_profile = final_profile.model_dump(mode="json")
    return {
        "user_profile": final_profile,
        "profile": final_profile,
        "jobs": final_state.get("jobs", []),
        "job_source": final_state.get("job_source", "unknown"),
        "matching_results": final_state.get("matching_results", []),
        "matched_jobs": final_state.get("matched_jobs", final_state.get("matching_results", [])),
        "gap_analyses": final_state.get("gap_analyses", []),
        "skill_gaps": final_state.get("skill_gaps", final_state.get("gap_analyses", [])),
        "current_jobs": final_state.get("current_jobs", 0),
        "opportunity_analysis": final_state.get("opportunity_analysis", {"current_jobs": 0, "opportunities": [], "combinations": []}),
        "career_intelligence": _build_career_intelligence(final_state),
        "training_recommendations": final_state.get("training_recommendations", []),
        "time_to_ready": final_state.get("time_to_ready", {}),
        "retrieved_jobs": final_state.get("retrieved_jobs", []),
        "retrieved_courses": final_state.get("retrieved_courses", []),
        "retrieved_sources": final_state.get("retrieved_sources", []),
        "rag_available": final_state.get("rag_available", False),
        "rag_query": final_state.get("rag_query", ""),
        "rag_index": final_state.get("rag_index", {}),
        "free_only": final_state.get("free_only", default_profile.free_only),
        "ai_reasoning": ai_list,
        "errors": final_state.get("errors", []),
        "warnings": final_state.get("warnings", []),
        "status": final_state.get("status", "completed"),
        "current_node": final_state.get("current_node", "report"),
        "failed_node": final_state.get("failed_node", ""),
        "node_status": final_state.get("node_status", {}),
        "report": final_state.get("report", {}),
        "tool_calls": final_state.get("tool_calls", []),
        "tool_results": final_state.get("tool_results", []),
        "tool_errors": final_state.get("tool_errors", []),
        "tool_trace": final_state.get("tool_trace", []),
        "run_id": final_state.get("run_id", ""),
    }


@app.post("/api/skill-gap/analyze/run", status_code=status.HTTP_202_ACCEPTED)
async def start_skill_gap_run(profile: LangGraphUserProfile = Body(...)) -> Dict[str, str]:
    """Start a workflow and return a run ID for live progress streaming."""
    from progress_events import progress_manager

    run_id = progress_manager.create_run()
    profile_dict = profile.model_dump(mode="python")

    async def execute() -> None:
        try:
            orch = _import_orchestration()
            final_state = await asyncio.to_thread(
                orch.run_skill_gap_workflow,
                profile_dict,
                profile.free_only,
                run_id,
            )
            progress_manager.complete(run_id, _serialize_skill_gap_result(final_state, profile))
        except Exception:
            progress_manager.fail(run_id, "Skill-gap workflow execution failed unexpectedly.")

    asyncio.create_task(execute())
    return {"run_id": run_id}


@app.get("/api/agent/progress/{run_id}")
async def stream_agent_progress(run_id: str) -> StreamingResponse:
    from progress_events import format_sse, progress_manager

    if not progress_manager.has_run(run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent run.")

    async def event_stream():
        async for event in progress_manager.subscribe(run_id):
            yield format_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/api/agent/runs/{run_id}")
async def get_agent_run(run_id: str) -> Dict[str, Any]:
    from progress_events import progress_manager

    if not progress_manager.has_run(run_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent run.")
    result = progress_manager.result(run_id)
    if result is None:
        return {"status": "running", "run_id": run_id}
    return result


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint verifying API service status."""
    return {
        "message": "Skill Match & Gap Analysis Multi-Agent API is running",
        "active_modules": [
            "profile-parsing-agent",
            "skill-match-agent",
            "gap-analysis-agent",
            "orchestration (LangGraph)",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=getattr(settings, "HOST", "0.0.0.0"),
        port=getattr(settings, "PORT", 8000),
        reload=getattr(settings, "DEBUG", True)
    )
