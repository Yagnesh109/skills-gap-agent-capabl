"""
Skill Gap Workflow Orchestration (Step 7 — LangGraph).

This module is an ORCHESTRATION layer only — it does NOT re-implement any
business logic from Steps 1–6. Instead, it wires the existing services
(JobSourceService, SkillMatchingService, GapAnalysisService, GeminiService)
into a single typed LangGraph StateGraph workflow.

Flow:

    START
      │
      ▼
  job_search_node   ── calls existing job_source_service.get_jobs()
      │               (internal Jooble or demo fallback)
      ▼
  skill_matching_node ── calls existing matching_service.rank_jobs()
      │
      ▼
  gap_analysis_node ── calls existing analyze_multiple_jobs()
      │
      ▼
  gemini_reasoning_node ── calls existing GeminiService.analyze_gap_reasoning()
      │                  (with internal deterministic fallback)
      ▼
     END

State uses a TypedDict with optional keys so each node only writes what it
produces. Graph construction uses the currently-installed LangGraph API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Any, Dict, List, Mapping, Optional, Tuple, Union

from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

try:
    from profile_parsing.schemas import UserProfile
except (ImportError, ValueError):
    from backend.profile_parsing.schemas import UserProfile

try:
    from .opportunity_analysis import analyze_opportunities
except (ImportError, ValueError):
    from opportunity_analysis import analyze_opportunities

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Imports — resilient path setup (test harnesses run from various CWDs)
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent.parent
for _p in (str(_BACKEND_DIR),
           str(_BACKEND_DIR / "skill-match-agent"),
           str(_BACKEND_DIR / "gap-analysis-agent")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _import_skill_services():
    """Load existing Step 3/4 services from skill-match-agent."""
    import importlib
    try:
        job_src_mod = importlib.import_module("services.job_source_service")
        match_mod = importlib.import_module("services.matching_service")
        return (
            job_src_mod.job_source_service,
            match_mod.matching_service,
        )
    except Exception:
        job_src_mod = importlib.import_module(
            "skill-match-agent.services.job_source_service"
        )
        match_mod = importlib.import_module(
            "skill-match-agent.services.matching_service"
        )
        return (
            job_src_mod.job_source_service,
            match_mod.matching_service,
        )


def _import_gap_services():
    """Load existing Step 5/6 services from gap-analysis-agent."""
    import importlib
    try:
        gap_mod = importlib.import_module("services.gap_analysis_service")
        gemini_mod = importlib.import_module("services.gemini_service")
        return (
            gap_mod.analyze_multiple_jobs,
            gap_mod.analyze_single_job_gap,
            gap_mod.dedupe_skill_list,
            gemini_mod.GeminiService,
            gemini_mod.gemini_service,
        )
    except Exception:
        gap_mod = importlib.import_module(
            "gap-analysis-agent.services.gap_analysis_service"
        )
        gemini_mod = importlib.import_module(
            "gap-analysis-agent.services.gemini_service"
        )
        return (
            gap_mod.analyze_multiple_jobs,
            gap_mod.analyze_single_job_gap,
            gap_mod.dedupe_skill_list,
            gemini_mod.GeminiService,
            gemini_mod.gemini_service,
        )


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class SkillGapState(TypedDict, total=False):
    """Typed workflow state for the end-to-end skill-gap pipeline.

    Keys are written incrementally by each node:
    - user_profile:  validated canonical UserProfile
      - jobs:          list[dict] of normalized job postings from JobSourceService
      - job_source:    "jooble" | "demo" — origin tag from job retrieval
      - user_skills:   deduped list[str] of user skills (derived from user_profile)
      - matching_results: list[dict] of ranked match results from SkillMatchingService
      - gap_analyses:  list[dict] of deterministic gap analyses (per job)
    - current_jobs:  count of jobs with a positive existing matching score
    - opportunity_analysis: deterministic individual and combination opportunities
    - training_recommendations: up to three course recommendations
    - time_to_ready: dict mapping job_id -> per-job time-to-ready result
      - ai_reasoning:  list[dict] of structured Gemini reasoning (one per job; fallback-safe)
      - errors:        list[{node, message}] of non-fatal informational errors
    - free_only: bool flag to filter courses to free-only
    """
    user_profile: UserProfile
    jobs: List[Dict[str, Any]]
    job_source: str
    user_skills: List[str]
    matching_results: List[Dict[str, Any]]
    gap_analyses: List[Dict[str, Any]]
    current_jobs: int
    opportunity_analysis: Dict[str, Any]
    training_recommendations: List[Dict[str, Any]]
    time_to_ready: Dict[str, Dict[str, Any]]
    retrieved_jobs: List[Dict[str, Any]]
    retrieved_courses: List[Dict[str, Any]]
    retrieved_sources: List[Dict[str, Any]]
    rag_available: bool
    rag_query: str
    rag_index: Dict[str, Any]
    profile: UserProfile
    matched_jobs: List[Dict[str, Any]]
    skill_gaps: List[Dict[str, Any]]
    ai_reasoning: List[Dict[str, Any]]
    errors: List[Dict[str, str]]
    free_only: bool
    profile_input: Dict[str, Any]
    profile_valid: bool
    profile_error: str
    status: str
    current_node: str
    failed_node: str
    warnings: List[Dict[str, str]]
    node_status: Dict[str, str]
    gemini_success: bool
    report: Dict[str, Any]
    messages: Annotated[List[Any], add_messages]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    tool_errors: List[Dict[str, Any]]
    tool_trace: List[Dict[str, Any]]
    tool_call_round: int
    tool_agent_available: bool
    run_id: str


# ---------------------------------------------------------------------------
# Service accessors (overridable for tests)
# ---------------------------------------------------------------------------


class _ServiceHolder:
    """Holds injectable service references. Tests swap these without importing twice."""

    def __init__(self) -> None:
        self._job_source_svc = None
        self._matching_svc = None
        self._analyze_multi_fn = None
        self._analyze_single_fn = None
        self._dedupe_skills_fn = None
        self._GeminiServiceCls = None
        self._default_gemini_svc = None
        self._recommend_training_fn = None

    def ensure_loaded(self) -> None:
        if self._job_source_svc is None:
            js, ms = _import_skill_services()
            self._job_source_svc = js
            self._matching_svc = ms
        if self._analyze_multi_fn is None:
            (am, as_, ds, gcls, gsvc) = _import_gap_services()
            self._analyze_multi_fn = am
            self._analyze_single_fn = as_
            self._dedupe_skills_fn = ds
            self._GeminiServiceCls = gcls
            self._default_gemini_svc = gsvc
        if self._recommend_training_fn is None:
            import importlib
            training_mod = importlib.import_module("training-agent.agent")
            self._recommend_training_fn = training_mod.recommend_training

    @property
    def job_source_service(self):
        self.ensure_loaded()
        return self._job_source_svc

    @property
    def matching_service(self):
        self.ensure_loaded()
        return self._matching_svc

    @property
    def analyze_multiple(self):
        self.ensure_loaded()
        return self._analyze_multi_fn

    @property
    def analyze_single(self):
        self.ensure_loaded()
        return self._analyze_single_fn

    @property
    def dedupe_skills(self):
        self.ensure_loaded()
        return self._dedupe_skills_fn

    @property
    def GeminiServiceCls(self):
        self.ensure_loaded()
        return self._GeminiServiceCls

    @property
    def default_gemini_service(self):
        self.ensure_loaded()
        return self._default_gemini_svc

    @property
    def recommend_training(self):
        self.ensure_loaded()
        return self._recommend_training_fn


_services = _ServiceHolder()


def set_service_overrides(
    *,
    job_source_service=None,
    matching_service=None,
    analyze_multiple_fn=None,
    analyze_single_fn=None,
    dedupe_skills_fn=None,
    gemini_service=None,
    training_fn=None,
) -> None:
    """Inject dependencies for unit tests. Pass None for any you don't override."""
    if job_source_service is not None:
        _services._job_source_svc = job_source_service
    if matching_service is not None:
        _services._matching_svc = matching_service
    if analyze_multiple_fn is not None:
        _services._analyze_multi_fn = analyze_multiple_fn
    if analyze_single_fn is not None:
        _services._analyze_single_fn = analyze_single_fn
    if dedupe_skills_fn is not None:
        _services._dedupe_skills_fn = dedupe_skills_fn
    if gemini_service is not None:
        _services._default_gemini_svc = gemini_service
    if training_fn is not None:
        _services._recommend_training_fn = training_fn


def _reset_service_overrides() -> None:
    """Reset injected overrides. Used for test teardown."""
    global _services
    _services = _ServiceHolder()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_user_profile(profile: Union[UserProfile, Mapping[str, Any], None]) -> UserProfile:
    """Validate canonical profiles while accepting legacy dict workflow callers."""
    if isinstance(profile, UserProfile):
        return profile
    return UserProfile.model_validate(dict(profile or {}))


def _profile_dict(state: SkillGapState) -> Dict[str, Any]:
    """Expose a plain mapping only at existing service boundaries."""
    return _coerce_user_profile(state.get("user_profile")).model_dump(mode="python")


def _record_error(state: SkillGapState, node: str, message: str) -> None:
    """Append a non-fatal error entry to state['errors'] (create list if missing)."""
    if "errors" not in state or state["errors"] is None:
        state["errors"] = []
    state["errors"].append({"node": node, "message": message})


def _record_warning(state: SkillGapState, node: str, message: str) -> None:
    if "warnings" not in state or state["warnings"] is None:
        state["warnings"] = []
    state["warnings"].append({"node": node, "message": message})


def _emit_node_event(state: SkillGapState, node: str, status: str, message: str, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    run_id = state.get("run_id")
    if not run_id:
        return
    try:
        from progress_events import _label, progress_manager
        progress_manager.publish(run_id, node=node, label=_label(node), status=status, message=message, data=data, error=error)
    except Exception:
        logger.debug("Progress event could not be emitted for %s", node, exc_info=True)


def _node_result_details(node: str, result: Mapping[str, Any]) -> Tuple[str, Dict[str, Any]]:
    if node == "profile_parsing":
        profile = result.get("user_profile")
        return "Profile extracted.", {"skills": len(getattr(profile, "skills", []) or [])}
    if node in {"job_search", "job_search_fallback"}:
        count = len(result.get("jobs") or [])
        return f"{count} jobs retrieved.", {"job_count": count, "source": result.get("job_source", "unknown")}
    if node in {"rag_retrieval", "rag_fallback"}:
        count = len(result.get("retrieved_sources") or [])
        return f"{count} sources retrieved.", {"source_count": count, "rag_available": bool(result.get("rag_available"))}
    if node == "skill_matching":
        count = len(result.get("matching_results") or [])
        return f"{count} candidate matches ranked.", {"candidate_count": count}
    if node == "gap_analysis":
        gaps = {str(skill).casefold() for item in (result.get("gap_analyses") or []) for skill in (item.get("missing_skills") or [])}
        return f"{len(gaps)} skill gaps identified.", {"gap_count": len(gaps)}
    if node == "opportunity_simulation":
        opportunities = (result.get("opportunity_analysis") or {}).get("opportunities") or []
        unlocked = sum(int(item.get("jobs_unlocked") or 0) for item in opportunities)
        return f"{unlocked} opportunity unlocks simulated.", {"jobs_unlocked": unlocked}
    if node == "time_to_ready":
        plans = len(result.get("time_to_ready") or {})
        return f"{plans} job learning plans calculated.", {"plan_count": plans}
    if node == "gemini_reasoning":
        return "Analysis generated.", {"reasoning_count": len(result.get("ai_reasoning") or [])}
    if node == "training_recommendations":
        count = len(result.get("training_recommendations") or [])
        return f"{count} learning recommendations ready.", {"course_count": count}
    if node == "report":
        return "Report state packaged.", {"report_status": (result.get("report") or {}).get("status", "ready")}
    return "Stage completed.", {}


def _tracked_node(name: str, function):
    """Decorate a node with lifecycle metadata without changing its logic."""
    def run(state: SkillGapState) -> Dict[str, Any]:
        _emit_node_event(state, name, "running", "Running.")
        result = dict(function(state) or {})
        statuses = dict(state.get("node_status") or {})
        failed = result.get("profile_valid") is False or result.get("status") == "error"
        statuses[name] = "failed" if failed else "completed"
        result["current_node"] = name
        result["node_status"] = statuses
        if failed:
            result["status"] = "error"
            result.setdefault("failed_node", name)
        elif result.get("status") is None:
            result["status"] = "running"
        message, data = _node_result_details(name, result)
        _emit_node_event(state, name, "failed" if failed else "completed", message, data=data, error=(result.get("profile_error") if failed else None))
        return result
    return run


def _load_course_catalog() -> List[Dict[str, Any]]:
    import importlib

    training_mod = importlib.import_module("training-agent.agent")
    courses = training_mod.load_courses()
    return [dict(course) for course in courses if isinstance(course, dict)]


def _collected_missing_skills(analyses: List[Dict[str, Any]]) -> List[str]:
    return _services.dedupe_skills([
        skill
        for analysis in analyses
        for skill in (analysis.get("missing_skills") or [])
    ])


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def profile_parsing_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 1 — Normalize the supplied profile once for all downstream nodes."""
    raw_profile = state.get("profile_input") or state.get("user_profile") or {}
    try:
        profile = _coerce_user_profile(raw_profile)
    except Exception:
        message = "Unable to parse a usable candidate profile."
        errors = list(state.get("errors") or [])
        errors.append({"node": "profile_parsing", "message": message})
        return {"profile_valid": False, "profile_error": message, "status": "error", "failed_node": "profile_parsing", "errors": errors}
    return {"user_profile": profile, "profile": profile, "profile_valid": True, "profile_error": ""}


def _demo_fallback_jobs() -> List[Dict[str, Any]]:
    import importlib
    jobs_module = importlib.import_module("skill-match-agent.data.demo_jobs")
    normalizer = importlib.import_module("skill-match-agent.services.job_normalizer")
    jobs = normalizer.normalize_demo_jobs(jobs_module.get_demo_jobs())
    return [job.model_dump(mode="python") if hasattr(job, "model_dump") else dict(job) for job in jobs]


def job_search_fallback_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 2b — Curated recovery path when the primary source returns no jobs."""
    try:
        return {"jobs": _demo_fallback_jobs(), "job_source": "demo_fallback", "warnings": [*(state.get("warnings") or []), {"node": "job_search_fallback", "message": "Job source returned no jobs. Using curated fallback jobs."}]}
    except Exception:
        message = "No jobs were available from the primary or curated fallback sources."
        errors = list(state.get("errors") or [])
        errors.append({"node": "job_search_fallback", "message": message})
        return {"jobs": [], "job_source": "error", "status": "error", "failed_node": "job_search_fallback", "errors": errors}


def rag_fallback_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 3b — Continue deterministically when RAG is unavailable."""
    warnings = list(state.get("warnings") or [])
    warnings.append({"node": "rag_fallback", "message": "RAG evidence unavailable. Continuing with the job and course catalog."})
    return {"rag_available": False, "retrieved_jobs": [], "retrieved_courses": [], "retrieved_sources": [], "warnings": warnings}


def deterministic_explanation_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 9b — Explicit recovery step after Gemini fallback reasoning."""
    warnings = list(state.get("warnings") or [])
    warnings.append({"node": "deterministic_explanation", "message": "AI explanation unavailable. Showing deterministic analysis."})
    return {"warnings": warnings, "gemini_success": False}


def report_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 11 — Package the completed state for the existing frontend report."""
    return {"report": {"status": "ready", "generated_by": "langgraph", "sections": ["profile", "matching_results", "gap_analyses", "opportunity_analysis", "time_to_ready", "ai_reasoning", "training_recommendations"], "evidence_available": bool(state.get("retrieved_sources")), "tool_calls": len(state.get("tool_trace") or [])}, "status": "completed"}


def job_search_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 1 — Retrieve jobs via the existing JobSourceService.

    The existing service internally handles:
      - Jooble API when key available / call succeeds
      - Seamless 50-demo-jobs fallback on any failure
    So this node just calls it and records the results + source tag.
    """
    profile = _profile_dict(state)
    skills_raw = profile.get("skills") or []
    interests_raw = profile.get("interests") or []
    keywords = profile.get("target_role") or ""
    location = profile.get("location") or ""

    # Run via an event loop wrapper so the node is callable synchronously
    # (LangGraph supports both sync and async nodes depending on runner).
    async def _do():
        try:
            jobs_models, source = await _services.job_source_service.get_jobs(
                keywords=keywords,
                location=location,
                candidate_skills=list(skills_raw),
                interests=list(interests_raw),
            )
            # Convert Pydantic models to plain dicts for TypedDict state
            jobs_dicts = [
                (j.model_dump() if hasattr(j, "model_dump") else dict(j))
                for j in jobs_models
            ]
            return {"jobs": jobs_dicts, "job_source": source}
        except Exception as exc:
            msg = f"Job search failed ({type(exc).__name__}); falling back to demo not available."
            logger.info("job_search_node: %s", msg[:200])
            err_list = list(state.get("errors") or [])
            err_list.append({"node": "job_search", "message": msg})
            return {"jobs": [], "job_source": "error", "errors": err_list}

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside a running event loop (e.g. FastAPI request).
            # asyncio.run() would raise RuntimeError here, so launch the
            # coroutine in a fresh thread using its own isolated loop.
            import concurrent.futures as _futures

            def _run():
                import asyncio as _aio
                return _aio.run(_do())

            with _futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(_run).result()
        return loop.run_until_complete(_do())
    except RuntimeError:
        # No event loop at all — create one via asyncio.run
        return asyncio.run(_do())


def skill_matching_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 2 — Rank all jobs via existing SkillMatchingService.

    Uses `matching_service.rank_jobs(candidate_skills, jobs)`.
    Writes: `user_skills` (deduped) and `matching_results`.
    """
    profile = _profile_dict(state)
    skills_raw = profile.get("skills") or []
    jobs: List[Dict[str, Any]] = list(state.get("jobs") or [])

    deduped_skills = _services.dedupe_skills(list(skills_raw))

    if not jobs:
        # Nothing to match: empty safe result, record info-level error
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "skill_matching",
            "message": "No jobs were returned by the job search step; skipping matching.",
        })
        return {
            "user_skills": deduped_skills,
            "matching_results": [],
            "errors": errors,
        }

    # Convert job dicts back into Pydantic models if the service expects them.
    # First, detect matching_service API: try Pydantic models first.
    import importlib
    try:
        sm_schemas = importlib.import_module("schemas")
        JobPostingCls = sm_schemas.JobPosting
    except Exception:
        try:
            sm_schemas = importlib.import_module("skill-match-agent.schemas")
            JobPostingCls = sm_schemas.JobPosting
        except Exception:
            JobPostingCls = None  # type: ignore

    job_inputs: List[Any] = []
    for j in jobs:
        if JobPostingCls is not None:
            try:
                job_inputs.append(JobPostingCls(**j))
            except Exception:
                job_inputs.append(j)
        else:
            job_inputs.append(j)

    try:
        ranked_models = _services.matching_service.rank_jobs(
            candidate_skills=deduped_skills,
            jobs=job_inputs,
        )
    except Exception as exc:
        msg = f"Matching failed ({type(exc).__name__}); treating as no matches."
        logger.info("skill_matching_node: %s", msg[:200])
        errors = list(state.get("errors") or [])
        errors.append({"node": "skill_matching", "message": msg})
        return {
            "user_skills": deduped_skills,
            "matching_results": [],
            "errors": errors,
        }

    # Convert JobMatchResult models -> plain dicts
    match_dicts = [
        (m.model_dump() if hasattr(m, "model_dump") else dict(m))
        for m in ranked_models
    ]
    return {
        "user_skills": deduped_skills,
        "matching_results": match_dicts,
        "matched_jobs": match_dicts,
    }


def gap_analysis_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 3 — Deterministic Gap Analysis for top-K matched jobs.

    Reuses `analyze_multiple_jobs(user_skills, jobs)` from the existing
    gap_analysis_service. Falls back gracefully when no matches exist.
    """
    user_skills: List[str] = list(state.get("user_skills") or [])
    matches: List[Dict[str, Any]] = list(state.get("matching_results") or [])
    jobs: List[Dict[str, Any]] = list(state.get("jobs") or [])

    jobs_by_id: Dict[str, Dict[str, Any]] = {
        j.get("job_id"): j for j in jobs
    }

    if not matches:
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "gap_analysis",
            "message": "No matching results available; skipping gap analysis.",
        })
        return {
            "gap_analyses": [],
            "skill_gaps": [],
            "errors": errors,
        }

    # Limit to top 10 to keep Gemini traffic bounded
    top_matches = matches[:10]

    analysis_inputs: List[Dict[str, Any]] = []
    for m in top_matches:
        job = jobs_by_id.get(m.get("job_id"), {})
        required = (
            job.get("required_skills")
            or m.get("required_skills")
            or []
        )
        analysis_inputs.append({
            "job_id": m.get("job_id"),
            "job_title": m.get("job_title") or m.get("title"),
            "required_skills": list(required),
            "matched_skills": list(m.get("matched_skills") or []),
            "missing_skills": list(m.get("missing_skills") or []),
            "match_score": m.get("match_score"),
        })

    try:
        analyses = _services.analyze_multiple(
            user_skills=user_skills,
            jobs=analysis_inputs,
        )
    except Exception as exc:
        msg = f"Gap analysis failed ({type(exc).__name__}); skipping."
        logger.info("gap_analysis_node: %s", msg[:200])
        errors = list(state.get("errors") or [])
        errors.append({"node": "gap_analysis", "message": msg})
        return {"gap_analyses": [], "skill_gaps": [], "errors": errors}

    analyses_dicts = [dict(a) for a in analyses]
    return {
        "gap_analyses": analyses_dicts,
        "skill_gaps": analyses_dicts,
    }


def opportunity_simulation_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 6 — Run the existing deterministic Opportunity Discovery logic."""
    analyses = list(state.get("gap_analyses") or [])
    user_skills = list(state.get("user_skills") or [])
    missing_skills = [skill for analysis in analyses for skill in (analysis.get("missing_skills") or [])]
    opportunity = analyze_opportunities(
        candidate_skills=user_skills,
        missing_skills=missing_skills,
        jobs=list(state.get("jobs") or []),
        matching_service=_services.matching_service,
    )
    return {"current_jobs": opportunity.get("current_jobs", 0), "opportunity_analysis": opportunity}


def time_to_ready_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 7 — Calculate job-specific learning plans using the existing engine."""
    import importlib
    analyses = list(state.get("gap_analyses") or [])
    free_only = bool(state.get("free_only", False))
    ttr_module = importlib.import_module("training-agent.time_to_ready")
    courses = _load_course_catalog()
    return {"time_to_ready": ttr_module.calculate_per_job_time_to_ready(analyses, courses=courses, free_only=free_only)}


def _training_skill_key(skill: Any) -> str:
    normalized = _services.dedupe_skills([str(skill or "")])
    return normalized[0].casefold() if normalized else ""


def training_recommendation_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 5 — Reuse the standalone Training Recommendation Agent."""
    analyses: List[Dict[str, Any]] = list(state.get("gap_analyses") or [])
    jobs: List[Dict[str, Any]] = list(state.get("jobs") or [])
    matches: List[Dict[str, Any]] = list(state.get("matching_results") or [])
    opportunity = state.get("opportunity_analysis") or {}
    profile = _profile_dict(state)
    free_only = bool(state.get("free_only", False))

    import importlib
    training_module = importlib.import_module("training-agent.agent")
    courses = training_module.load_courses()
    time_to_ready = dict(state.get("time_to_ready") or {})

    missing_skills = _collected_missing_skills(analyses)
    if not missing_skills or not jobs or not matches:
        return {"training_recommendations": []}

    jobs_by_id = {job.get("job_id"): job for job in jobs}
    top_jobs = [
        jobs_by_id[match.get("job_id")]
        for match in matches[:10]
        if match.get("job_id") in jobs_by_id
    ]
    if not top_jobs:
        return {"training_recommendations": []}

    opportunity_by_skill = {
        _training_skill_key(entry.get("skill")): entry
        for entry in (opportunity.get("opportunities") or [])
    }
    ordered_missing = sorted(
        missing_skills,
        key=lambda skill: (
            -int((opportunity_by_skill.get(_training_skill_key(skill)) or {}).get("jobs_unlocked", 0)),
            _training_skill_key(skill),
        ),
    )

    courses_by_name = {
        course.get("title"): course
        for course in courses
        if isinstance(course, dict) and course.get("title")
    }

    recommendations: List[Dict[str, Any]] = []
    seen_courses = set()
    retrieved_courses = list(state.get("retrieved_courses") or [])
    retrieved_by_title = {
        str(item.get("title") or "").casefold(): item
        for item in retrieved_courses
        if item.get("title")
    }
    for skill in ordered_missing[:3]:
        try:
            result = _services.recommend_training(
                missing_skills=[skill],
                top_job_matches=top_jobs,
                user_profile=profile,
                opportunity_analysis=opportunity,
                free_only=free_only,
            ) or {}
        except TypeError:
            result = _services.recommend_training(
                missing_skills=[skill],
                top_job_matches=top_jobs,
                user_profile=profile,
                opportunity_analysis=opportunity,
            ) or {}
        except Exception as exc:
            logger.info("training_recommendation_node failed for %s: %s", skill, type(exc).__name__)
            continue

        for recommendation in result.get("recommendations") or []:
            course_name = recommendation.get("course_name") or ""
            if not course_name or course_name in seen_courses:
                continue
            seen_courses.add(course_name)
            course = courses_by_name.get(course_name, {})
            course_skill_keys = {
                _training_skill_key(course_skill)
                for course_skill in course.get("skills_taught") or []
            }
            course_opportunities = [
                entry for key, entry in opportunity_by_skill.items()
                if key in course_skill_keys
            ]
            jobs_unlocked = max(
                [int(entry.get("jobs_unlocked", 0)) for entry in course_opportunities]
                or [0]
            )
            duration = recommendation.get("duration_weeks")
            try:
                duration_value = float(duration)
            except (TypeError, ValueError):
                duration_value = 0.0
            output = {
                "course_name": course_name,
                "provider": recommendation.get("provider", ""),
                "duration_weeks": duration,
                "jobs_unlocked": jobs_unlocked,
                "learning_impact": round(jobs_unlocked / duration_value, 2) if duration_value > 0 else None,
                "reasoning": recommendation.get("roi_reasoning", ""),
                "url": recommendation.get("url", ""),
                "price_inr": recommendation.get("price_inr", course.get("price_inr", 0)),
                "is_free": recommendation.get("is_free", course.get("is_free", True)),
            }
            retrieved_course = retrieved_by_title.get(course_name.casefold())
            if retrieved_course and retrieved_course.get("source_id"):
                output["course_id"] = retrieved_course.get("source_id")
                output["source_ids"] = [retrieved_course.get("source_id")]
                output["evidence_sources"] = [retrieved_course]
            elif course.get("course_id"):
                output["course_id"] = course.get("course_id")
                output["source_ids"] = [course.get("course_id")]
            recommendations.append(output)
            break
        if len(recommendations) >= 3:
            break

    return {"training_recommendations": recommendations}


def rag_retrieval_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 4 — Retrieve grounded PathWise job/course evidence."""
    profile = _profile_dict(state)
    jobs: List[Dict[str, Any]] = list(state.get("jobs") or [])
    analyses: List[Dict[str, Any]] = list(state.get("gap_analyses") or [])
    missing_skills = _collected_missing_skills(analyses)

    try:
        from .rag import rag_retriever
    except Exception:
        try:
            from rag import rag_retriever  # type: ignore
        except Exception as exc:
            errors = list(state.get("errors") or [])
            errors.append({
                "node": "rag_retrieval",
                "message": f"RAG retriever unavailable ({type(exc).__name__}).",
            })
            return {
                "retrieved_jobs": [],
                "retrieved_courses": [],
                "retrieved_sources": [],
                "rag_available": False,
                "rag_query": "",
                "rag_index": {"documents": 0, "using_faiss": False},
                "errors": errors,
            }

    try:
        return rag_retriever.retrieve(
            user_profile=profile,
            jobs=jobs,
            courses=_load_course_catalog(),
            missing_skills=missing_skills,
        )
    except Exception as exc:
        logger.info("rag_retrieval_node failed: %s", type(exc).__name__)
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "rag_retrieval",
            "message": f"RAG retrieval failed ({type(exc).__name__}).",
        })
        return {
            "retrieved_jobs": [],
            "retrieved_courses": [],
            "retrieved_sources": [],
            "rag_available": False,
            "rag_query": "",
            "rag_index": {"documents": 0, "using_faiss": False},
            "errors": errors,
        }


MAX_TOOL_CALL_ROUNDS = 2


def _tool_call_model():
    """Create the LangChain Gemini model lazily so normal fallback runs stay safe."""
    import os
    from langchain_google_genai import ChatGoogleGenerativeAI

    try:
        from backend.config import settings
    except ImportError:
        from config import settings
    api_key = os.getenv("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return None
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_TOOL_MODEL", "gemini-2.0-flash"),
        google_api_key=api_key,
        temperature=0,
    )


def gemini_tool_agent_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 8a — Let Gemini select typed tools through native function calling."""
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from .tool_calling import PATHWISE_TOOLS
    except Exception as exc:
        return {"tool_agent_available": False, "warnings": [*(state.get("warnings") or []), {"node": "gemini_tool_agent", "message": "Tool calling unavailable; continuing with deterministic state."}]}

    try:
        model = _tool_call_model()
        if model is None:
            return {"tool_agent_available": False, "warnings": [*(state.get("warnings") or []), {"node": "gemini_tool_agent", "message": "Gemini tool calling is not configured; continuing with deterministic analysis."}]}

        profile = _profile_dict(state)
        missing = _collected_missing_skills(list(state.get("gap_analyses") or []))
        opportunity = state.get("opportunity_analysis") or {}
        prompt = (
            "Review this completed deterministic PathWise analysis. Use a tool only if additional "
            "grounded evidence would materially improve the final explanation. Do not recalculate "
            "values yourself. Prefer search_courses for missing skills or simulate_skill for a "
            "specific what-if; use search_jobs/analyze_gaps only when the current state is insufficient. "
            "After any tool call, provide a concise grounded note.\n\n"
            f"Profile: {profile}\nMissing skills: {missing[:8]}\n"
            f"Opportunity summary: {opportunity.get('opportunities', [])[:8]}\n"
            f"Current tool round: {state.get('tool_call_round', 0)}"
        )
        prior_messages = list(state.get("messages") or [])
        messages = prior_messages or [
            SystemMessage(content="You are the PathWise evidence agent. Tool outputs are authoritative and must not be fabricated."),
            HumanMessage(content=prompt),
        ]
        response = model.bind_tools(PATHWISE_TOOLS).invoke(messages)
        run_id = state.get("run_id")
        if run_id:
            try:
                from progress_events import progress_manager
                for call in (getattr(response, "tool_calls", None) or []):
                    tool_name = call.get("name", "tool")
                    progress_manager.publish(run_id, node=f"tool:{tool_name}", label=tool_name, status="running", message="Gemini requested tool execution.", data={"arguments": _safe_tool_arguments(tool_name, dict(call.get("args") or {}))})
            except Exception:
                logger.debug("Tool running event could not be emitted", exc_info=True)
        return {"messages": ([*messages, response] if not prior_messages else [response]), "tool_agent_available": True}
    except Exception as exc:
        warnings = list(state.get("warnings") or [])
        warnings.append({"node": "gemini_tool_agent", "message": "Gemini tool calling failed; continuing with deterministic analysis."})
        logger.info("gemini_tool_agent_node failed: %s", type(exc).__name__)
        return {"tool_agent_available": False, "warnings": warnings}


def route_after_tool_agent(state: SkillGapState) -> str:
    messages = list(state.get("messages") or [])
    last = messages[-1] if messages else None
    tool_calls = getattr(last, "tool_calls", None) or []
    if state.get("tool_agent_available") and tool_calls and int(state.get("tool_call_round", 0)) < MAX_TOOL_CALL_ROUNDS:
        return "tool_execution"
    return "gemini_reasoning"


def _tool_result_summary(tool_name: str, content: Any) -> Tuple[str, str, Dict[str, Any]]:
    payload = content
    if isinstance(content, str):
        try:
            payload = json.loads(content)
        except Exception:
            payload = {"status": "error", "error": "Tool returned an unreadable result."}
    if not isinstance(payload, Mapping):
        payload = {"status": "error", "error": "Tool returned an invalid result."}
    status = str(payload.get("status") or "error")
    if status == "error":
        return status, str(payload.get("error") or "Tool execution failed."), dict(payload)
    if tool_name == "search_jobs":
        return status, f"{len(payload.get('jobs') or [])} jobs found", dict(payload)
    if tool_name == "search_courses":
        return status, f"{len(payload.get('courses') or [])} courses found", dict(payload)
    if tool_name == "analyze_gaps":
        return status, f"{len(payload.get('analyses') or [])} gap analyses returned", dict(payload)
    if tool_name == "simulate_skill":
        return status, f"{int(payload.get('jobs_unlocked') or 0)} additional opportunities", dict(payload)
    return status, "Tool completed", dict(payload)


def _safe_tool_arguments(tool_name: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
    if tool_name == "analyze_gaps":
        profile = arguments.get("user_profile") or {}
        return {"job_count": len(arguments.get("jobs") or []), "skill_count": len(profile.get("skills") or [])}
    if tool_name == "simulate_skill":
        return {"skill": str(arguments.get("skill") or "")}
    if tool_name == "search_courses":
        return {key: arguments.get(key) for key in ("skills", "max_weeks", "budget_inr", "free_only") if key in arguments}
    return {key: arguments.get(key) for key in ("role", "location", "skills", "limit") if key in arguments}


def tool_trace_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 8b — Convert native AI/tool messages into a safe UI trace."""
    messages = list(state.get("messages") or [])
    calls = list(state.get("tool_calls") or [])
    results = list(state.get("tool_results") or [])
    errors = list(state.get("tool_errors") or [])
    trace = list(state.get("tool_trace") or [])
    seen_call_ids = {str(item.get("tool_call_id")) for item in calls}
    call_by_id = {}
    for message in messages:
        for call in (getattr(message, "tool_calls", None) or []):
            call_id = str(call.get("id") or call.get("name"))
            call_by_id[call_id] = call
            if call_id not in seen_call_ids:
                entry = {"tool_call_id": call_id, "tool_name": call.get("name", ""), "arguments": _safe_tool_arguments(call.get("name", ""), dict(call.get("args") or {}))}
                calls.append(entry)
                seen_call_ids.add(call_id)

    seen_results = {str(item.get("tool_call_id")) for item in results}
    for message in messages:
        if getattr(message, "type", "") != "tool":
            continue
        call_id = str(getattr(message, "tool_call_id", ""))
        if call_id in seen_results:
            continue
        call = call_by_id.get(call_id, {})
        tool_name = str(call.get("name") or getattr(message, "name", "tool"))
        status, summary, payload = _tool_result_summary(tool_name, getattr(message, "content", ""))
        result_entry = {"tool_call_id": call_id, "tool_name": tool_name, "status": status, "result_summary": summary}
        results.append(result_entry)
        trace.append({"tool_name": tool_name, "status": status, "arguments": _safe_tool_arguments(tool_name, dict(call.get("args") or {})), "result_summary": summary})
        run_id = state.get("run_id")
        if run_id:
            try:
                from progress_events import progress_manager
                progress_manager.publish(run_id, node=f"tool:{tool_name}", label=tool_name, status="completed" if status == "success" else "failed", message=summary, data={"tool_name": tool_name}, error=(summary if status == "error" else None))
            except Exception:
                logger.debug("Tool completion event could not be emitted", exc_info=True)
        if status == "error":
            errors.append({"tool_name": tool_name, "error": summary})

    return {"tool_calls": calls, "tool_results": results, "tool_errors": errors, "tool_trace": trace, "tool_call_round": int(state.get("tool_call_round", 0)) + 1}


def gemini_reasoning_node(state: SkillGapState) -> Dict[str, Any]:
    """NODE 4 — Attach Gemini structured reasoning to each gap analysis.

    Uses the existing GeminiService.analyze_gap_reasoning() which already
    handles all failure modes (missing key, API error, timeout, malformed
    JSON) via a deterministic fallback — so this node itself never fails.

    The service's in-built hallucination-protection guarantees that
    strengths / priority_gaps reference only the deterministic
    matched_skills / missing_skills respectively.
    """
    profile = _profile_dict(state)
    jobs_by_id: Dict[str, Dict[str, Any]] = {
        j.get("job_id"): j for j in (state.get("jobs") or [])
    }
    matches_by_id: Dict[str, Dict[str, Any]] = {
        m.get("job_id"): m for m in (state.get("matching_results") or [])
    }
    analyses: List[Dict[str, Any]] = list(state.get("gap_analyses") or [])
    retrieved_jobs = list(state.get("retrieved_jobs") or [])
    retrieved_courses = list(state.get("retrieved_courses") or [])
    retrieved_sources = list(state.get("retrieved_sources") or [])

    if not analyses:
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "gemini_reasoning",
            "message": "No gap analyses available; skipping Gemini reasoning.",
        })
        return {"ai_reasoning": [], "gemini_success": False, "errors": errors}

    svc = _services.default_gemini_service
    all_reasoning: List[Dict[str, Any]] = []

    async def _run_one(job_id, job, match, analysis):
        """Run Gemini for a single job, falling back to deterministic on ANY failure."""
        try:
            # real GeminiService.analyze_gap_reasoning returns (dict, success_flag)
            # and already has internal fallback on API/key/etc failures.
            reasoning_dict, ok_flag = await svc.analyze_gap_reasoning(
                user_profile=profile,
                job=job,
                matching=match,
                gap_analysis=analysis,
                retrieved_jobs=retrieved_jobs,
                retrieved_courses=retrieved_courses,
            )
            return dict(reasoning_dict), bool(ok_flag)
        except Exception as exc:
            # Fallback if svc itself raises (shouldn't with the real service,
            # but the graph must be safe regardless).
            logger.info(
                "gemini_reasoning_node: per-job Gemini call for %s failed (%s); using fallback.",
                job_id,
                type(exc).__name__,
            )
            # Build a minimal deterministic fallback ai_reasoning dict in the
            # same shape AiReasoning schema uses, matching the real service.
            strengths = list(analysis.get("matched_skills") or [])
            missing = list(analysis.get("missing_skills") or [])
            fallback = {
                "summary": (
                    (f"Gemini reasoning unavailable for {analysis.get('job_title', job_id) or 'this role'}."
                     " Using deterministic gap analysis.")
                ),
                "strengths": strengths,
                "priority_gaps": [
                    {"skill": s, "reason": f"{s} is listed as required for this role."}
                    for s in missing
                ],
                "learning_focus": [f"Build working knowledge of {s}" for s in missing],
                "source": "deterministic_fallback",
                "note": "Gemini reasoning unavailable. Using deterministic gap analysis.",
            }
            return fallback, False

    async def _run_all():
        tasks = []
        for analysis in analyses:
            jid = analysis.get("job_id")
            job = jobs_by_id.get(jid, {})
            match = matches_by_id.get(jid, {})
            tasks.append(_run_one(jid, job, match, analysis))
        return await asyncio.gather(*tasks, return_exceptions=False)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running inside an async event loop (e.g. FastAPI).
            # Launch the coroutine in its own thread + loop to avoid RuntimeError.
            import concurrent.futures as _futures

            def _run():
                import asyncio as _aio
                return _aio.run(_run_all())

            with _futures.ThreadPoolExecutor(max_workers=1) as ex:
                results = ex.submit(_run).result()
        else:
            results = loop.run_until_complete(_run_all())
    except RuntimeError:
        results = asyncio.run(_run_all())

    try:
        from .rag.citation_validator import attach_default_citations, validate_reasoning_citations
    except Exception:
        from rag.citation_validator import attach_default_citations, validate_reasoning_citations  # type: ignore

    for (reasoning_dict, ok_flag) in results:
        entry = attach_default_citations(
            dict(reasoning_dict),
            job_sources=retrieved_jobs,
            course_sources=retrieved_courses,
        )
        entry = validate_reasoning_citations(entry, retrieved_sources)
        entry["_success"] = bool(ok_flag)
        all_reasoning.append(entry)

    return {"ai_reasoning": all_reasoning, "gemini_success": bool(results) and all(ok_flag for _, ok_flag in results)}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def error_handler_node(state: SkillGapState) -> Dict[str, Any]:
    """Fatal terminal node that preserves safe, user-readable failure state."""
    errors = list(state.get("errors") or [])
    failed_node = state.get("failed_node") or "unknown"
    if not errors:
        errors = [{"node": failed_node, "message": "The workflow could not continue."}]
    return {"status": "error", "current_node": "error_handler", "failed_node": failed_node, "errors": errors}


def route_after_profile(state: SkillGapState) -> str:
    return "job_search" if state.get("profile_valid") else "error_handler"


def route_after_job_search(state: SkillGapState) -> str:
    return "rag_retrieval" if state.get("jobs") else "job_search_fallback"


def route_after_rag(state: SkillGapState) -> str:
    return "skill_matching" if state.get("rag_available") else "rag_fallback"


def route_after_gemini(state: SkillGapState) -> str:
    return "training_recommendations" if state.get("gemini_success") else "deterministic_explanation"


def build_skill_gap_graph():
    """Build the full lifecycle graph with explicit recovery routes."""
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from .tool_calling import PATHWISE_TOOLS

    workflow = StateGraph(SkillGapState)
    tool_node = ToolNode(PATHWISE_TOOLS)
    nodes = {
        "profile_parsing": profile_parsing_node,
        "job_search": job_search_node,
        "job_search_fallback": job_search_fallback_node,
        "rag_retrieval": rag_retrieval_node,
        "rag_fallback": rag_fallback_node,
        "skill_matching": skill_matching_node,
        "gap_analysis": gap_analysis_node,
        "opportunity_simulation": opportunity_simulation_node,
        "time_to_ready": time_to_ready_node,
        "gemini_tool_agent": gemini_tool_agent_node,
        "tool_trace": tool_trace_node,
        "gemini_reasoning": gemini_reasoning_node,
        "deterministic_explanation": deterministic_explanation_node,
        "training_recommendations": training_recommendation_node,
        "report": report_node,
        "error_handler": error_handler_node,
    }
    for name, function in nodes.items():
        workflow.add_node(name, _tracked_node(name, function))
    # Register the native ToolNode directly so LangGraph supplies its runtime
    # context to each tool execution.
    workflow.add_node("tool_execution", tool_node)

    workflow.set_entry_point("profile_parsing")
    workflow.add_conditional_edges("profile_parsing", route_after_profile, {"job_search": "job_search", "error_handler": "error_handler"})
    workflow.add_conditional_edges("job_search", route_after_job_search, {"rag_retrieval": "rag_retrieval", "job_search_fallback": "job_search_fallback"})
    workflow.add_edge("job_search_fallback", "rag_retrieval")
    workflow.add_conditional_edges("rag_retrieval", route_after_rag, {"skill_matching": "skill_matching", "rag_fallback": "rag_fallback"})
    workflow.add_edge("rag_fallback", "skill_matching")
    workflow.add_edge("skill_matching", "gap_analysis")
    workflow.add_edge("gap_analysis", "opportunity_simulation")
    workflow.add_edge("opportunity_simulation", "time_to_ready")
    workflow.add_edge("time_to_ready", "gemini_tool_agent")
    workflow.add_conditional_edges("gemini_tool_agent", route_after_tool_agent, {"tool_execution": "tool_execution", "gemini_reasoning": "gemini_reasoning"})
    workflow.add_edge("tool_execution", "tool_trace")
    workflow.add_edge("tool_trace", "gemini_tool_agent")
    workflow.add_conditional_edges("gemini_reasoning", route_after_gemini, {"training_recommendations": "training_recommendations", "deterministic_explanation": "deterministic_explanation"})
    workflow.add_edge("deterministic_explanation", "training_recommendations")
    workflow.add_edge("training_recommendations", "report")
    workflow.add_edge("report", END)
    workflow.add_edge("error_handler", END)

    return workflow.compile()


# Default compiled singleton (shared across HTTP requests when not overridden)
try:
    skill_gap_graph = build_skill_gap_graph()
except Exception:  # pragma: no cover - fallback if LangGraph import fails
    skill_gap_graph = None


# ---------------------------------------------------------------------------
# Public orchestration helpers
# ---------------------------------------------------------------------------


def run_skill_gap_workflow(
    user_profile: Union[UserProfile, Mapping[str, Any]],
    free_only: bool = False,
    run_id: Optional[str] = None,
) -> SkillGapState:
    """Execute the full LangGraph workflow synchronously and return the final state."""
    if isinstance(user_profile, Mapping):
        free_only = bool(user_profile.get("free_only", free_only))
    canonical_profile = _coerce_user_profile(user_profile)
    initial: SkillGapState = {
        "profile_input": canonical_profile.model_dump(mode="python"),
        "user_profile": canonical_profile,
        "profile": canonical_profile,
        "jobs": [],
        "user_skills": [],
        "matching_results": [],
        "matched_jobs": [],
        "gap_analyses": [],
        "skill_gaps": [],
        "current_jobs": 0,
        "opportunity_analysis": {
            "current_jobs": 0,
            "opportunities": [],
            "combinations": [],
        },
        "training_recommendations": [],
        "time_to_ready": {},
        "retrieved_jobs": [],
        "retrieved_courses": [],
        "retrieved_sources": [],
        "rag_available": False,
        "rag_query": "",
        "rag_index": {},
        "free_only": free_only,
        "ai_reasoning": [],
        "errors": [],
        "warnings": [],
        "node_status": {},
        "status": "pending",
        "profile_valid": False,
        "gemini_success": False,
        "report": {},
        "messages": [],
        "tool_calls": [],
        "tool_results": [],
        "tool_errors": [],
        "tool_trace": [],
        "tool_call_round": 0,
        "tool_agent_available": False,
        "run_id": run_id,
    }
    graph = skill_gap_graph if skill_gap_graph is not None else build_skill_gap_graph()
    result = graph.invoke(initial)
    # Ensure all required keys exist in final state (invoke may not populate empties)
    for k in (
        "jobs",
        "user_skills",
        "matching_results",
        "matched_jobs",
        "gap_analyses",
        "skill_gaps",
        "ai_reasoning",
        "errors",
        "retrieved_jobs",
        "retrieved_courses",
        "retrieved_sources",
    ):
        if k not in result:
            result[k] = []
    if "rag_available" not in result:
        result["rag_available"] = False
    if "rag_query" not in result:
        result["rag_query"] = ""
    if "rag_index" not in result:
        result["rag_index"] = {}
    if "current_jobs" not in result:
        result["current_jobs"] = 0
    if "opportunity_analysis" not in result:
        result["opportunity_analysis"] = {
            "current_jobs": result["current_jobs"],
            "opportunities": [],
            "combinations": [],
        }
    if "training_recommendations" not in result:
        result["training_recommendations"] = []
    if "time_to_ready" not in result:
        result["time_to_ready"] = {}
    if "free_only" not in result:
        result["free_only"] = free_only
    if "warnings" not in result:
        result["warnings"] = []
    if "node_status" not in result:
        result["node_status"] = {}
    if "status" not in result:
        result["status"] = "completed"
    if "report" not in result:
        result["report"] = {}
    if "messages" not in result:
        result["messages"] = []
    if "tool_calls" not in result:
        result["tool_calls"] = []
    if "tool_results" not in result:
        result["tool_results"] = []
    if "tool_errors" not in result:
        result["tool_errors"] = []
    if "tool_trace" not in result:
        result["tool_trace"] = []
    if "profile" not in result:
        result["profile"] = canonical_profile
    if "user_profile" not in result:
        result["user_profile"] = canonical_profile
    return result


# Public helpers exported for the FastAPI router / tests
__all__ = [
    "SkillGapState",
    "build_skill_gap_graph",
    "skill_gap_graph",
    "run_skill_gap_workflow",
    "profile_parsing_node",
    "job_search_node",
    "job_search_fallback_node",
    "skill_matching_node",
    "gap_analysis_node",
    "opportunity_simulation_node",
    "time_to_ready_node",
    "rag_retrieval_node",
    "gemini_reasoning_node",
    "deterministic_explanation_node",
    "report_node",
    "error_handler_node",
    "route_after_profile",
    "route_after_job_search",
    "route_after_rag",
    "route_after_gemini",
    "set_service_overrides",
    "_reset_service_overrides",
]
