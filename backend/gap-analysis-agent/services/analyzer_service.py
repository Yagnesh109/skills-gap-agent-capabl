from typing import List, Dict, Any, Tuple

try:
    from .gap_analysis_service import (
        GapAnalysisService,
        gap_analysis_service,
        dedupe_skill_list,
        analyze_single_job_gap,
        analyze_multiple_jobs,
    )
except (ImportError, ValueError):
    from gap_analysis_service import (  # type: ignore
        GapAnalysisService,
        gap_analysis_service,
        dedupe_skill_list,
        analyze_single_job_gap,
        analyze_multiple_jobs,
    )


class SkillAnalyzerService:
    """
    Helper service for comparing possessed skills against target requirements
    and structuring gap categories (Critical, Nice-to-have, etc.).

    Updated for Step 5: now delegates to the deterministic gap_analysis_service
    while preserving the legacy method signatures.
    """

    def __init__(self, service: GapAnalysisService = gap_analysis_service):
        self._svc = service

    def identify_missing_skills(
        self,
        possessed_skills: List[str],
        required_skills: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Compares candidate skills to job requirements to find missing skills.

        Returns a list of structured per-skill gap dictionaries (legacy format):
          [{ "skill_name": str,
             "importance_level": "High|Medium|Low",
             "category": "Technical" }]
        """
        analysis = analyze_single_job_gap(
            user_skills=possessed_skills,
            job_id="legacy-analyzer",
            job_title="Target Role",
            required_skills=required_skills,
        )
        missing_display = analysis.get("missing_skills", [])
        results: List[Dict[str, Any]] = []
        for ms in missing_display:
            results.append({
                "skill_name": ms,
                "importance_level": analysis.get("gap_priority", "Medium"),
                "category": "Technical",
                "suggested_action": f"Acquire practical experience and foundational knowledge in {ms}.",
            })
        return results

    def calculate_readiness_score(
        self,
        total_required: int,
        matched_count: int,
    ) -> float:
        """
        Calculates career readiness percentage score (0.0 - 100.0).

        Safe handling for edge cases:
          - total_required == 0 -> 100.0 (no requirements means fully ready)
          - matched_count < 0  -> clamp to 0
          - matched_count > total_required -> clamp to 100.0
        """
        if total_required <= 0:
            return 100.0
        matched = max(0, min(matched_count, total_required))
        return round((matched / total_required) * 100.0, 2)


# Legacy singleton export preserved for backward compatibility
analyzer_service = SkillAnalyzerService()
