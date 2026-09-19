"""Deterministic skill-combination optimization.

This module deliberately delegates matching and course selection to the
existing services.  It only owns candidate-pool construction, combination
enumeration, constraint evaluation, and comparison-oriented output shaping.
"""

from __future__ import annotations

import importlib
from itertools import combinations
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


MIN_COMBINATION_SIZE = 2
MAX_COMBINATION_SIZE = 2  # Changed from 3 to stop it from checking groups of 3
MAX_CANDIDATE_SKILLS = 8  # Changed from 12 to only check the top 8 most demanded skills
MAX_EVALUATED_COMBINATIONS = 40  # Hard cap dropped from 180 to 40

def _normalize_skill(skill: Any) -> str:
    for module_name in ("services.normalizer", "skill-match-agent.services.normalizer"):
        try:
            return importlib.import_module(module_name).normalize_skill(str(skill))
        except (ImportError, AttributeError, ValueError):
            continue
    return str(skill or "").strip().casefold()


def _as_dict(value: Any) -> Dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return dict(value) if isinstance(value, Mapping) else {}


def _skill_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _dedupe_display(skills: Iterable[Any]) -> List[str]:
    output: List[str] = []
    seen = set()
    for skill in skills:
        display = str(skill or "").strip()
        normalized = _normalize_skill(display)
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(display)
    return output


def _compatible_job_ids(results: Iterable[Any]) -> set[str]:
    ids: set[str] = set()
    for result in results:
        item = _as_dict(result)
        if not item.get("job_id"):
            continue
        # Keep compatibility identical to Opportunity Discovery: a job is
        # unlocked when the deterministic matcher reports no missing skills.
        if not item.get("missing_skills"):
            ids.add(str(item["job_id"]))
    return ids


def _course_source_ids(courses: Sequence[Mapping[str, Any]]) -> List[str]:
    return [str(course.get("course_id")) for course in courses if course.get("course_id")]


def _build_candidate_pool(
    profile_skills: Sequence[str],
    jobs: Sequence[Mapping[str, Any]],
    courses: Sequence[Mapping[str, Any]],
    baseline_results: Sequence[Any],
    rag_sources: Sequence[Mapping[str, Any]],
) -> List[str]:
    """Build a bounded, data-backed pool without inventing skills."""
    current = {_normalize_skill(skill) for skill in profile_skills}
    candidates: Dict[str, Tuple[str, int, int]] = {}

    def add(skill: Any, job_signal: int = 0, course_signal: int = 0) -> None:
        display = str(skill or "").strip()
        normalized = _normalize_skill(display)
        if not normalized or normalized in current:
            return
        old = candidates.get(normalized)
        if old:
            candidates[normalized] = (old[0], old[1] + job_signal, old[2] + course_signal)
        else:
            candidates[normalized] = (display, job_signal, course_signal)

    for result in baseline_results:
        item = _as_dict(result)
        for skill in _skill_list(item.get("missing_skills")):
            add(skill, job_signal=2)

    for job in jobs:
        for skill in _skill_list(job.get("required_skills")):
            if _normalize_skill(skill) not in current:
                add(skill, job_signal=1)

    # Courses are only allowed to enrich skills already supported by a job
    # requirement or a retrieved evidence record.
    job_skill_norms = {
        _normalize_skill(skill)
        for job in jobs
        for skill in _skill_list(job.get("required_skills"))
    }
    rag_skill_norms = {
        _normalize_skill(skill)
        for source in rag_sources
        for skill in _skill_list(source.get("metadata", {}).get("required_skills"))
        + _skill_list(source.get("metadata", {}).get("skills_taught"))
    }
    for course in courses:
        for skill in _skill_list(course.get("skills_taught")):
            normalized = _normalize_skill(skill)
            if normalized in job_skill_norms or normalized in rag_skill_norms:
                add(skill, course_signal=1)

    ordered = sorted(
        candidates.values(),
        key=lambda item: (-(item[1] + item[2]), -item[1], -item[2], _normalize_skill(item[0])),
    )
    return [item[0] for item in ordered[:MAX_CANDIDATE_SKILLS]]


def _evidence_for(
    skills: Sequence[str],
    courses: Sequence[Mapping[str, Any]],
    rag_sources: Sequence[Mapping[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    selected = {_normalize_skill(skill) for skill in skills}
    matched_courses = []
    for course in courses:
        course_skills = {_normalize_skill(skill) for skill in _skill_list(course.get("skills_taught"))}
        if selected & course_skills:
            matched_courses.append(dict(course))

    source_ids: List[str] = []
    for source in rag_sources:
        metadata = source.get("metadata") or {}
        source_skills = _skill_list(metadata.get("required_skills")) + _skill_list(metadata.get("skills_taught"))
        if selected & {_normalize_skill(skill) for skill in source_skills}:
            source_id = source.get("source_id")
            if source_id and source_id not in source_ids:
                source_ids.append(str(source_id))
    return matched_courses, source_ids


def optimize_skill_combinations(
    *,
    user_profile: Mapping[str, Any],
    jobs: Sequence[Any],
    courses: Sequence[Mapping[str, Any]],
    matching_service: Any,
    calculate_time_to_ready: Any,
    max_weeks: float,
    budget_inr: float,
    rag_sources: Optional[Sequence[Mapping[str, Any]]] = None,
    min_combination_size: int = MIN_COMBINATION_SIZE,
    max_combination_size: int = MAX_COMBINATION_SIZE,
) -> Dict[str, Any]:
    """Return comparable valid and constraint-exceeded skill combinations."""
    profile = _as_dict(user_profile)
    profile_skills = _dedupe_display(_skill_list(profile.get("skills")))
    job_dicts = [_as_dict(job) for job in jobs]
    course_dicts = [dict(course) for course in courses if isinstance(course, Mapping)]
    evidence = list(rag_sources or [])

    baseline_results = matching_service.rank_jobs(profile_skills, jobs)
    baseline_ids = _compatible_job_ids(baseline_results)
    candidate_pool = _build_candidate_pool(
        profile_skills, job_dicts, course_dicts, baseline_results, evidence
    )

    max_size = max(min_combination_size, min(max_combination_size, len(candidate_pool)))
    combinations_to_evaluate = [
        tuple(sorted(combo, key=_normalize_skill))
        for size in range(max(2, min_combination_size), max_size + 1)
        for combo in combinations(candidate_pool, size)
    ]
    combinations_to_evaluate = list(dict.fromkeys(combinations_to_evaluate))
    # Keep interactive requests bounded while preserving every pair and the
    # highest-ranked triples from the demand-ordered candidate pool.
    combinations_to_evaluate = combinations_to_evaluate[:MAX_EVALUATED_COMBINATIONS]

    output: List[Dict[str, Any]] = []
    for combo in combinations_to_evaluate:
        simulated_skills = profile_skills + list(combo)
        simulated_results = matching_service.rank_jobs(simulated_skills, jobs)
        simulated_ids = _compatible_job_ids(simulated_results)
        unlocked_ids = sorted(simulated_ids - baseline_ids)
        unlocked_jobs = [job for job in job_dicts if str(job.get("job_id")) in unlocked_ids]

        time_result = calculate_time_to_ready(list(combo), course_dicts)
        selected_courses = list(time_result.get("recommended_courses") or [])
        learning_weeks = time_result.get("total_weeks", 0)
        cost_inr = time_result.get("total_cost_inr", 0)
        within_time = float(learning_weeks) <= float(max_weeks)
        within_budget = float(cost_inr) <= float(budget_inr)
        matched_courses, source_ids = _evidence_for(combo, course_dicts, evidence)
        course_ids = [str(course.get("course_id")) for course in selected_courses if course.get("course_id")]

        item = {
            "skills": list(combo),
            "additional_jobs": len(unlocked_ids),
            "opportunity_gain": len(unlocked_ids),
            "learning_weeks": learning_weeks,
            "cost_inr": cost_inr,
            "within_time": within_time,
            "within_budget": within_budget,
            "within_constraints": within_time and within_budget,
            "opportunities_per_week": round(len(unlocked_ids) / float(learning_weeks), 2) if learning_weeks else None,
            "opportunities_per_rupee": round(len(unlocked_ids) / float(cost_inr), 6) if cost_inr else None,
            "job_ids": unlocked_ids,
            "unlocked_jobs": unlocked_jobs,
            "courses": selected_courses,
            "course_ids": course_ids,
            "available_courses": matched_courses,
            "source_ids": source_ids,
            "uncovered_skills": list(time_result.get("uncovered_skills") or []),
            "is_fully_covered": bool(time_result.get("is_fully_covered", True)),
        }
        output.append(item)

    valid = [item for item in output if item["within_constraints"]]
    exceeded = [item for item in output if not item["within_constraints"]]
    ranking = lambda item: (-item["opportunity_gain"], float(item["learning_weeks"]), float(item["cost_inr"]), tuple(_normalize_skill(s) for s in item["skills"]))
    valid.sort(key=ranking)
    exceeded.sort(key=ranking)

    return {
        "constraints": {"max_weeks": max_weeks, "budget_inr": budget_inr},
        "candidate_skills": candidate_pool,
        "baseline_jobs": len(baseline_ids),
        "combinations": valid + exceeded,
        "valid_combinations": valid,
        "constraint_exceeded_combinations": exceeded,
        "rag_sources": evidence,
    }
