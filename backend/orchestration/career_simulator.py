from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

try:
    from gap_analysis_agent.services.gap_analysis_service import normalize_skill
except Exception:
    try:
        from backend.gap_analysis_agent.services.gap_analysis_service import normalize_skill
    except Exception:
        import importlib
        gap_mod = importlib.import_module("gap-analysis-agent.services.gap_analysis_service")
        normalize_skill = gap_mod.normalize_skill

import importlib

try:
    from skill_match_agent.services.matching_service import matching_service
    from skill_match_agent.services.job_source_service import job_source_service
except Exception:
    try:
        module = importlib.import_module("skill_match_agent.services.matching_service")
        source_module = importlib.import_module("skill_match_agent.services.job_source_service")
        matching_service = module.matching_service
        job_source_service = source_module.job_source_service
    except Exception:
        match_module = importlib.import_module("skill-match-agent.services.matching_service")
        source_module = importlib.import_module("skill-match-agent.services.job_source_service")
        matching_service = match_module.matching_service
        job_source_service = source_module.job_source_service

try:
    from training_agent.time_to_ready import calculate_time_to_ready
except Exception:
    try:
        ttr = importlib.import_module("training_agent.time_to_ready")
        calculate_time_to_ready = ttr.calculate_time_to_ready
    except Exception:
        ttr = importlib.import_module("training-agent.time_to_ready")
        calculate_time_to_ready = ttr.calculate_time_to_ready


def _dedupe_skills(skills: Sequence[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for skill in skills or []:
        text = str(skill or "").strip()
        key = normalize_skill(text)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _job_id(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        return result.get("job_id") or result.get("id") or result.get("title")
    return getattr(result, "job_id", None) or getattr(result, "id", None) or getattr(result, "title", None)


def _match_score(result: Any) -> float:
    if isinstance(result, dict):
        value = result.get("match_score", 0.0)
    else:
        value = getattr(result, "match_score", 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _has_missing_skill(result: Any) -> bool:
    if isinstance(result, dict):
        missing = result.get("missing_skills")
    else:
        missing = getattr(result, "missing_skills", None)
    if missing is None:
        return False
    return bool(missing)


def _eligible_jobs(results: Sequence[Any]) -> List[Any]:
    return [item for item in results if not _has_missing_skill(item)]


def _average_match(results: Sequence[Any]) -> float:
    eligible = _eligible_jobs(results)
    if not eligible:
        return 0.0
    return round(sum(_match_score(item) for item in eligible) / len(eligible), 2)


def simulate_career_path(
    user_profile: Dict[str, Any],
    add_skills: Optional[Sequence[str]] = None,
    max_weeks: Optional[int] = None,
    budget_inr: Optional[int] = None,
) -> Dict[str, Any]:
    """Reuses the existing matching and time-to-ready logic to simulate learning additions."""
    profile_skills = list((user_profile or {}).get("skills") or [])
    current_skills = _dedupe_skills(profile_skills)
    selected_skills = _dedupe_skills(skill for skill in (add_skills or []) if ((normalize_skill(str(skill or "")) or "") not in {normalize_skill(s) for s in current_skills}))

    jobs = []
    try:
        jobs, _ = job_source_service.get_jobs(
            keywords=str((user_profile or {}).get("target_role") or ""),
            location=str((user_profile or {}).get("location") or ""),
            candidate_skills=current_skills,
            interests=list((user_profile or {}).get("interests") or []),
            force_demo=True,
        )
    except Exception:
        jobs = []

    if not jobs:
        return {
            "current": {"matching_jobs": 0, "average_match": 0.0},
            "simulated": {"skills_added": selected_skills, "matching_jobs": 0, "average_match": 0.0},
            "change": {"jobs_unlocked": 0, "average_match_change": 0.0},
            "learning": {"courses": [], "total_weeks": 0, "total_cost_inr": 0},
            "constraints": {
                "max_weeks": max_weeks,
                "budget_inr": budget_inr,
                "within_time_limit": max_weeks is None or 0 <= max_weeks,
                "within_budget": budget_inr is None or 0 <= budget_inr,
            },
            "evidence": {"job_ids": []},
            "selected_skills": selected_skills,
        }

    current_results = matching_service.rank_jobs(candidate_skills=current_skills, jobs=jobs)
    simulated_skills = current_skills + selected_skills
    simulated_results = matching_service.rank_jobs(candidate_skills=simulated_skills, jobs=jobs)

    current_eligible = _eligible_jobs(current_results)
    simulated_eligible = _eligible_jobs(simulated_results)
    current_ids = {str(_job_id(item)) for item in current_eligible if _job_id(item) is not None}
    simulated_ids = {str(_job_id(item)) for item in simulated_eligible if _job_id(item) is not None}
    jobs_unlocked = len(simulated_ids - current_ids)

    current_average = _average_match(current_results)
    simulated_average = _average_match(simulated_results)
    average_match_change = round(simulated_average - current_average, 2)

    learning_plan = calculate_time_to_ready(
        selected_skills,
        courses=None,
        free_only=bool((user_profile or {}).get("free_only", False)),
    )

    total_weeks = float(learning_plan.get("total_weeks") or 0)
    total_cost_inr = int(learning_plan.get("total_cost_inr") or 0)
    recommended_courses = learning_plan.get("recommended_courses") or []

    within_time_limit = True if max_weeks is None else total_weeks <= max_weeks
    within_budget = True if budget_inr is None else total_cost_inr <= budget_inr

    result = {
        "current": {
            "matching_jobs": len(current_eligible),
            "average_match": current_average,
        },
        "simulated": {
            "skills_added": selected_skills,
            "matching_jobs": len(simulated_eligible),
            "average_match": simulated_average,
        },
        "change": {
            "jobs_unlocked": jobs_unlocked,
            "average_match_change": average_match_change,
        },
        "learning": {
            "courses": recommended_courses,
            "total_weeks": total_weeks,
            "total_cost_inr": total_cost_inr,
        },
        "constraints": {
            "max_weeks": max_weeks,
            "budget_inr": budget_inr,
            "within_time_limit": within_time_limit,
            "within_budget": within_budget,
        },
        "evidence": {
            "job_ids": sorted(simulated_ids - current_ids),
        },
        "selected_skills": selected_skills,
    }
    if max_weeks is not None and not within_time_limit:
        result["constraints"]["time_excess_weeks"] = round(total_weeks - max_weeks, 2)
    if budget_inr is not None and not within_budget:
        result["constraints"]["budget_excess_inr"] = total_cost_inr - budget_inr
    return result
