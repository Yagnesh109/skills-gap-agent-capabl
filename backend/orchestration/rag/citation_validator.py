from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Mapping, Set


def valid_source_ids(retrieved_sources: Iterable[Mapping[str, Any]]) -> Set[str]:
    return {
        str(source.get("source_id"))
        for source in retrieved_sources or []
        if source.get("source_id")
    }


def filter_source_ids(source_ids: Any, valid_ids: Set[str]) -> List[str]:
    if not isinstance(source_ids, list):
        return []
    filtered: List[str] = []
    for source_id in source_ids:
        sid = str(source_id or "").strip()
        if sid and sid in valid_ids and sid not in filtered:
            filtered.append(sid)
    return filtered


def validate_reasoning_citations(reasoning: Mapping[str, Any], retrieved_sources: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Remove fabricated source IDs from Gemini/fallback reasoning payloads."""
    valid_ids = valid_source_ids(retrieved_sources)
    cleaned: Dict[str, Any] = deepcopy(dict(reasoning or {}))

    cleaned["source_ids"] = filter_source_ids(cleaned.get("source_ids"), valid_ids)

    for key in ("strengths", "priority_gaps", "learning_focus"):
        items = cleaned.get(key)
        if not isinstance(items, list):
            continue
        new_items = []
        for item in items:
            if isinstance(item, dict):
                item_copy = dict(item)
                item_copy["source_ids"] = filter_source_ids(item_copy.get("source_ids"), valid_ids)
                new_items.append(item_copy)
            else:
                new_items.append(item)
        cleaned[key] = new_items

    return cleaned


def attach_default_citations(
    reasoning: Mapping[str, Any],
    *,
    job_sources: Iterable[Mapping[str, Any]],
    course_sources: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Add conservative citations when Gemini is unavailable or omits them."""
    cleaned = deepcopy(dict(reasoning or {}))
    job_ids = [str(item.get("source_id")) for item in job_sources if item.get("source_id")]
    course_ids = [str(item.get("source_id")) for item in course_sources if item.get("source_id")]

    strengths = cleaned.get("strengths")
    if isinstance(strengths, list):
        normalized = []
        for item in strengths:
            if isinstance(item, dict):
                item_copy = dict(item)
                item_copy["source_ids"] = filter_source_ids(item_copy.get("source_ids") or job_ids[:3], set(job_ids))
                normalized.append(item_copy)
            else:
                normalized.append({"skill": str(item), "source_ids": job_ids[:3]})
        cleaned["strengths"] = normalized

    gaps = cleaned.get("priority_gaps")
    if isinstance(gaps, list):
        normalized = []
        for item in gaps:
            if isinstance(item, dict):
                item_copy = dict(item)
                if not item_copy.get("source_ids"):
                    item_copy["source_ids"] = job_ids[:4]
                normalized.append(item_copy)
        cleaned["priority_gaps"] = normalized

    focus = cleaned.get("learning_focus")
    if isinstance(focus, list):
        normalized = []
        for item in focus:
            if isinstance(item, dict):
                item_copy = dict(item)
                if not item_copy.get("source_ids"):
                    item_copy["source_ids"] = course_ids[:2] or job_ids[:2]
                normalized.append(item_copy)
            else:
                normalized.append({"topic": str(item), "source_ids": course_ids[:2] or job_ids[:2]})
        cleaned["learning_focus"] = normalized

    return cleaned
