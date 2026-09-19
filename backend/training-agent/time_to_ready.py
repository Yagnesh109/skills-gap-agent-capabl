"""
Time-to-Ready Calculation Engine

Deterministic logic to calculate total learning time and cost per target job
based on missing skills and available courses.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Reuse the project's skill normalizer
try:
    from gap_analysis_agent.services.gap_analysis_service import normalize_skill
except (ImportError, ValueError):
    try:
        from backend.gap_analysis_agent.services.gap_analysis_service import normalize_skill
    except (ImportError, ValueError):
        import importlib
        gap_svc_mod = importlib.import_module("gap-analysis-agent.services.gap_analysis_service")
        normalize_skill = gap_svc_mod.normalize_skill


def load_courses() -> List[Dict[str, Any]]:
    """Load the course catalog from courses.json."""
    file_path = Path(__file__).parent / "courses.json"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def validate_course_data(courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate and normalize course data, filtering out invalid entries."""
    valid_courses = []
    for course in courses:
        if not isinstance(course, dict):
            continue
        if not course.get("course_id") or not course.get("title"):
            continue
        try:
            duration = course.get("duration_weeks")
            if duration is None:
                continue
            duration_val = float(duration)
            if duration_val <= 0:
                continue
        except (TypeError, ValueError):
            continue
        try:
            price = course.get("price_inr", 0)
            price_val = int(price)
            if price_val < 0:
                price_val = 0
        except (TypeError, ValueError):
            price_val = 0
        is_free = course.get("is_free", False)
        if is_free and price_val != 0:
            price_val = 0
        if not is_free and price_val == 0:
            price_val = 1
        skills_taught = course.get("skills_taught") or []
        if not isinstance(skills_taught, list):
            skills_taught = []
        normalized_skills = [normalize_skill(s) for s in skills_taught if s]
        normalized_skills = [s for s in normalized_skills if s]
        if not normalized_skills:
            continue
        valid_course = {
            "course_id": course["course_id"],
            "title": course["title"],
            "provider": course.get("provider", ""),
            "skills_taught": normalized_skills,
            "skills_taught_original": course.get("skills_taught", []),
            "duration_weeks": duration_val,
            "difficulty": course.get("difficulty", ""),
            "url": course.get("url", ""),
            "price_inr": price_val,
            "is_free": bool(is_free),
        }
        valid_courses.append(valid_course)
    return valid_courses


def build_skill_to_courses_map(courses: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Build a mapping from normalized skill to list of courses that teach it."""
    skill_map: Dict[str, List[Dict[str, Any]]] = {}
    for course in courses:
        for skill in course.get("skills_taught", []):
            if skill not in skill_map:
                skill_map[skill] = []
            skill_map[skill].append(course)
    return skill_map


def _normalize_missing_skills(missing_skills: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Return deduped normalized skills and a normalized -> display lookup."""
    normalized: List[str] = []
    display_by_norm: Dict[str, str] = {}
    for skill in missing_skills or []:
        norm = normalize_skill(str(skill))
        if not norm or norm in display_by_norm:
            continue
        normalized.append(norm)
        display_by_norm[norm] = str(skill).strip()
    return normalized, display_by_norm


def select_courses_for_skills(
    missing_skills: List[str],
    courses: List[Dict[str, Any]],
    free_only: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str], bool]:
    """
    Select a minimal set of courses to cover the missing skills.
    
    Returns:
        (selected_courses, uncovered_skills, is_fully_covered)
    """
    if not missing_skills:
        return [], [], True
    
    valid_courses = validate_course_data(courses)
    if free_only:
        valid_courses = [c for c in valid_courses if c["is_free"]]
    
    if not valid_courses:
        return [], missing_skills, False
    
    skill_to_courses = build_skill_to_courses_map(valid_courses)
    missing_norm, display_by_norm = _normalize_missing_skills(missing_skills)
    
    # Find which missing skills have no courses at all
    uncovered = [skill for skill in missing_norm if skill not in skill_to_courses]
    
    # Skills that can be covered
    coverable_skills = [skill for skill in missing_norm if skill in skill_to_courses]
    
    if not coverable_skills:
        return [], [display_by_norm.get(skill, skill) for skill in missing_norm], False
    
    # Greedy selection: prefer courses covering multiple missing skills,
    # then shorter duration, then lower cost
    selected_courses: List[Dict[str, Any]] = []
    selected_course_ids: Set[str] = set()
    covered_skills: Set[str] = set()
    
    remaining_skills = set(coverable_skills)
    
    while remaining_skills:
        best_course = None
        best_score = (-1, float("inf"), float("inf"))  # (skills_covered, -duration, -cost)
        
        for course in valid_courses:
            if course["course_id"] in selected_course_ids:
                continue
            
            course_skills = set(course.get("skills_taught", []))
            newly_covered = course_skills & remaining_skills
            if not newly_covered:
                continue
            
            # Score: more skills covered is better, then shorter duration, then lower cost
            score = (len(newly_covered), -course["duration_weeks"], -course["price_inr"])
            if score > best_score:
                best_score = score
                best_course = course
        
        if best_course is None:
            # No course can cover remaining skills
            break
        
        selected_courses.append(best_course)
        selected_course_ids.add(best_course["course_id"])
        covered_skills.update(best_course.get("skills_taught", []))
        remaining_skills -= covered_skills
    
    final_uncovered = [s for s in missing_norm if s not in covered_skills]
    
    # Build output with skills_covered for each course
    output_courses = []
    for course in selected_courses:
        course_skills = set(course.get("skills_taught", []))
        skills_covered = [
            display_by_norm.get(skill, skill)
            for skill in missing_norm
            if skill in course_skills
        ]
        output_courses.append({
            "course_id": course["course_id"],
            "title": course["title"],
            "provider": course["provider"],
            "skills_covered": skills_covered,
            "duration_weeks": course["duration_weeks"],
            "price_inr": course["price_inr"],
            "is_free": course["is_free"],
            "url": course["url"],
            "difficulty": course["difficulty"],
        })
    
    is_fully_covered = len(final_uncovered) == 0
    
    return (
        output_courses,
        [display_by_norm.get(skill, skill) for skill in final_uncovered],
        is_fully_covered,
    )


def calculate_time_to_ready(
    missing_skills: List[str],
    courses: Optional[List[Dict[str, Any]]] = None,
    free_only: bool = False,
) -> Dict[str, Any]:
    """
    Calculate Time-to-Ready for a single job based on its missing skills.
    
    Returns:
        Dictionary with total_weeks, total_cost_inr, recommended_courses,
        uncovered_skills, is_fully_covered
    """
    if courses is None:
        courses = load_courses()
    
    if not missing_skills:
        return {
            "recommended_courses": [],
            "total_weeks": 0,
            "total_cost_inr": 0,
            "uncovered_skills": [],
            "is_fully_covered": True,
        }
    
    selected_courses, uncovered_skills, is_fully_covered = select_courses_for_skills(
        missing_skills=missing_skills,
        courses=courses,
        free_only=free_only,
    )
    
    total_weeks = sum(c["duration_weeks"] for c in selected_courses)
    total_cost_inr = sum(c["price_inr"] for c in selected_courses)
    
    return {
        "recommended_courses": selected_courses,
        "total_weeks": total_weeks,
        "total_cost_inr": total_cost_inr,
        "uncovered_skills": uncovered_skills,
        "is_fully_covered": is_fully_covered,
    }


def calculate_per_job_time_to_ready(
    gap_analyses: List[Dict[str, Any]],
    courses: Optional[List[Dict[str, Any]]] = None,
    free_only: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate Time-to-Ready for each job in the gap analyses.
    
    Returns:
        Dictionary mapping job_id to time_to_ready result
    """
    results = {}
    for analysis in gap_analyses:
        job_id = analysis.get("job_id")
        job_title = analysis.get("job_title", "")
        missing_skills = analysis.get("missing_skills", [])
        
        if not job_id:
            continue
        
        ttr = calculate_time_to_ready(
            missing_skills=missing_skills,
            courses=courses,
            free_only=free_only,
        )
        ttr["job_id"] = job_id
        ttr["job_title"] = job_title
        results[job_id] = ttr
    
    return results
