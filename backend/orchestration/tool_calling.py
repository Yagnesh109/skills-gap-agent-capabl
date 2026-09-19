"""Real LangChain tools for grounded PathWise agent actions.

The tools are intentionally thin adapters. Existing deterministic services
remain the source of truth for jobs, gaps, courses, and opportunities.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool


def _run_async(awaitable):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(awaitable)).result()
        return loop.run_until_complete(awaitable)
    except RuntimeError:
        return asyncio.run(awaitable)


def _dump(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return dict(value) if isinstance(value, dict) else {}


def _error(tool_name: str, message: str) -> Dict[str, Any]:
    return {"tool": tool_name, "status": "error", "error": message}


@tool
def search_jobs(
    role: str = "",
    location: str = "",
    skills: Optional[List[str]] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Search the real PathWise job source for roles matching a profile.

    Use this when additional job information is needed beyond the jobs already
    present in graph state. Results come from Jooble/demo normalization and are
    never invented by the model.
    """
    try:
        source_module = importlib.import_module("skill-match-agent.services.job_source_service")
        bounded_limit = max(1, min(int(limit), 25))
        jobs, source = _run_async(source_module.job_source_service.get_jobs(
            keywords=str(role or ""),
            location=str(location or ""),
            candidate_skills=list(skills or []),
        ))
        job_dicts = [_dump(job) for job in jobs[:bounded_limit]]
        return {"tool": "search_jobs", "status": "success", "source": source, "jobs": job_dicts, "job_ids": [job.get("job_id") for job in job_dicts]}
    except Exception as exc:
        return _error("search_jobs", "Job provider unavailable; existing graph data remains available.")


@tool
def search_courses(
    skills: List[str],
    max_weeks: Optional[float] = None,
    budget_inr: Optional[float] = None,
    free_only: bool = False,
) -> Dict[str, Any]:
    """Find real catalog courses for target skills under optional constraints.

    Use this when the user needs learning options for missing skills. Returned
    durations, prices, IDs, and URLs come only from the PathWise course catalog.
    """
    try:
        training_module = importlib.import_module("training-agent.agent")
        time_module = importlib.import_module("training-agent.time_to_ready")
        requested = {str(skill).strip().casefold() for skill in skills if str(skill).strip()}
        courses = time_module.validate_course_data(training_module.load_courses())
        results = []
        for course in courses:
            taught = {str(skill).casefold() for skill in course.get("skills_taught", [])}
            if not requested.intersection(taught):
                continue
            if free_only and not course.get("is_free"):
                continue
            if max_weeks is not None and float(course.get("duration_weeks", 0)) > float(max_weeks):
                continue
            if budget_inr is not None and float(course.get("price_inr", 0)) > float(budget_inr):
                continue
            results.append({
                "course_id": course.get("course_id"),
                "course_name": course.get("title"),
                "skills": course.get("skills_taught_original", course.get("skills_taught", [])),
                "duration_weeks": course.get("duration_weeks"),
                "price_inr": course.get("price_inr", 0),
                "is_free": bool(course.get("is_free")),
                "url": course.get("url", ""),
                "source": "course_catalog",
            })
        return {"tool": "search_courses", "status": "success", "courses": results[:12], "course_ids": [course.get("course_id") for course in results[:12]]}
    except Exception:
        return _error("search_courses", "Course catalog unavailable; no fabricated courses were returned.")


@tool
def analyze_gaps(user_profile: Dict[str, Any], jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run deterministic gap analysis for the supplied jobs and profile.

    Use this when gaps must be recalculated for a different job set. The
    existing gap-analysis service determines matched and missing skills.
    """
    try:
        gap_module = importlib.import_module("gap-analysis-agent.services.gap_analysis_service")
        profile = dict(user_profile or {})
        normalized_jobs = []
        for job in jobs or []:
            item = dict(job or {})
            normalized_jobs.append({
                **item,
                "job_id": item.get("job_id"),
                "job_title": item.get("job_title") or item.get("title") or "Untitled role",
                "required_skills": list(item.get("required_skills") or []),
            })
        analyses = gap_module.analyze_multiple_jobs(
            user_skills=list(profile.get("skills") or []),
            jobs=normalized_jobs,
        )
        output = []
        for analysis in analyses:
            item = _dump(analysis)
            required = item.get("required_skills") or []
            matched = item.get("matched_skills") or []
            item["coverage"] = round((len(matched) / len(required)) * 100, 2) if required else 100.0
            output.append({
                "job_id": item.get("job_id"),
                "matched_skills": matched,
                "missing_skills": item.get("missing_skills") or [],
                "coverage": item["coverage"],
            })
        return {"tool": "analyze_gaps", "status": "success", "analyses": output}
    except Exception:
        return _error("analyze_gaps", "Gap analysis could not be completed from the supplied data.")


@tool
def simulate_skill(user_profile: Dict[str, Any], skill: str) -> Dict[str, Any]:
    """Simulate adding one skill and return deterministic job unlock results.

    Use this for a what-if question about one additional skill. Counts are
    based on unique compatible job IDs from the existing matcher.
    """
    try:
        source_module = importlib.import_module("skill-match-agent.services.job_source_service")
        matching_module = importlib.import_module("skill-match-agent.services.matching_service")
        profile = dict(user_profile or {})
        jobs, source = _run_async(source_module.job_source_service.get_jobs(
            keywords=profile.get("target_role") or "",
            location=profile.get("location") or "",
            candidate_skills=list(profile.get("skills") or []),
            interests=list(profile.get("interests") or []),
        ))
        current_skills = list(profile.get("skills") or [])
        baseline = matching_module.matching_service.rank_jobs(current_skills, jobs)
        simulated = matching_module.matching_service.rank_jobs(current_skills + [skill], jobs)

        def compatible(results):
            return {str(item.job_id) for item in results if not getattr(item, "missing_skills", [])}

        before_ids = compatible(baseline)
        after_ids = compatible(simulated)
        unlocked = sorted(after_ids - before_ids)
        return {
            "tool": "simulate_skill",
            "status": "success",
            "skill": skill,
            "source": source,
            "before_match_count": len(before_ids),
            "after_match_count": len(after_ids),
            "jobs_unlocked": len(unlocked),
            "unlocked_job_ids": unlocked,
        }
    except Exception:
        return _error("simulate_skill", "Skill simulation could not be completed from the available job data.")


PATHWISE_TOOLS = [search_jobs, search_courses, analyze_gaps, simulate_skill]
