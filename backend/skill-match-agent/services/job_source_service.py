import logging
from typing import List, Tuple, Optional

try:
    from ..schemas import JobPosting
    from ..data.demo_jobs import get_demo_jobs
    from .jooble_service import jooble_service
    from .job_normalizer import normalize_demo_jobs
except (ImportError, ValueError):
    from schemas import JobPosting
    from data.demo_jobs import get_demo_jobs
    from services.jooble_service import jooble_service
    from services.job_normalizer import normalize_demo_jobs

logger = logging.getLogger(__name__)


class JobSourceService:
    """
    Job Source Orchestrator.
    Retrieves and normalizes the 50 local demo jobs.

    Jooble integration is intentionally bypassed so PathWise demo runs are
    deterministic and driven only by the curated local job dataset.
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
        Retrieves jobs from the local demo dataset only.
        
        Args:
            keywords: Target keywords or role title
            location: Target geographic location
            candidate_skills: Candidate's skill list for building search query
            interests: Candidate's interest domains for enriching search query
            force_demo: Preserved for compatibility; demo data is always used.
            
        Returns:
            Tuple of (List[JobPosting], source_name), where source_name is always 'demo'.
        """
        logger.info("Serving local demo jobs. Jooble lookup is disabled for deterministic demo runs.")
        return normalize_demo_jobs(get_demo_jobs()), "demo"


# Global singleton instance
job_source_service = JobSourceService()
