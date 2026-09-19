import logging
import html
import re
from typing import List, Dict, Any, Tuple, Optional, Set


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization integration with skill-match-agent (reuse without hard copy)
# Falls back to a local deterministic normalizer if import is unavailable.
# ---------------------------------------------------------------------------


def _load_normalizer_from_skill_match_agent():
    """Attempt to import the canonical normalizer from skill-match-agent.

    Returns a tuple (normalize_skill_func, build_skill_map_func) or (None, None)
    if the import path is not reachable in the current Python context.
    """
    try:
        from skill_match_agent_services_normalizer import (  # type: ignore
            normalize_skill as _sm_norm,
            build_skill_map as _sm_map,
        )
        return _sm_norm, _sm_map
    except Exception:
        pass

    # Try dynamic import via importlib to support hyphenated module directory
    try:
        import importlib
        normalizer_mod = importlib.import_module("services.normalizer")
        return normalizer_mod.normalize_skill, normalizer_mod.build_skill_map
    except Exception:
        pass

    try:
        import sys
        from pathlib import Path
        # Add parent folders to path
        backend_dir = Path(__file__).resolve().parent.parent
        agent_dir = backend_dir / "skill-match-agent"
        for p in (str(backend_dir), str(agent_dir)):
            if p not in sys.path:
                sys.path.insert(0, p)
        import importlib
        normalizer_mod = importlib.import_module("services.normalizer")
        return normalizer_mod.normalize_skill, normalizer_mod.build_skill_map
    except Exception:
        return None, None


# Copy of the alias dictionary kept local as a deterministic fallback
# This mirrors the skill-match-agent normalizer. The *primary* source is
# still the imported function above; this fallback is used only when the
# import path is unavailable (e.g. during isolated unit tests).
_FALLBACK_SKILL_ALIASES: Dict[str, str] = {
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "react framework": "react",
    "python": "python",
    "python 3": "python",
    "python3": "python",
    "python 3.x": "python",
    "python programming": "python",
    "javascript": "javascript",
    "js": "javascript",
    "ecmascript": "javascript",
    "vanilla js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "node": "nodejs",
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "node js": "nodejs",
    "sql": "sql",
    "structured query language": "sql",
    "rdbms": "sql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "postgre sql": "postgresql",
    "mysql": "mysql",
    "my sql": "mysql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "rest": "rest api",
    "rest api": "rest api",
    "restful api": "rest api",
    "rest apis": "rest api",
    "restful apis": "rest api",
    "graphql": "graphql",
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "tailwind": "tailwind css",
    "tailwind css": "tailwind css",
    "bootstrap": "bootstrap",
    "fastapi": "fastapi",
    "fast api": "fastapi",
    "django": "django",
    "flask": "flask",
    "spring": "spring boot",
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "next": "next.js",
    "next.js": "next.js",
    "nextjs": "next.js",
    "express": "express.js",
    "express.js": "express.js",
    "expressjs": "express.js",
    "docker": "docker",
    "docker containers": "docker",
    "containerization": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "version control": "version control",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",
    "ml": "machine learning",
    "machine learning": "machine learning",
    "dl": "deep learning",
    "deep learning": "deep learning",
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "nlp": "nlp",
    "natural language processing": "nlp",
    "computer vision": "computer vision",
    "cv": "computer vision",
    "genai": "generative ai",
    "generative ai": "generative ai",
    "llm": "llms",
    "llms": "llms",
    "large language models": "llms",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "pandas": "pandas",
    "numpy": "numpy",
    "scikit-learn": "scikit-learn",
    "scikitlearn": "scikit-learn",
    "sklearn": "scikit-learn",
    "powerbi": "powerbi",
    "power bi": "powerbi",
    "tableau": "tableau",
    "excel": "excel",
    "ms excel": "excel",
    "dsa": "data structures",
    "data structures": "data structures",
    "algorithms": "algorithms",
    "oop": "object-oriented programming",
    "oops": "object-oriented programming",
    "object-oriented programming": "object-oriented programming",
    "c++": "c++",
    "cpp": "c++",
    "c": "c",
    "golang": "go",
    "go": "go",
    "java": "java",
    "core java": "java",
}


# Canonical display-name mapping used for fall-back normalization
_FALLBACK_CANONICAL_DISPLAY: Dict[str, str] = {
    v: v.title().replace("Api", "API").replace("Ai", "AI").replace("Js", "JS")
    for v in set(_FALLBACK_SKILL_ALIASES.values())
}
# Overwrite with precise casing
_FALLBACK_CANONICAL_DISPLAY.update({
    "python": "Python",
    "react": "React",
    "javascript": "JavaScript",
    "nodejs": "Node.js",
    "typescript": "TypeScript",
    "next.js": "Next.js",
    "express.js": "Express.js",
    "rest api": "REST API",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "spring boot": "Spring Boot",
    "html": "HTML",
    "css": "CSS",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "version control": "Version Control",
    "ci/cd": "CI/CD",
    "graphql": "GraphQL",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "NLP",
    "computer vision": "Computer Vision",
    "generative ai": "Generative AI",
    "llms": "LLMs",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-learn",
    "powerbi": "PowerBI",
    "tableau": "Tableau",
    "excel": "Excel",
    "data structures": "Data Structures",
    "algorithms": "Algorithms",
    "object-oriented programming": "OOP",
    "c++": "C++",
    "c": "C",
    "go": "Go",
    "java": "Java",
})


def _fallback_normalize_skill(skill: str) -> str:
    """Deterministic skill normalizer used when the skill-match-agent
    module is not on the import path. Mirrors the project's normalizer."""
    if not skill or not isinstance(skill, str):
        return ""
    cleaned = skill.strip().lower()
    cleaned = re.sub(r"[\'\"]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned in _FALLBACK_SKILL_ALIASES:
        return _FALLBACK_SKILL_ALIASES[cleaned]
    simplified = re.sub(
        r"\b(development|developer|programming|framework|library|technologies|technology)\b",
        "",
        cleaned,
    ).strip()
    if simplified in _FALLBACK_SKILL_ALIASES:
        return _FALLBACK_SKILL_ALIASES[simplified]
    return cleaned


def _fallback_build_skill_map(skills: List[str]) -> Dict[str, str]:
    """Fallback: build normalized -> original lookup preserving display casing."""
    skill_map: Dict[str, str] = {}
    for s in skills:
        norm = _fallback_normalize_skill(s)
        if norm and norm not in skill_map:
            skill_map[norm] = s.strip()
    return skill_map


# Resolve normalizer once at import time
_IMPORTED_NORMALIZE_SKILL, _IMPORTED_BUILD_SKILL_MAP = _load_normalizer_from_skill_match_agent()


def normalize_skill(skill: str) -> str:
    """Normalize a skill string using the project's canonical normalizer.

    Falls back to a local mirror when the skill-match-agent normalizer
    cannot be imported (e.g. in isolated test environments).
    """
    if _IMPORTED_NORMALIZE_SKILL is not None:
        try:
            return _IMPORTED_NORMALIZE_SKILL(skill)
        except Exception:
            return _fallback_normalize_skill(skill)
    return _fallback_normalize_skill(skill)


def build_skill_map(skills: List[str]) -> Dict[str, str]:
    """Return a mapping from normalized-skill -> original display skill.

    Reuses the project's normalizer when available.
    """
    if _IMPORTED_BUILD_SKILL_MAP is not None:
        try:
            return _IMPORTED_BUILD_SKILL_MAP(skills)
        except Exception:
            return _fallback_build_skill_map(skills)
    return _fallback_build_skill_map(skills)


def dedupe_skill_list(skills: List[str]) -> List[str]:
    """Deduplicate a skill list case-insensitively after normalization,
    preserving the first occurrence's display form and original order."""
    if not skills:
        return []
    seen: Set[str] = set()
    result: List[str] = []
    for s in skills:
        if s is None:
            continue
        norm = normalize_skill(str(s))
        if not norm:
            continue
        if norm in seen:
            continue
        seen.add(norm)
        result.append(str(s).strip())
    return result


def _display_for_norm(norm: str, fallback_map: Dict[str, str]) -> str:
    """Return a human-readable display form for a normalized skill."""
    if norm in fallback_map:
        return fallback_map[norm]
    return _FALLBACK_CANONICAL_DISPLAY.get(norm, norm.title())


# ---------------------------------------------------------------------------
# Human-readable list helpers for explanation text
# ---------------------------------------------------------------------------


def _format_list(items: List[str]) -> str:
    """Format a list into an Oxford-comma English phrase.

    ['A']         -> 'A'
    ['A', 'B']    -> 'A and B'
    ['A', 'B','C'] -> 'A, B, and C'
    []             -> ''
    """
    if not items:
        return ""
    if len(items) == 1:
        return str(items[0])
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


# ---------------------------------------------------------------------------
# Gap analysis core logic
# ---------------------------------------------------------------------------


def analyze_single_job_gap(
    user_skills: List[str],
    job_id: str,
    job_title: str,
    required_skills: List[str],
    precomputed_matched: Optional[List[str]] = None,
    precomputed_missing: Optional[List[str]] = None,
    match_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Run deterministic gap analysis for a single job.

    Args:
        user_skills: deduplicated user skills (any casing accepted)
        job_id: unique job identifier
        job_title: role name
        required_skills: list of required skills from the job posting
        precomputed_matched: optional matched skills from Skill Matching Agent
        precomputed_missing: optional missing skills from Skill Matching Agent
        match_score: optional score from Skill Matching Agent (0-100)

    Returns:
        Dictionary matching SingleJobGapAnalysis schema fields.
    """
    # Deduplicate inputs using project normalizer
    dedup_user_skills = dedupe_skill_list(user_skills)
    dedup_required_skills = dedupe_skill_list(required_skills)

    user_norm_map = build_skill_map(dedup_user_skills)
    req_norm_map = build_skill_map(dedup_required_skills)

    user_norm_set = set(user_norm_map.keys())
    req_norm_set = set(req_norm_map.keys())

    total_required = len(req_norm_set)

    # Use precomputed results if provided AND they validate cleanly after
    # normalization; otherwise recompute deterministically.
    recompute = True
    if precomputed_matched is not None and precomputed_missing is not None:
        # Validate: union of matched/missing (normalized) must equal required set
        matched_norm = {normalize_skill(s) for s in precomputed_matched if normalize_skill(s)}
        missing_norm = {normalize_skill(s) for s in precomputed_missing if normalize_skill(s)}
        if matched_norm.union(missing_norm) == req_norm_set and matched_norm.isdisjoint(missing_norm):
            recompute = False

    if recompute:
        matched_norms = req_norm_set.intersection(user_norm_set)
        missing_norms = req_norm_set - matched_norms
    else:
        matched_norms = {normalize_skill(s) for s in precomputed_matched if normalize_skill(s)}
        missing_norms = {normalize_skill(s) for s in precomputed_missing if normalize_skill(s)}

    # Map back to display names (prefer original casing from req input)
    matched_display = sorted(
        [req_norm_map[n] for n in matched_norms if n in req_norm_map]
    )
    missing_display = sorted(
        [req_norm_map[n] for n in missing_norms if n in req_norm_map]
    )

    # --- Determine gap priority (deterministic rules) ---
    if total_required == 0:
        gap_priority = "None"
    elif len(missing_norms) == 0:
        gap_priority = "None"
    else:
        missing_pct = len(missing_norms) / total_required
        if match_score is not None:
            if match_score >= 85.0:
                gap_priority = "Low"
            elif match_score >= 65.0:
                gap_priority = "Medium" if missing_pct < 0.5 else "High"
            elif match_score >= 40.0:
                gap_priority = "High"
            else:
                gap_priority = "Critical"
        else:
            if missing_pct >= 0.75:
                gap_priority = "Critical"
            elif missing_pct >= 0.5:
                gap_priority = "High"
            elif missing_pct >= 0.25:
                gap_priority = "Medium"
            else:
                gap_priority = "Low"

    # --- Generate gap explanation (deterministic, data-driven) ---
    user_has_any = len(user_norm_set) > 0
    matched_count = len(matched_norms)
    missing_count = len(missing_norms)

    if total_required == 0:
        gap_explanation = (
            f"No required skills are listed for the {job_title} role, "
            "so no skill gaps can be identified."
        )
    elif not user_has_any:
        if missing_count:
            missing_list_str = _format_list(missing_display)
            gap_explanation = (
                f"The candidate has not provided any skills that match the requirements "
                f"for the {job_title} role. {missing_list_str} {'are' if missing_count != 1 else 'is'} "
                "required and currently missing."
            )
        else:
            gap_explanation = (
                f"The candidate has not provided any skills, but the {job_title} role "
                "currently has no listed required skills either."
            )
    elif matched_count == 0 and missing_count:
        missing_list_str = _format_list(missing_display)
        gap_explanation = (
            f"None of the candidate's current skills overlap with the {job_title} "
            f"role requirements. {missing_list_str} {'are' if missing_count != 1 else 'is'} "
            "needed to qualify."
        )
    elif matched_count and missing_count == 0:
        matched_list_str = _format_list(matched_display)
        gap_explanation = (
            f"The candidate currently has all of the required skills for the {job_title} role. "
            f"The matched skills include {matched_list_str}."
        )
    else:
        matched_list_str = _format_list(matched_display)
        missing_list_str = _format_list(missing_display)
        gap_explanation = (
            f"The candidate already has {matched_list_str}, but {missing_list_str} "
            f"{'are' if missing_count != 1 else 'is'} required for the {job_title} role "
            "and are currently missing."
        )

    return {
        "job_id": job_id,
        "job_title": job_title,
        "user_skills": dedup_user_skills,
        "required_skills": dedup_required_skills,
        "matched_skills": matched_display,
        "missing_skills": missing_display,
        "match_score": round(match_score, 2) if isinstance(match_score, (int, float)) and not (match_score != match_score) else None,  # NaN guard
        "gap_explanation": gap_explanation,
        "gap_priority": gap_priority,
    }


def analyze_multiple_jobs(
    user_skills: List[str],
    jobs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Analyze multiple matched jobs in sequence, preserving input order.

    Each job dict should contain at least: job_id, job_title, required_skills.
    Optional: matched_skills, missing_skills, match_score.

    Returns an ordered list of per-job analysis result dicts.
    """
    analyses: List[Dict[str, Any]] = []
    for idx, job in enumerate(jobs):
        if not isinstance(job, dict):
            raise ValueError(f"Job at index {idx} must be a dictionary")
        analysis = analyze_single_job_gap(
            user_skills=user_skills,
            job_id=job["job_id"],
            job_title=job["job_title"],
            required_skills=job.get("required_skills", []),
            precomputed_matched=job.get("matched_skills"),
            precomputed_missing=job.get("missing_skills"),
            match_score=job.get("match_score"),
        )
        analyses.append(analysis)
    return analyses


def compute_metadata(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate summary metadata for a batch of gap analyses."""
    count_jobs_analyzed = len(analyses)
    total_missing_skills = sum(len(a["missing_skills"]) for a in analyses)
    total_matched_skills = sum(len(a["matched_skills"]) for a in analyses)

    priority_counts: Dict[str, int] = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "None": 0,
    }
    all_missing: Set[str] = set()
    for a in analyses:
        p = a.get("gap_priority", "Medium")
        if p not in priority_counts:
            priority_counts[p] = 0
        priority_counts[p] += 1
        for ms in a.get("missing_skills", []):
            n = normalize_skill(ms)
            if n:
                all_missing.add(n)

    avg_match_score: Optional[float] = None
    scores = [a["match_score"] for a in analyses if isinstance(a.get("match_score"), (int, float))]
    if scores:
        avg_match_score = round(sum(scores) / len(scores), 2)

    return {
        "count_jobs_analyzed": count_jobs_analyzed,
        "total_missing_skill_occurrences": total_missing_skills,
        "total_matched_skill_occurrences": total_matched_skills,
        "unique_missing_skills_count": len(all_missing),
        "avg_match_score": avg_match_score,
        "gap_priority_counts": priority_counts,
    }


# ---------------------------------------------------------------------------
# Public service singleton
# ---------------------------------------------------------------------------


class GapAnalysisService:
    """Deterministic Skill Gap Analysis service (Step 5).

    Reuses the project's skill normalizer from skill-match-agent when
    reachable on the import path, and provides per-job as well as
    batched analysis methods.
    """

    def __init__(self):
        self.normalize_skill = normalize_skill
        self.build_skill_map = build_skill_map
        self.dedupe_skill_list = dedupe_skill_list

    def analyze_job(
        self,
        *,
        user_skills: List[str],
        job_id: str,
        job_title: str,
        required_skills: List[str],
        matched_skills: Optional[List[str]] = None,
        missing_skills: Optional[List[str]] = None,
        match_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        return analyze_single_job_gap(
            user_skills=user_skills,
            job_id=job_id,
            job_title=job_title,
            required_skills=required_skills,
            precomputed_matched=matched_skills,
            precomputed_missing=missing_skills,
            match_score=match_score,
        )

    def analyze_jobs(self, *, user_skills: List[str], jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return analyze_multiple_jobs(user_skills=user_skills, jobs=jobs)

    def metadata_for(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        return compute_metadata(analyses)


# Global singleton instance
gap_analysis_service = GapAnalysisService()
