from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .document_preparation import prepare_rag_documents
from .vector_store import FaissVectorStore

logger = logging.getLogger(__name__)

DEFAULT_TOP_K_JOBS = 8
DEFAULT_TOP_K_COURSES = 5

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_SKILL_MATCH_DIR = _BACKEND_DIR / "skill-match-agent"
for _path in (str(_BACKEND_DIR), str(_SKILL_MATCH_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _load_embedding_service():
    try:
        module = importlib.import_module("services.embedding_service")
        return module.embedding_service
    except Exception:
        module = importlib.import_module("skill-match-agent.services.embedding_service")
        return module.embedding_service


class RagRetriever:
    """Builds a local RAG index over current jobs and courses and retrieves evidence."""

    def __init__(self, *, top_k_jobs: int = DEFAULT_TOP_K_JOBS, top_k_courses: int = DEFAULT_TOP_K_COURSES) -> None:
        self.top_k_jobs = top_k_jobs
        self.top_k_courses = top_k_courses
        self.vector_store = FaissVectorStore(_load_embedding_service())

    def retrieve(
        self,
        *,
        user_profile: Mapping[str, Any],
        jobs: Iterable[Mapping[str, Any]],
        courses: Iterable[Mapping[str, Any]],
        missing_skills: Optional[Iterable[str]] = None,
        top_k_jobs: Optional[int] = None,
        top_k_courses: Optional[int] = None,
    ) -> Dict[str, Any]:
        documents = prepare_rag_documents(jobs, courses)
        rag_available = self.vector_store.build_if_needed(documents)
        query = build_retrieval_query(user_profile=user_profile, missing_skills=missing_skills)

        if not rag_available:
            return {
                "retrieved_jobs": [],
                "retrieved_courses": [],
                "retrieved_sources": [],
                "rag_available": False,
                "rag_query": query,
                "rag_index": {"documents": len(documents), "using_faiss": False},
            }

        try:
            retrieved_jobs = self.vector_store.search(
                query,
                top_k=top_k_jobs or self.top_k_jobs,
                source_type="job",
            )
            retrieved_courses = self.vector_store.search(
                query,
                top_k=top_k_courses or self.top_k_courses,
                source_type="course",
            )
        except Exception as exc:
            logger.info("RAG retrieval failed: %s", type(exc).__name__)
            return {
                "retrieved_jobs": [],
                "retrieved_courses": [],
                "retrieved_sources": [],
                "rag_available": False,
                "rag_query": query,
                "rag_index": {"documents": len(documents), "using_faiss": self.vector_store.using_faiss},
            }

        retrieved_sources = retrieved_jobs + retrieved_courses
        return {
            "retrieved_jobs": retrieved_jobs,
            "retrieved_courses": retrieved_courses,
            "retrieved_sources": retrieved_sources,
            "rag_available": bool(retrieved_sources),
            "rag_query": query,
            "rag_index": {
                "documents": len(documents),
                "using_faiss": self.vector_store.using_faiss,
                "top_k_jobs": top_k_jobs or self.top_k_jobs,
                "top_k_courses": top_k_courses or self.top_k_courses,
            },
        }


def _list_text(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def build_retrieval_query(*, user_profile: Mapping[str, Any], missing_skills: Optional[Iterable[str]] = None) -> str:
    profile = dict(user_profile or {})
    skills = _list_text(profile.get("skills"))
    interests = _list_text(profile.get("interests"))
    target_role = str(profile.get("target_role") or "").strip()
    location = str(profile.get("location") or "").strip()
    missing = [str(skill).strip() for skill in (missing_skills or []) if str(skill).strip()]

    parts: List[str] = []
    if skills:
        parts.append("Current skills: " + " ".join(skills))
    if target_role:
        parts.append("Target: " + target_role)
    if missing:
        parts.append("Missing: " + " ".join(missing))
    if interests:
        parts.append("Interests: " + " ".join(interests))
    if location:
        parts.append("Location: " + location)
    return "\n".join(parts) or "software developer skills jobs courses"


rag_retriever = RagRetriever()
