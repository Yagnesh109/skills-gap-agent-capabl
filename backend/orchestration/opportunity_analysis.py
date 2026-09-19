"""Deterministic opportunity analysis built on the existing skill matcher."""

from __future__ import annotations

import importlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


MAX_COMBINATION_SKILLS = 5
MAX_COMBINATIONS = 10


def _normalizer():
    for module_name in ("services.normalizer", "skill-match-agent.services.normalizer"):
        try:
            module = importlib.import_module(module_name)
            return module.normalize_skill
        except (ImportError, AttributeError, ValueError):
            continue

    def fallback(skill: Any) -> str:
        return str(skill or "").strip().casefold()

    return fallback


normalize_skill = _normalizer()


def _load_job_posting_class():
    for module_name in ("schemas", "skill-match-agent.schemas"):
        try:
            module = importlib.import_module(module_name)
            return module.JobPosting
        except (ImportError, AttributeError, ValueError):
            continue
    return None


def _coerce_jobs(jobs: Sequence[Any]) -> List[Any]:
    job_posting = _load_job_posting_class()
    if job_posting is None:
        return list(jobs or [])

    result = []
    for job in jobs or []:
        if isinstance(job, job_posting) or (
            hasattr(job, "model_dump") and hasattr(job, "required_skills")
        ):
            result.append(job)
        elif isinstance(job, Mapping):
            try:
                result.append(job_posting.model_validate(dict(job)))
            except Exception:
                continue
    return result


def _result_score(result: Any) -> float:
    if isinstance(result, Mapping):
        value = result.get("match_score", 0.0)
    else:
        value = getattr(result, "match_score", 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _compatible_job_count(matching_service: Any, skills: List[str], jobs: List[Any]) -> int:
    if not jobs:
        return 0
    results = matching_service.rank_jobs(candidate_skills=skills, jobs=jobs)
    compatible_count = 0
    for result in results:
        if isinstance(result, Mapping):
            missing = result.get("missing_skills")
        else:
            missing = getattr(result, "missing_skills", None)
        if missing is not None:
            if not missing:
                compatible_count += 1
        elif _result_score(result) > 0.0:
            # Compatibility fallback for lightweight matcher test doubles.
            compatible_count += 1
    return compatible_count


def _dedupe_skills(skills: Iterable[Any]) -> List[Tuple[str, str]]:
    seen = set()
    result: List[Tuple[str, str]] = []
    for skill in skills or []:
        display = str(skill or "").strip()
        normalized = normalize_skill(display)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append((normalized, display))
    return result


def _load_skill_durations() -> Dict[str, float]:
    courses_path = Path(__file__).resolve().parents[1] / "training-agent" / "courses.json"
    try:
        courses = json.loads(courses_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}

    durations: Dict[str, float] = {}
    for course in courses if isinstance(courses, list) else []:
        if not isinstance(course, dict):
            continue
        try:
            duration = float(course.get("duration_weeks"))
        except (TypeError, ValueError):
            continue
        if duration <= 0:
            continue
        for skill in course.get("skills_taught") or []:
            normalized = normalize_skill(skill)
            if normalized:
                durations[normalized] = min(duration, durations.get(normalized, duration))
    return durations


def analyze_opportunities(
    *,
    candidate_skills: Optional[Sequence[str]],
    missing_skills: Optional[Sequence[str]],
    jobs: Sequence[Any],
    matching_service: Any,
) -> Dict[str, Any]:
    """Calculate job opportunities by repeatedly calling the existing matcher."""
    normalized_jobs = _coerce_jobs(jobs)
    current_skills = [display for _, display in _dedupe_skills(candidate_skills or [])]
    missing = _dedupe_skills(missing_skills or [])
    current_jobs = _compatible_job_count(matching_service, current_skills, normalized_jobs)
    durations = _load_skill_durations()

    opportunities: List[Dict[str, Any]] = []
    for normalized, display in missing:
        projected_skills = current_skills + [display]
        projected_jobs = _compatible_job_count(matching_service, projected_skills, normalized_jobs)
        entry: Dict[str, Any] = {
            "skill": display,
            "current_jobs": current_jobs,
            "projected_jobs": projected_jobs,
            "jobs_unlocked": max(0, projected_jobs - current_jobs),
        }
        duration = durations.get(normalized)
        if duration is not None:
            entry["duration_weeks"] = duration
            entry["learning_impact"] = round(entry["jobs_unlocked"] / duration, 2)
        opportunities.append(entry)

    opportunities.sort(key=lambda item: (-item["jobs_unlocked"], normalize_skill(item["skill"])))

    combinations_output: List[Dict[str, Any]] = []
    combination_candidates = [display for _, display in missing[:MAX_COMBINATION_SKILLS]]
    for skill_pair in combinations(combination_candidates, 2):
        projected_jobs = _compatible_job_count(
            matching_service,
            current_skills + list(skill_pair),
            normalized_jobs,
        )
        combinations_output.append({
            "skills": list(skill_pair),
            "current_jobs": current_jobs,
            "projected_jobs": projected_jobs,
            "jobs_unlocked": max(0, projected_jobs - current_jobs),
        })
    combinations_output.sort(
        key=lambda item: (-item["jobs_unlocked"], tuple(normalize_skill(skill) for skill in item["skills"]))
    )
    combinations_output = combinations_output[:MAX_COMBINATIONS]

    return {
        "current_jobs": current_jobs,
        "opportunities": opportunities,
        "combinations": combinations_output,
    }
