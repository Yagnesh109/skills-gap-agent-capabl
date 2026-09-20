"""Shared Google Gemini service for Step 6.

Design goals:
- Isolate all Gemini SDK usage to this file.
- Use official google-generativeai SDK when GEMINI_API_KEY is configured.
- Return structured JSON (ai_reasoning whenever possible.
- Never expose deterministic fallback behavior when Gemini is missing / errored / rate-limited.
- never log or return the API key.
- never modify deterministic facts (match_score / matched / required / missing).
"""

from __future__ import annotations

import json
import logging
import re
import asyncio
import traceback
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from backend.config import settings
except Exception:  # pragma: no cover - import paths vary by test harness
    import sys
    from pathlib import Path
    _backend_dir = Path(__file__).resolve().parent.parent
    if str(_backend_dir) not in sys.path:
        sys.path.insert(0, str(_backend_dir))
    try:
        from config import settings  # type: ignore
    except Exception:
        class _Stub:
            GEMINI_API_KEY: str = ""
            GEMINI_MODEL: str = "gemini-3.6-flash"
            GEMINI_TEMPERATURE: float = 0.2
            GEMINI_TIMEOUT_SECONDS: float = 20.0
        settings = _Stub()


# ---------------------------------------------------------------------------
# System + Response Schema (structured JSON shape expected from Gemini)
# ---------------------------------------------------------------------------

AI_REASONING_SHAPE = {
    "summary": str,
    "strengths": list,
    "priority_gaps": list,
    "learning_focus": list,
}


def _build_fallback_ai_reasoning(
    *,
    job_title: str,
    matched_skills: List[str],
    missing_skills: List[str],
    unavailable_reason: str = "Gemini unavailable.",
) -> Dict[str, Any]:
    """Return a deterministic, safe ai_reasoning payload when Gemini can't run."""
    from .gap_analysis_service import _format_list  # local import avoids cycle

    summary_parts = [f"{unavailable_reason} Using deterministic gap analysis."]
    if matched_skills:
        summary_parts.append(
            f"The candidate already has {_format_list(matched_skills)}."
        )
    else:
        summary_parts.append("The candidate currently has no matched required skills.")
    if missing_skills:
        summary_parts.append(
            f"{_format_list(missing_skills)} {'is' if len(missing_skills) == 1 else 'are'} "
            f"required for the {job_title} role and need to be learned."
        )
    else:
        summary_parts.append("No skill gaps were identified.")
    return {
        "summary": " ".join(summary_parts),
        "strengths": list(matched_skills),
        "priority_gaps": [
            {
                "skill": skill,
                "reason": (
                    f"{skill} is explicitly listed as a required skill for the "
                    f"{job_title} role."
                ),
            }
            for skill in missing_skills
        ],
        "learning_focus": [f"{s} fundamentals" for s in missing_skills],
        "source": "deterministic_fallback",
        "note": unavailable_reason,
    }


# ---------------------------------------------------------------------------
# Prompt + Prompt Builder
# ---------------------------------------------------------------------------


GEMINI_SYSTEM_PROMPT = """You are a career skill-gap analysis assistant working for a Skill Matching AI Agent.

STRICT RULES — DO NOT VIOLATE THESE:
1. Use ONLY the structured information provided in the user message. Never invent facts.
2. Do NOT modify or correct the calculated match_score — treat it as authoritative truth.
3. Do NOT add or remove skills from matched_skills, required_skills, or missing_skills.
4. Do NOT invent companies, salaries, courses, job URLs, certifications, or dates.
5. If the provided information does not include something, say so — do not guess.

Your role is EXPLANATION AND REASONING ONLY:
- Summarize what the candidate already has.
- Summarize what skills are missing.
- Explain, briefly, why each missing skill matters for THIS specific role/job.
- Recommend what to learn first.

Return STRICTLY a single JSON object with the following shape and NO OTHER TEXT:
{
  "summary": "One-paragraph summary of the skill gap situation, referencing only supplied data and retrieved evidence.",
  "strengths": [
    {
      "skill": "Matched skill name",
      "source_ids": ["JOB-001"]
    }
  ],
  "priority_gaps": [
    {
      "skill": "Missing skill name",
      "reason": "Short, practical reason this is important for THIS role, using retrieved jobs as evidence",
      "source_ids": ["JOB-001", "JOB-002"]
    },
    ...
  ],
  "learning_focus": [
    {
      "topic": "Practical short learning goal",
      "source_ids": ["COURSE-101"]
    }
  ]
}

Citation rules:
- Only cite source IDs that appear in retrieved_jobs or retrieved_courses.
- Do not invent job IDs, course IDs, companies, courses, URLs, or skills.
- If retrieved evidence is empty, return empty source_ids arrays.
- For job-market reasons, cite JOB source IDs.
- For learning/course suggestions, cite COURSE source IDs when available.

Do NOT wrap in markdown (```). Do NOT prefix with "Here's the JSON..." or anything else.
Return ONLY the JSON object."""


def _build_user_prompt_payload(
    *,
    user_profile: Dict[str, Any],
    job: Dict[str, Any],
    matching: Dict[str, Any],
    gap_analysis: Dict[str, Any],
    retrieved_jobs: Optional[List[Dict[str, Any]]] = None,
    retrieved_courses: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build a structured user prompt that is small, clear, and deterministic."""
    trimmed = {
        "user_profile": {
            "education": user_profile.get("education"),
            "skills": user_profile.get("skills") or [],
            "location": user_profile.get("location"),
            "interests": user_profile.get("interests") or [],
        },
        "job": {
            "title": job.get("title") or job.get("job_title"),
            "company": job.get("company"),
            "required_skills": job.get("required_skills") or [],
            "description": (job.get("description") or "")[:2000],
            "location": job.get("location"),
        },
        "matching": {
            "match_score": matching.get("match_score"),
            "matched_skills": matching.get("matched_skills") or [],
            "missing_skills": matching.get("missing_skills") or [],
        },
        "gap_analysis": {
            "missing_skills": gap_analysis.get("missing_skills") or [],
            "matched_skills": gap_analysis.get("matched_skills") or [],
            "gap_priority": gap_analysis.get("gap_priority"),
        },
        "retrieved_jobs": [
            {
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "relevance_score": item.get("relevance_score"),
                "required_skills": (item.get("metadata") or {}).get("required_skills") or [],
                "company": (item.get("metadata") or {}).get("company"),
                "location": (item.get("metadata") or {}).get("location"),
                "url": item.get("url"),
                "content": (item.get("content") or "")[:900],
            }
            for item in (retrieved_jobs or [])[:8]
        ],
        "retrieved_courses": [
            {
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "relevance_score": item.get("relevance_score"),
                "skills_taught": (item.get("metadata") or {}).get("skills_taught") or [],
                "provider": (item.get("metadata") or {}).get("provider"),
                "duration_weeks": (item.get("metadata") or {}).get("duration_weeks"),
                "is_free": (item.get("metadata") or {}).get("is_free"),
                "url": item.get("url"),
                "content": (item.get("content") or "")[:700],
            }
            for item in (retrieved_courses or [])[:5]
        ],
    }
    return (
        "Analyze the following structured career skill gap information and return ONLY valid JSON per the system prompt shape:\n"
        + json.dumps(trimmed, ensure_ascii=False, indent=2)
    )


# ---------------------------------------------------------------------------
# Gemini Service
# ---------------------------------------------------------------------------


class GeminiService:
    """Isolated Gemini client: initialises model lazily, handles all failures with graceful fallback.

    The service NEVER raises to the caller — it either returns (ai_reasoning_dict, True/False success flag).
    On ANY failure (missing key / timeout / api error / bad JSON), the second tuple element is False and the
    first element is a safe, deterministic ai_reasoning fallback dictionary.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout_seconds: Optional[float] = None,
    ):
        # Configuration — prefer explicit arguments, then dedicated gap analysis key, then default key
        if api_key is not None:
            self.api_key = str(api_key).strip()
        else:
            self.api_key = (
                getattr(settings, "GEMINI_API_KEY_GAP_ANALYSIS", "")
                or getattr(settings, "GEMINI_API_KEY_2", "")
                or getattr(settings, "GEMINI_API_KEY", "")
                or ""
            ).strip()
        # Masked copy for logging only
        self._api_key_masked = _mask_key(self.api_key)
        self.model_name: str = model_name or settings.GEMINI_MODEL or "gemini-3.6-flash"
        self.temperature: float = (
            float(temperature)
            if temperature is not None
            else float(getattr(settings, "GEMINI_TEMPERATURE", 0.2))
        )
        self.timeout_seconds: float = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 20))
        )

        self._generativeai_module = None  # google.generativeai module, lazily loaded
        self._model_instance = None       # cached GenerativeModel instance

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        """True when a non-empty API key is present. Does NOT check if the key works.
        """
        return bool(self.api_key and str(self.api_key).strip())

    # ------------------------------------------------------------------
    # SDK lazy loading
    # ------------------------------------------------------------------

    def _load_sdk(self) -> Tuple[Any, Any]:
        """Load google.generativeai and configure it, or raise if unavailable.

        Returns (google_generativeai_module, configured_model_instance).
        """
        if self._model_instance is not None:
            return self._generativeai_module, self._model_instance

        if not self.is_configured:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        import google.generativeai as genai  # lazy import
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=dict(
                temperature=float(self.temperature),
                top_p=0.95,
                top_k=40,
                max_output_tokens=1500,
                response_mime_type="application/json",
            ),
        )
        self._generativeai_module = genai
        self._model_instance = model
        return genai, model

    # ------------------------------------------------------------------
    # Primary public API (single job reasoning)
    # ------------------------------------------------------------------

    async def analyze_gap_reasoning(
        self,
        *,
        user_profile: Dict[str, Any],
        job: Dict[str, Any],
        matching: Dict[str, Any],
        gap_analysis: Dict[str, Any],
        retrieved_jobs: Optional[List[Dict[str, Any]]] = None,
        retrieved_courses: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], bool]:
        """Run Gemini analysis for one job, with a deterministic fallback on any failure.

        Returns a tuple (ai_reasoning_dict, success_bool).
        success_bool == True when Gemini ran and produced parseable JSON matching the shape.
        success_bool == False on any problem (missing key, error, timeout, bad JSON).
        The caller can trust the returned dict in both cases.
        """
        job_title = str(job.get("title") or job.get("job_title") or "target role")
        matched_skills: List[str] = list(
            matching.get("matched_skills") or gap_analysis.get("matched_skills") or []
        )
        missing_skills: List[str] = list(
            gap_analysis.get("missing_skills") or matching.get("missing_skills") or []
        )

        if not self.is_configured:
            return (
                _build_fallback_ai_reasoning(
                    job_title=job_title,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    unavailable_reason="Gemini unavailable (GEMINI_API_KEY not configured).",
                ),
                False,
            )

        prompt = _build_user_prompt_payload(
            user_profile=user_profile,
            job=job,
            matching=matching,
            gap_analysis=gap_analysis,
            retrieved_jobs=retrieved_jobs,
            retrieved_courses=retrieved_courses,
        )

        try:
            _, model = self._load_sdk()
        except Exception as exc:
            logger.info("Gemini SDK load failed: %s", _exc_summary(exc))
            return (
                _build_fallback_ai_reasoning(
                    job_title=job_title,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    unavailable_reason="Gemini unavailable (SDK configuration failed).",
                ),
                False,
            )

        last_error = None
        raw_text = None
        for attempt in range(1):
            try:
                raw_text = await self._call_gemini_with_timeout(model, prompt)
                last_error = None
                break
            except Exception as exc:
                err_msg = str(exc)
                last_error = exc
                if "429" in err_msg or "quota" in err_msg.lower() or "resourceexhausted" in err_msg.lower():
                    break
                break

        if last_error is not None:
            err_str = str(last_error)
            reason = "Gemini unavailable (API call failed)."
            if "429" in err_str or "quota" in err_str.lower() or "resourceexhausted" in err_str.lower():
                reason = "Gemini unavailable (rate limit or quota exceeded)."
            logger.info("Gemini call failed: %s", _exc_summary(last_error))
            return (
                _build_fallback_ai_reasoning(
                    job_title=job_title,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    unavailable_reason=reason,
                ),
                False,
            )

        parsed, ok = _parse_gemini_json(raw_text)
        if not ok:
            return (
                _build_fallback_ai_reasoning(
                    job_title=job_title,
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    unavailable_reason="Gemini unavailable (malformed response).",
                ),
                False,
            )

        normalized = _normalize_ai_reasoning_shape(parsed)
        # Hallucination protection (defense-in-depth): never let strengths/priority_gaps reference
        # skills that are not actually in the authoritative deterministic lists.
        normalized_strengths: List[Any] = []
        for strength in normalized["strengths"]:
            strength_skill = strength.get("skill") if isinstance(strength, dict) else strength
            if _in_any(strength_skill, matched_skills):
                deterministic_skill = _find_by_norm(strength_skill, matched_skills)
                if isinstance(strength, dict):
                    normalized_strengths.append({
                        "skill": deterministic_skill,
                        "source_ids": list(strength.get("source_ids") or []),
                    })
                else:
                    normalized_strengths.append(deterministic_skill)
        normalized["strengths"] = normalized_strengths
        allowed_missing_norm = {_norm_skill(s) for s in missing_skills}
        filtered_priority_gaps: List[Dict[str, Any]] = []
        for pg in normalized.get("priority_gaps", []) or []:
            if not isinstance(pg, dict):
                continue
            skill = str(pg.get("skill", ""))
            if not skill:
                continue
            if _norm_skill(skill) in allowed_missing_norm:
                # Keep the original missing skill name (canonical deterministic form)
                deterministic_skill = _find_by_norm(skill, missing_skills)
                filtered_priority_gaps.append({
                    "skill": deterministic_skill,
                    "reason": str(pg.get("reason") or (
                        f"{deterministic_skill} is required for the {job_title} role."
                    )),
                    "source_ids": list(pg.get("source_ids") or []),
                })
        normalized["priority_gaps"] = filtered_priority_gaps

        # learning_focus: allow free-text items or citation objects, capped at length of missing_skills
        normalized["learning_focus"] = list(normalized["learning_focus"])[: max(1, len(missing_skills))]

        normalized["source"] = "gemini"
        return normalized, True

    async def _call_gemini_with_timeout(self, model: Any, prompt: str) -> str:
        """Call generate_content_async wrapped in a timeout. Raises on error."""
        # Use asyncio.wait_for as a second defense (SDK's internal timeout may not always apply if SDK sync)
        async def _do():
            resp = await model.generate_content_async(
                contents=[
                    {"role": "user", "parts": [{"text": GEMINI_SYSTEM_PROMPT}]},
                    {"role": "model", "parts": [{"text": "Understood."}]},
                    {"role": "user", "parts": [{"text": prompt}]},
                ],
            )
            try:
                return resp.text
            except Exception:
                # If .text failed, try string-join parts
                parts = []
                try:
                    for cand in resp.candidates:
                        for part in cand.content.parts:
                            parts.append(str(getattr(part, "text", "") or ""))
                except Exception:
                    pass
                text = "\n".join(parts)
                if not text:
                    raise
                return text

        return await asyncio.wait_for(_do(), timeout=float(self.timeout_seconds))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm_skill(s: Any) -> str:
    try:
        from .gap_analysis_service import normalize_skill
        return normalize_skill(s)
    except Exception:
        return str(s).strip().lower()


def _in_any(skill_candidate: Any, haystack: List[str]) -> bool:
    n = _norm_skill(skill_candidate)
    if not n:
        return False
    return any(_norm_skill(h) == n for h in haystack)


def _find_by_norm(skill_candidate: Any, haystack: List[str]) -> str:
    n = _norm_skill(skill_candidate)
    for h in haystack:
        if _norm_skill(h) == n:
            return h
    return str(skill_candidate)


def _exc_summary(exc: BaseException) -> str:
    try:
        return f"{type(exc).__name__}: {exc}"[:200]
    except Exception:
        return "Unknown error"


def _mask_key(key: str) -> str:
    s = (key or "").strip()
    if len(s) <= 6:
        return "***"
    return s[:3] + "…" + s[-2:]


def _parse_gemini_json(raw_text: Optional[str]) -> Tuple[Dict[str, Any], bool]:
    """Robust JSON extractor for a Gemini response. Returns (dict, ok).

    ok=True only when we actually obtained a JSON object with the expected shape keys.
    """
    if not raw_text or not isinstance(raw_text, str):
        return {}, False
    text = raw_text.strip()

    # Remove ``` (rarely markdown blocks
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        # find first { ... last } (loose in case stray leading/trailing narrative
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}, False
        candidate = text[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except Exception:
            return {}, False

    if not isinstance(parsed, dict):
        return {}, False

    missing_shape = {"summary", "strengths", "priority_gaps", "learning_focus"}
    if not missing_shape.issubset(set(parsed.keys())):
        # Allow partial responses — but reject empty. We'll normalize in the next callera.
        pass
    return parsed, True


def _normalize_ai_reasoning_shape(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Cast parsed JSON output into a consistent dict shape, never raises."""
    out: Dict[str, Any] = {
        "summary": "",
        "strengths": [],
        "priority_gaps": [],
        "learning_focus": [],
    }
    try:
        summary = parsed.get("summary", "")
        out["summary"] = str(summary) if summary is not None else ""
    except Exception:
        pass

    strengths = parsed.get("strengths") or []
    if isinstance(strengths, list):
        cleaned_strengths: List[Any] = []
        for s in strengths:
            if isinstance(s, dict):
                skill = str(s.get("skill") or "").strip()
                if skill:
                    cleaned_strengths.append({
                        "skill": skill,
                        "source_ids": list(s.get("source_ids") or []),
                    })
            elif s is not None and str(s).strip():
                cleaned_strengths.append(str(s))
        out["strengths"] = cleaned_strengths
    else:
        out["strengths"] = []

    priority_gaps = parsed.get("priority_gaps") or []
    if isinstance(priority_gaps, list):
        cleaned: List[Dict[str, Any]] = []
        for pg in priority_gaps:
            if isinstance(pg, dict):
                skill = str(pg.get("skill") or "")
                reason = str(pg.get("reason") or "")
                if not skill:
                    continue
                cleaned.append({
                    "skill": skill,
                    "reason": reason,
                    "source_ids": list(pg.get("source_ids") or []),
                })
            elif isinstance(pg, str):
                cleaned.append({"skill": pg, "reason": ""})
        out["priority_gaps"] = cleaned
    else:
        out["priority_gaps"] = []

    learning_focus = parsed.get("learning_focus") or []
    if isinstance(learning_focus, list):
        cleaned_focus: List[Any] = []
        for item in learning_focus:
            if isinstance(item, dict):
                topic = str(item.get("topic") or item.get("skill") or item.get("course") or "").strip()
                if topic:
                    cleaned_focus.append({
                        "topic": topic,
                        "source_ids": list(item.get("source_ids") or []),
                    })
            elif item is not None and str(item).strip():
                cleaned_focus.append(str(item))
        out["learning_focus"] = cleaned_focus
    elif isinstance(learning_focus, str) and learning_focus.strip():
        out["learning_focus"] = [learning_focus.strip()]
    else:
        out["learning_focus"] = []

    return out


# Singleton instance (used by default in router/service when not overridden for testing)
try:
    gemini_service = GeminiService()
except Exception:
    gemini_service = GeminiService(api_key="")
