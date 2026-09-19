import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"
for path in (BASE_DIR, BACKEND_DIR, BACKEND_DIR / "skill-match-agent"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from orchestration.opportunity_analysis import analyze_opportunities


class CountingMatcher:
    """Test double for the existing matching_service.rank_jobs contract."""

    def __init__(self):
        self.calls = []

    def rank_jobs(self, *, candidate_skills, jobs, top_k=None):
        skills = {skill.casefold() for skill in candidate_skills}
        self.calls.append(set(skills))
        results = []
        for job in jobs:
            required = {skill.casefold() for skill in job.required_skills}
            score = 1.0 if required.issubset(skills) else 0.0
            results.append({
                "match_score": score,
                "missing_skills": [] if score else list(required - skills),
            })
        return results


def make_jobs():
    import importlib

    JobPosting = importlib.import_module("skill-match-agent.schemas").JobPosting

    return [
        JobPosting(job_id="1", title="Python", company="A", location="Pune", required_skills=["Python"]),
        JobPosting(job_id="2", title="Git", company="A", location="Pune", required_skills=["Python", "Git"]),
        JobPosting(job_id="3", title="SQL", company="A", location="Pune", required_skills=["Python", "SQL"]),
        JobPosting(job_id="4", title="Git SQL", company="A", location="Pune", required_skills=["Python", "Git", "SQL"]),
    ]


class TestOpportunityAnalysis(unittest.TestCase):
    def test_current_and_individual_opportunities_are_deterministic(self):
        matcher = CountingMatcher()
        result = analyze_opportunities(
            candidate_skills=["Python", "Python"],
            missing_skills=["Docker", "Git", "SQL", "Git"],
            jobs=make_jobs(),
            matching_service=matcher,
        )

        self.assertEqual(result["current_jobs"], 1)
        opportunities = {item["skill"]: item for item in result["opportunities"]}
        self.assertEqual(opportunities["Git"]["projected_jobs"], 2)
        self.assertEqual(opportunities["Git"]["jobs_unlocked"], 1)
        self.assertEqual(opportunities["Git"]["duration_weeks"], 2.0)
        self.assertEqual(opportunities["Git"]["learning_impact"], 0.5)
        self.assertEqual(opportunities["SQL"]["projected_jobs"], 2)
        self.assertEqual(opportunities["Docker"]["jobs_unlocked"], 0)
        self.assertEqual(
            [item["skill"] for item in result["opportunities"]],
            ["Git", "SQL", "Docker"],
        )

    def test_combinations_and_edge_cases(self):
        matcher = CountingMatcher()
        result = analyze_opportunities(
            candidate_skills=["Python"],
            missing_skills=["Git", "SQL"],
            jobs=make_jobs(),
            matching_service=matcher,
        )

        combo = next(item for item in result["combinations"] if item["skills"] == ["Git", "SQL"])
        self.assertEqual(combo["current_jobs"], 1)
        self.assertEqual(combo["projected_jobs"], 4)
        self.assertEqual(combo["jobs_unlocked"], 3)

        empty = analyze_opportunities(
            candidate_skills=["Python"],
            missing_skills=[],
            jobs=[],
            matching_service=matcher,
        )
        self.assertEqual(empty["current_jobs"], 0)
        self.assertEqual(empty["opportunities"], [])

    def test_end_to_end_matching_gap_and_opportunity_flow(self):
        import importlib

        matching_module = importlib.import_module("skill-match-agent.services.matching_service")
        gap_module = importlib.import_module("gap-analysis-agent.services.gap_analysis_service")
        job_posting = importlib.import_module("skill-match-agent.schemas").JobPosting
        jobs = [
            job_posting(
                job_id="E2E-1",
                title="Python Role",
                company="Example",
                location="Pune",
                required_skills=["Python"],
            ),
            job_posting(
                job_id="E2E-2",
                title="Python Git Role",
                company="Example",
                location="Pune",
                required_skills=["Python", "Git"],
            ),
        ]

        with patch.object(
            matching_module.embedding_service,
            "compute_similarity_matrix",
            side_effect=lambda left, right: np.zeros((len(left), len(right))),
        ):
            matches = matching_module.matching_service.rank_jobs(["Python"], jobs)
            gap_jobs = [
                {
                    "job_id": match.job_id,
                    "job_title": match.title,
                    "required_skills": jobs[index].required_skills,
                    "matched_skills": match.matched_skills,
                    "missing_skills": match.missing_skills,
                    "match_score": match.match_score,
                }
                for index, match in enumerate(matches)
            ]
            analyses = gap_module.analyze_multiple_jobs(
                user_skills=["Python"],
                jobs=gap_jobs,
            )
            opportunities = analyze_opportunities(
                candidate_skills=["Python"],
                missing_skills=[skill for analysis in analyses for skill in analysis["missing_skills"]],
                jobs=jobs,
                matching_service=matching_module.matching_service,
            )

        self.assertEqual(analyses[1]["matched_skills"], ["Python"])
        self.assertEqual(analyses[1]["missing_skills"], ["Git"])
        self.assertEqual(opportunities["current_jobs"], 1)
        self.assertEqual(opportunities["opportunities"][0]["jobs_unlocked"], 1)


if __name__ == "__main__":
    unittest.main()