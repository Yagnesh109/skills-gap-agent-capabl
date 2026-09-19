import os
import sys
from pathlib import Path

# Disable TensorFlow in transformers to avoid global Protobuf gencode/runtime conflicts
os.environ["USE_TF"] = "0"
os.environ["USE_TORCH"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import importlib
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, File, HTTPException, UploadFile, status, Body
from fastapi.middleware.cors import CORSMiddleware
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

# Dynamically import routers from modular agent directories
skill_match_module = importlib.import_module("skill-match-agent.router")
skill_match_router = skill_match_module.router

gap_analysis_module = importlib.import_module("gap-analysis-agent.router")
gap_analysis_router = gap_analysis_module.router


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TextParseRequest(BaseModel):
    text: str


class LangGraphUserProfile(BaseModel):
    """Schema accepted by the end-to-end LangGraph orchestration endpoint."""
    education: Optional[str] = Field(default=None, description="Candidate education / qualification")
    skills: List[str] = Field(..., description="Candidate's current skills", min_length=0)
    location: Optional[str] = Field(default=None, description="Preferred job location")
    interests: Optional[List[str]] = Field(default_factory=list, description="Candidate's interest domains")
    target_role: Optional[str] = Field(default=None, description="Target role / keywords to search for")
    user_id: Optional[str] = Field(default="user_001", description="Optional user identifier")
    name: Optional[str] = Field(default="Candidate", description="Optional candidate name")


def _import_orchestration():
    return importlib.import_module("orchestration")


# Initialize FastAPI application
app = FastAPI(
    title="Skill Match & Gap Analysis Multi-Agent API",
    description="Multi-agent platform for Profile Parsing, Skill Matching, and Gap Analysis using LangGraph, Gemini 3.6, and Sentence Transformers.",
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
    """Execute the complete 4-node LangGraph workflow."""
    try:
        orch = _import_orchestration()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LangGraph orchestration module could not be loaded.",
        )

    profile_dict: Dict[str, Any] = profile.model_dump(mode="python")

    try:
        final_state: Dict[str, Any] = orch.run_skill_gap_workflow(profile_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Skill-gap workflow execution failed unexpectedly.",
        )

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
