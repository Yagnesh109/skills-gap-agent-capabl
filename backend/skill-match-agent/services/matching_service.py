from typing import List, Dict, Any, Tuple, Optional
import numpy as np

try:
    from ..schemas import JobPosting, JobMatchResult, UserProfile
    from .normalizer import normalize_skill, normalize_skills, build_skill_map
    from .embedding_service import embedding_service, DEFAULT_SIMILARITY_THRESHOLD
except (ImportError, ValueError):
    from schemas import JobPosting, JobMatchResult, UserProfile
    from services.normalizer import normalize_skill, normalize_skills, build_skill_map
    from services.embedding_service import embedding_service, DEFAULT_SIMILARITY_THRESHOLD

# Configurable Scoring Weights
DEFAULT_EXACT_WEIGHT: float = 0.70
DEFAULT_SEMANTIC_WEIGHT: float = 0.30


class SkillMatchingService:
    """
    Skill Matching Engine.
    Combines rule-based exact skill overlap and Sentence Transformers semantic similarity
    to rank job postings for candidate skill profiles.
    """

    def __init__(
        self,
        exact_weight: float = DEFAULT_EXACT_WEIGHT,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ):
        # Weights must sum to 1.0 for normalized 0-100 scaling
        self.exact_weight = exact_weight
        self.semantic_weight = semantic_weight
        self.similarity_threshold = similarity_threshold

    def calculate_job_match(
        self,
        candidate_skills: List[str],
        job: JobPosting,
        candidate_embeddings: Optional[np.ndarray] = None
    ) -> JobMatchResult:
        """
        Calculates the match score between candidate skills and a single job posting.
        Returns a JobMatchResult with matched/missing skills and scores.
        """
        required_skills = job.required_skills or []
        if not required_skills:
            # If job has no requirements, 100% match by default
            return JobMatchResult(
                job_id=job.job_id,
                title=job.title,
                company=job.company,
                location=job.location,
                snippet=job.description,
                url=job.job_url,
                match_score=100.0,
                explicit_score=100.0,
                semantic_score=100.0,
                matched_skills=[],
                missing_skills=[],
                unmatched_skills=[]
            )

        if not candidate_skills:
            # Candidate has provided no skills -> 0% match
            return JobMatchResult(
                job_id=job.job_id,
                title=job.title,
                company=job.company,
                location=job.location,
                snippet=job.description,
                url=job.job_url,
                match_score=0.0,
                explicit_score=0.0,
                semantic_score=0.0,
                matched_skills=[],
                missing_skills=list(required_skills),
                unmatched_skills=list(required_skills)
            )

        # 1. Exact Skill Overlap (Normalized)
        cand_norm_map = build_skill_map(candidate_skills)  # {norm: original}
        job_norm_map = build_skill_map(required_skills)    # {norm: original}

        cand_norm_set = set(cand_norm_map.keys())
        job_norm_set = set(job_norm_map.keys())

        # Preserve the job's declared order so output and scoring are repeatable.
        exact_matched_norms = [
            norm for norm in job_norm_map if norm in cand_norm_set
        ]
        unmatched_norms = [
            norm for norm in job_norm_map if norm not in cand_norm_set
        ]

        matched_skills_display = [job_norm_map[norm] for norm in exact_matched_norms]
        missing_skills_display = []
        semantic_matched_skills = []

        total_required = len(job_norm_set)
        exact_matched_count = len(exact_matched_norms)

        # 2. Semantic Similarity Matching
        # Compute embeddings for unmatched skills vs candidate skills
        similarity_scores_per_req: List[float] = [1.0] * exact_matched_count

        if unmatched_norms and candidate_skills:
            if candidate_embeddings is None:
                candidate_embeddings = embedding_service.encode(candidate_skills)

            unmatched_displays = [job_norm_map[norm] for norm in unmatched_norms]
            unmatched_embeddings = embedding_service.encode(unmatched_displays)

            sim_matrix = embedding_service.compute_similarity_matrix(
                unmatched_embeddings,
                candidate_embeddings
            )

            for idx, req_norm in enumerate(unmatched_norms):
                orig_name = job_norm_map[req_norm]
                max_sim = float(np.max(sim_matrix[idx])) if sim_matrix.size > 0 else 0.0

                if max_sim >= self.similarity_threshold:
                    # Meets semantic equivalence threshold (e.g. 'React' vs 'React.js development')
                    matched_skills_display.append(orig_name)
                    semantic_matched_skills.append(orig_name)
                    similarity_scores_per_req.append(max_sim)
                else:
                    missing_skills_display.append(orig_name)
                    # Below-threshold similarity is not a partial match.
                    similarity_scores_per_req.append(0.0)
        else:
            for req_norm in unmatched_norms:
                missing_skills_display.append(job_norm_map[req_norm])
                similarity_scores_per_req.append(0.0)

        # 3. Score Calculations
        # Explicit Skill Overlap Score (0 - 100)
        explicit_score = (exact_matched_count / total_required) * 100.0

        # Semantic Similarity Score (0 - 100)
        semantic_score = (sum(similarity_scores_per_req) / total_required) * 100.0

        # Combined Final Score: 70% Explicit + 30% Semantic
        raw_final_score = (
            (self.exact_weight * explicit_score) +
            (self.semantic_weight * semantic_score)
        )

        # Ensure bounds [0.0, 100.0] and round to 2 decimals
        final_score = round(max(0.0, min(100.0, raw_final_score)), 2)
        explicit_score = round(max(0.0, min(100.0, explicit_score)), 2)
        semantic_score = round(max(0.0, min(100.0, semantic_score)), 2)

        return JobMatchResult(
            job_id=job.job_id,
            title=job.title,
            company=job.company,
            location=job.location,
            snippet=job.description,
            url=job.job_url,
            match_score=final_score,
            explicit_score=explicit_score,
            semantic_score=semantic_score,
            matched_skills=matched_skills_display,
            missing_skills=missing_skills_display,
            unmatched_skills=missing_skills_display,
            semantic_matched_skills=semantic_matched_skills,
        )

    def rank_jobs(
        self,
        candidate_skills: List[str],
        jobs: List[JobPosting],
        top_k: Optional[int] = None
    ) -> List[JobMatchResult]:
        """
        Computes match scores for all candidate jobs and returns them ranked in descending order.
        """
        if not jobs:
            return []

        # Precompute candidate embeddings once for batch efficiency
        candidate_embeddings = (
            embedding_service.encode(candidate_skills)
            if candidate_skills else None
        )

        results = [
            self.calculate_job_match(candidate_skills, job, candidate_embeddings)
            for job in jobs
        ]

        # Sort in descending order of match_score
        ranked = sorted(results, key=lambda r: r.match_score, reverse=True)

        if top_k is not None and top_k > 0:
            return ranked[:top_k]
        return ranked


# Global service instance
matching_service = SkillMatchingService()
