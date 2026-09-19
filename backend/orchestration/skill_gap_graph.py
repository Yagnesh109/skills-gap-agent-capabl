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
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from typing_extensions import TypedDict

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
      - ai_reasoning:  list[dict] of structured Gemini reasoning (one per job; fallback-safe)
      - errors:        list[{node, message}] of non-fatal informational errors
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
    profile: UserProfile
    matched_jobs: List[Dict[str, Any]]
    skill_gaps: List[Dict[str, Any]]
    ai_reasoning: List[Dict[str, Any]]
    errors: List[Dict[str, str]]


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


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


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

    def _opportunity_result(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        missing_skills = [
            skill
            for analysis in analyses
            for skill in (analysis.get("missing_skills") or [])
        ]
        return analyze_opportunities(
            candidate_skills=user_skills,
            missing_skills=missing_skills,
            jobs=jobs,
            matching_service=_services.matching_service,
        )

    jobs_by_id: Dict[str, Dict[str, Any]] = {
        j.get("job_id"): j for j in jobs
    }

    if not matches:
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "gap_analysis",
            "message": "No matching results available; skipping gap analysis.",
        })
        opportunity = _opportunity_result([])
        return {
            "gap_analyses": [],
            "skill_gaps": [],
            "current_jobs": opportunity["current_jobs"],
            "opportunity_analysis": opportunity,
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
    opportunity = _opportunity_result(analyses_dicts)
    return {
        "gap_analyses": analyses_dicts,
        "skill_gaps": analyses_dicts,
        "current_jobs": opportunity["current_jobs"],
        "opportunity_analysis": opportunity,
    }


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

    missing_skills = _services.dedupe_skills([
        skill
        for analysis in analyses
        for skill in (analysis.get("missing_skills") or [])
    ])
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

    import importlib
    training_module = importlib.import_module("training-agent.agent")
    courses = training_module.load_courses()
    courses_by_name = {
        course.get("title"): course
        for course in courses
        if isinstance(course, dict) and course.get("title")
    }

    recommendations: List[Dict[str, Any]] = []
    seen_courses = set()
    for skill in ordered_missing[:3]:
        try:
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
            }
            recommendations.append(output)
            break
        if len(recommendations) >= 3:
            break

    return {"training_recommendations": recommendations}


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

    if not analyses:
        errors = list(state.get("errors") or [])
        errors.append({
            "node": "gemini_reasoning",
            "message": "No gap analyses available; skipping Gemini reasoning.",
        })
        return {"ai_reasoning": [], "errors": errors}

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

    for (reasoning_dict, ok_flag) in results:
        entry = dict(reasoning_dict)
        entry["_success"] = bool(ok_flag)
        all_reasoning.append(entry)

    return {"ai_reasoning": all_reasoning}


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_skill_gap_graph():
    """Build and compile the 4-node LangGraph StateGraph for Skill Gap analysis.

    Execution order:
      job_search -> skill_matching -> gap_analysis -> gemini_reasoning -> END
    """
    from langgraph.graph import StateGraph, END

    workflow = StateGraph(SkillGapState)
    workflow.add_node("job_search", job_search_node)
    workflow.add_node("skill_matching", skill_matching_node)
    workflow.add_node("gap_analysis", gap_analysis_node)
    workflow.add_node("gemini_reasoning", gemini_reasoning_node)
    workflow.add_node("training_recommendations", training_recommendation_node)

    workflow.set_entry_point("job_search")
    workflow.add_edge("job_search", "skill_matching")
    workflow.add_edge("skill_matching", "gap_analysis")
    workflow.add_edge("gap_analysis", "gemini_reasoning")
    workflow.add_edge("gemini_reasoning", "training_recommendations")
    workflow.add_edge("training_recommendations", END)

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
) -> SkillGapState:
    """Execute the full LangGraph workflow synchronously and return the final state."""
    canonical_profile = _coerce_user_profile(user_profile)
    initial: SkillGapState = {
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
        "ai_reasoning": [],
        "errors": [],
    }
    graph = skill_gap_graph if skill_gap_graph is not None else build_skill_gap_graph()
    result = graph.invoke(initial)
    # Ensure all required keys exist in final state (invoke may not populate empties)
    for k in ("jobs", "user_skills", "matching_results", "matched_jobs", "gap_analyses", "skill_gaps", "ai_reasoning", "errors"):
        if k not in result:
            result[k] = []
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
    "job_search_node",
    "skill_matching_node",
    "gap_analysis_node",
    "gemini_reasoning_node",
    "set_service_overrides",
    "_reset_service_overrides",
]
