from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class RagDocument:
    """Searchable document chunk plus source metadata for citation."""

    chunk_id: str
    content: str
    metadata: Dict[str, Any]


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _source_id(item: Mapping[str, Any], id_key: str, prefix: str) -> str:
    value = _clean(item.get(id_key) or item.get("source_id"))
    return value or f"{prefix}-UNKNOWN"


def _chunk_text(source_id: str, source_type: str, content: str, metadata: Dict[str, Any]) -> List[RagDocument]:
    """Keep short docs whole; split very long docs into stable paragraph chunks."""
    text = content.strip()
    if len(text) <= 2400:
        return [
            RagDocument(
                chunk_id=f"{source_id}-CHUNK-01",
                content=text,
                metadata={**metadata, "chunk_id": f"{source_id}-CHUNK-01"},
            )
        ]

    sections = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: List[RagDocument] = []
    buffer: List[str] = []
    buffer_len = 0
    for section in sections:
        if buffer and buffer_len + len(section) > 1800:
            chunk_id = f"{source_id}-CHUNK-{len(chunks) + 1:02d}"
            chunks.append(RagDocument(chunk_id=chunk_id, content="\n\n".join(buffer), metadata={**metadata, "chunk_id": chunk_id}))
            buffer = []
            buffer_len = 0
        buffer.append(section)
        buffer_len += len(section)
    if buffer:
        chunk_id = f"{source_id}-CHUNK-{len(chunks) + 1:02d}"
        chunks.append(RagDocument(chunk_id=chunk_id, content="\n\n".join(buffer), metadata={**metadata, "chunk_id": chunk_id}))
    return chunks


def prepare_job_documents(jobs: Iterable[Mapping[str, Any]]) -> List[RagDocument]:
    documents: List[RagDocument] = []
    for job in jobs or []:
        job_id = _source_id(job, "job_id", "JOB")
        title = _clean(job.get("title") or job.get("job_title"))
        company = _clean(job.get("company"))
        location = _clean(job.get("location"))
        skills = _as_list(job.get("required_skills"))
        description = _clean(job.get("description") or job.get("snippet"))
        url = _clean(job.get("job_url") or job.get("url"))
        source = _clean(job.get("source") or "job_catalog")

        content = "\n".join(
            part
            for part in [
                f"{job_id}",
                f"Title: {title}" if title else "",
                f"Company: {company}" if company else "",
                f"Location: {location}" if location else "",
                "Required Skills:\n" + "\n".join(skills) if skills else "",
                f"Description:\n{description}" if description else "",
            ]
            if part
        )
        metadata = {
            "source_type": "job",
            "source_id": job_id,
            "job_id": job_id,
            "title": title,
            "company": company,
            "location": location,
            "required_skills": skills,
            "url": url,
            "source": source,
        }
        documents.extend(_chunk_text(job_id, "job", content, metadata))
    return documents


def prepare_course_documents(courses: Iterable[Mapping[str, Any]]) -> List[RagDocument]:
    documents: List[RagDocument] = []
    for course in courses or []:
        course_id = _source_id(course, "course_id", "COURSE")
        title = _clean(course.get("title") or course.get("course_name"))
        provider = _clean(course.get("provider"))
        skills = _as_list(course.get("skills_taught") or course.get("skills_covered"))
        duration = course.get("duration_weeks")
        price = course.get("price_inr")
        is_free = bool(course.get("is_free", False))
        difficulty = _clean(course.get("difficulty"))
        description = _clean(course.get("description"))
        url = _clean(course.get("url"))

        content = "\n".join(
            part
            for part in [
                f"{course_id}",
                f"Title: {title}" if title else "",
                f"Provider: {provider}" if provider else "",
                "Skills Taught:\n" + "\n".join(skills) if skills else "",
                f"Duration Weeks: {duration}" if duration is not None else "",
                f"Price INR: {price}" if price is not None else "",
                f"Free: {is_free}",
                f"Difficulty: {difficulty}" if difficulty else "",
                f"Description:\n{description}" if description else "",
            ]
            if part
        )
        metadata = {
            "source_type": "course",
            "source_id": course_id,
            "course_id": course_id,
            "title": title,
            "provider": provider,
            "skills_taught": skills,
            "duration_weeks": duration,
            "price_inr": price,
            "is_free": is_free,
            "difficulty": difficulty,
            "url": url,
        }
        documents.extend(_chunk_text(course_id, "course", content, metadata))
    return documents


def prepare_rag_documents(jobs: Iterable[Mapping[str, Any]], courses: Iterable[Mapping[str, Any]]) -> List[RagDocument]:
    return prepare_job_documents(jobs) + prepare_course_documents(courses)
