import logging
from typing import List, Tuple, Optional, Set

try:
    from ..schemas import JobPosting
    from ..data.demo_jobs import get_demo_jobs
    from .jooble_service import jooble_service
    from .job_normalizer import normalize_jooble_jobs
except (ImportError, ValueError):
    from schemas import JobPosting
    from data.demo_jobs import get_demo_jobs
    from services.jooble_service import jooble_service
    from services.job_normalizer import normalize_jooble_jobs

logger = logging.getLogger(__name__)


class JobSourceService:
    """
    Job Source Orchestrator.
    Attempts to retrieve and normalize live jobs from Jooble API.
    Gracefully falls back to the 50 local demo jobs when Jooble is unavailable or unconfigured.
    """

    def __init__(self, jooble_client=None):
        self.jooble_client = jooble_client or jooble_service

    async def get_jobs(
        self,
        keywords: str = "",
        location: str = "",
        candidate_skills: Optional[List[str]] = None,
        interests: Optional[List[str]] = None,
        force_demo: bool = False
    ) -> Tuple[List[JobPosting], str]:
        """
        Retrieves jobs from Jooble (primary) or demo dataset (fallback).
        
        Args:
            keywords: Target keywords or role title
            location: Target geographic location
            candidate_skills: Candidate's skill list for building search query
            interests: Candidate's interest domains for enriching search query
            force_demo: If True, bypasses Jooble and immediately uses demo dataset
            
        Returns:
            Tuple of (List[JobPosting], source_name), where source_name is 'jooble' or 'demo'.
        """
        if force_demo:
            logger.info("force_demo=True requested. Serving local demo jobs.")
            return get_demo_jobs(), "demo"

        # Construct search query keywords
        search_keywords = (keywords or "").strip()

        # Build keyword components: 1) explicit keywords, 2) top skills, 3) top interests
        keyword_parts: List[str] = []
        if search_keywords:
            keyword_parts.append(search_keywords)
        if candidate_skills:
            keyword_parts.extend(candidate_skills[:3])
        if interests:
            keyword_parts.extend(interests[:2])

        # Dedup while preserving order, join into query
        seen_parts: Set[str] = set()       # exact/lowercase full parts already included
        deduped_parts: List[str] = []
        for p in keyword_parts:
            ps = p.strip()
            pl = ps.lower()
            if not ps:
                continue
            # If part was already included as an exact/lowercase match, skip it
            if pl in seen_parts:
                continue
            # For single-word parts, skip if this exact word already appears tokenized in an earlier part
            if " " not in pl:
                already_embedded = False
                for existing in deduped_parts:
                    existing_words = set(existing.lower().split())
                    if pl in existing_words:
                        already_embedded = True
                        break
                if already_embedded:
                    continue
            seen_parts.add(pl)
            deduped_parts.append(ps)

        search_keywords = " ".join(deduped_parts)

        # Final pass: token-level deduplication across the whole query string
        # (e.g. "python developer Python Django" -> "python developer Django")
        if search_keywords:
            final_tokens: List[str] = []
            final_seen: Set[str] = set()
            for tok in search_keywords.split():
                tl = tok.lower()
                if tl not in final_seen:
                    final_seen.add(tl)
                    final_tokens.append(tok)
            search_keywords = " ".join(final_tokens)

        # Attempt Jooble API retrieval if client has key
        if self.jooble_client.has_api_key:
            try:
                raw_jobs = await self.jooble_client.search_jobs(
                    keywords=search_keywords,
                    location=(location or "").strip()
                )

                if raw_jobs:
                    normalized = normalize_jooble_jobs(raw_jobs)
                    if normalized:
                        logger.info(f"Retrieved {len(normalized)} normalized live jobs from Jooble API.")
                        return normalized, "jooble"
                    else:
                        logger.warning("Jooble returned raw jobs, but normalization produced 0 jobs. Using demo fallback.")
                else:
                    logger.info("Jooble returned 0 jobs or request failed. Using demo jobs fallback.")
            except Exception as e:
                logger.warning(f"Error querying Jooble: {type(e).__name__}. Using demo jobs fallback.")
        else:
            logger.info("Jooble API key not set. Using local demo jobs fallback.")

        # Fallback to local demo jobs
        return get_demo_jobs(), "demo"


# Global singleton instance
job_source_service = JobSourceService()
