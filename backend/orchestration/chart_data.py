"""Chart-ready projections of existing deterministic career intelligence."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _skills(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique_skills(value: Any) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for skill in _skills(value):
        normalized = _norm(skill)
        if normalized:
            output.setdefault(normalized, skill)
    return output


def build_career_intelligence_charts(
    *,
    gap_analyses: Iterable[Mapping[str, Any]],
    opportunity_analysis: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Transform existing gap/opportunity results without recalculating matches."""
    # Merge duplicate analysis records by job ID so one job contributes only
    # once to both skill-gap counts and coverage.
    jobs: Dict[str, Dict[str, Any]] = {}
    for analysis in gap_analyses or []:
        item = dict(analysis)
        job_id = str(item.get("job_id") or f"analysis-{len(jobs)}")
        current = jobs.setdefault(job_id, {"required": {}, "matched": {}, "missing": {}})
        current["required"].update(_unique_skills(item.get("required_skills")))
        current["matched"].update(_unique_skills(item.get("matched_skills")))
        current["missing"].update(_unique_skills(item.get("missing_skills")))

    gap_job_ids: Dict[str, set[str]] = {}
    for job_id, item in jobs.items():
        for normalized, display in item["missing"].items():
            gap_job_ids.setdefault(normalized, set()).add(job_id)

    skill_gap = [
        {"skill": next(item["missing"][normalized] for item in jobs.values() if normalized in item["missing"]), "job_count": len(job_ids)}
        for normalized, job_ids in gap_job_ids.items()
    ]
    skill_gap.sort(key=lambda item: (-item["job_count"], _norm(item["skill"])))

    # These values are already calculated by Opportunity Discovery using the
    # existing matcher; the chart only selects and orders them for display.
    opportunity_unlock = []
    for item in (opportunity_analysis or {}).get("opportunities", []) or []:
        if not isinstance(item, Mapping) or not item.get("skill"):
            continue
        opportunity_unlock.append({
            "skill": str(item["skill"]),
            "jobs_unlocked": int(item.get("jobs_unlocked") or 0),
        })
    opportunity_unlock.sort(key=lambda item: (-item["jobs_unlocked"], _norm(item["skill"])))

    total_required = 0
    total_matched = 0
    for item in jobs.values():
        required = set(item["required"])
        matched = set(item["matched"]) & required
        total_required += len(required)
        total_matched += len(matched)

    coverage = None
    if total_required:
        matched_percentage = round((total_matched / total_required) * 100, 2)
        coverage = {
            "matched_percentage": matched_percentage,
            "missing_percentage": round(100 - matched_percentage, 2),
            "matched_skills": total_matched,
            "required_skills": total_required,
        }

    return {
        "skill_gap": skill_gap[:8],
        "opportunity_unlock": opportunity_unlock[:8],
        "skill_coverage": coverage,
    }
