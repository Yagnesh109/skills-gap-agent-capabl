import sys
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np

# Add backend and skill-match-agent directories to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
AGENT_DIR = BACKEND_DIR / "skill-match-agent"

for p in [str(BASE_DIR), str(BACKEND_DIR), str(AGENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from schemas import JobPosting, UserProfile, SkillMatchRequest
from services.normalizer import normalize_skill, normalize_skills
import services.matching_service as service_module
from services.matching_service import SkillMatchingService, matching_service
from services.embedding_service import DEFAULT_SIMILARITY_THRESHOLD
from data.demo_jobs import get_demo_jobs
from fastapi.testclient import TestClient
from main import app


class TestSkillMatchingAgent(unittest.TestCase):
    """Test suite covering the 6 core scenarios and FastAPI endpoint for Skill Matching Agent."""

    @classmethod
    def setUpClass(cls):
        cls.demo_jobs = get_demo_jobs()
        cls.service = matching_service
        cls.client = TestClient(app)

    def test_demo_jobs_count_and_structure(self):
        """Ensure 50 realistic demo jobs are loaded with proper fields."""
        self.assertEqual(len(self.demo_jobs), 50)
        for job in self.demo_jobs:
            self.assertTrue(job.job_id.startswith("JOB-"))
            self.assertTrue(len(job.title) > 0)
            self.assertTrue(len(job.company) > 0)
            self.assertTrue(len(job.location) > 0)
            self.assertTrue(len(job.required_skills) > 0)
            self.assertTrue(len(job.description) > 0)
            self.assertTrue(job.job_url.startswith("http"))

    def test_1_user_with_several_matching_skills(self):
        """Scenario 1: User with several matching skills (e.g. Python, SQL, Git)."""
        candidate_skills = ["Python", "SQL", "Git"]
        # Find JOB-001 (Python Developer: Python, Django, SQL, Git, REST API)
        job_001 = next(j for j in self.demo_jobs if j.job_id == "JOB-001")
        result = self.service.calculate_job_match(candidate_skills, job_001)

        # 3 out of 5 skills matched exactly -> explicit overlap = 60.0%
        self.assertEqual(result.explicit_score, 60.0)
        self.assertIn("Python", result.matched_skills)
        self.assertIn("SQL", result.matched_skills)
        self.assertIn("Git", result.matched_skills)
        self.assertIn("Django", result.missing_skills)
        self.assertIn("REST API", result.missing_skills)
        self.assertGreater(result.match_score, 40.0)
        self.assertLess(result.match_score, 100.0)

    def test_2_user_with_no_matching_skills(self):
        """Scenario 2: User with no matching skills produces 0.0 match score."""
        candidate_skills = ["Underwater Basket Weaving", "Pottery", "Ancient Latin"]
        job_001 = next(j for j in self.demo_jobs if j.job_id == "JOB-001")
        result = self.service.calculate_job_match(candidate_skills, job_001)

        self.assertEqual(result.explicit_score, 0.0)
        self.assertEqual(len(result.matched_skills), 0)
        self.assertEqual(len(result.missing_skills), len(job_001.required_skills))
        # With zero semantic match to technical skills, score should be 0.0 or near 0
        self.assertLess(result.match_score, 10.0)

    def test_3_user_with_all_required_skills(self):
        """Scenario 3: User with all required skills achieves 100.0 match score."""
        job_001 = next(j for j in self.demo_jobs if j.job_id == "JOB-001")
        candidate_skills = list(job_001.required_skills)
        result = self.service.calculate_job_match(candidate_skills, job_001)

        self.assertEqual(result.explicit_score, 100.0)
        self.assertEqual(result.semantic_score, 100.0)
        self.assertEqual(result.match_score, 100.0)
        self.assertEqual(len(result.missing_skills), 0)
        self.assertEqual(len(result.matched_skills), 5)

    def test_4_skill_aliases_normalization(self):
        """Scenario 4: Skill aliases like React/React.js, Python 3/Python, JS/JavaScript are normalized."""
        # Test normalizer directly
        self.assertEqual(normalize_skill("React.js"), "react")
        self.assertEqual(normalize_skill("ReactJS"), "react")
        self.assertEqual(normalize_skill("React"), "react")
        self.assertEqual(normalize_skill("Python 3"), "python")
        self.assertEqual(normalize_skill("Python"), "python")
        self.assertEqual(normalize_skill("JS"), "javascript")
        self.assertEqual(normalize_skill("JavaScript"), "javascript")
        self.assertEqual(normalize_skill("Node.js"), "nodejs")
        self.assertEqual(normalize_skill("NodeJS"), "nodejs")
        self.assertEqual(normalize_skill("SQL"), "sql")

        # Test within matching engine: user has 'React.js' and 'JS', job requires 'React' and 'JavaScript'
        job_006 = next(j for j in self.demo_jobs if j.job_id == "JOB-006")  # React Developer
        candidate_skills = ["React.js", "JS", "Redux"]
        result = self.service.calculate_job_match(candidate_skills, job_006)

        # React and JavaScript should be matched through alias normalization
        matched_lower = [s.lower() for s in result.matched_skills]
        self.assertIn("react", matched_lower)
        self.assertIn("javascript", matched_lower)
        self.assertIn("redux", matched_lower)

    def test_4b_distinct_technology_aliases_do_not_collapse(self):
        self.assertNotEqual(normalize_skill("Git"), normalize_skill("GitHub"))
        self.assertNotEqual(normalize_skill("Git"), normalize_skill("GitLab"))
        self.assertNotEqual(normalize_skill("SQL"), normalize_skill("PostgreSQL"))
        self.assertNotEqual(normalize_skill("SQL"), normalize_skill("MySQL"))
        self.assertNotEqual(normalize_skill("Python"), normalize_skill("Django"))

    def test_4c_exact_and_missing_skills_are_deterministic(self):
        job = JobPosting(
            job_id="TEST-001",
            title="Python Role",
            company="Example",
            location="Pune",
            required_skills=["Python", "SQL"],
        )

        with patch.object(service_module.embedding_service, "encode") as encode, patch.object(
            service_module.embedding_service,
            "compute_similarity_matrix",
            return_value=np.array([[0.1]], dtype=np.float32),
        ):
            encode.side_effect = [
                np.ones((1, 384), dtype=np.float32),
                np.ones((1, 384), dtype=np.float32),
            ]
            result = self.service.calculate_job_match([" PYTHON "], job)

        self.assertEqual(result.matched_skills, ["Python"])
        self.assertEqual(result.missing_skills, ["SQL"])
        self.assertEqual(result.semantic_matched_skills, [])

    def test_4d_below_threshold_semantics_do_not_add_score(self):
        job = JobPosting(
            job_id="TEST-002",
            title="Python Role",
            company="Example",
            location="Pune",
            required_skills=["Python", "Django"],
        )
        service = SkillMatchingService(similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD)
        low_similarity = np.array([[0.1]], dtype=np.float32)

        with patch.object(service_module.embedding_service, "encode") as encode, patch.object(
            service_module.embedding_service,
            "compute_similarity_matrix",
            return_value=low_similarity,
        ):
            encode.side_effect = [
                np.ones((1, 384), dtype=np.float32),
                np.ones((1, 384), dtype=np.float32),
            ]
            result = service.calculate_job_match(["Python"], job)

        self.assertEqual(result.matched_skills, ["Python"])
        self.assertEqual(result.missing_skills, ["Django"])
        self.assertEqual(result.semantic_matched_skills, [])
        self.assertEqual(result.semantic_score, 50.0)
        self.assertEqual(result.match_score, 50.0)

    def test_4e_accepted_semantic_match_is_reported(self):
        job = JobPosting(
            job_id="TEST-003",
            title="Python Web Role",
            company="Example",
            location="Pune",
            required_skills=["Python", "Django"],
        )
        service = SkillMatchingService(similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD)
        high_similarity = np.array([[0.9]], dtype=np.float32)

        with patch.object(service_module.embedding_service, "encode") as encode, patch.object(
            service_module.embedding_service,
            "compute_similarity_matrix",
            return_value=high_similarity,
        ):
            encode.side_effect = [
                np.ones((1, 384), dtype=np.float32),
                np.ones((1, 384), dtype=np.float32),
            ]
            result = service.calculate_job_match(["Python"], job)

        self.assertEqual(result.matched_skills, ["Python", "Django"])
        self.assertEqual(result.missing_skills, [])
        self.assertEqual(result.semantic_matched_skills, ["Django"])


    def test_5_multiple_jobs_ranked_correctly(self):
        """Scenario 5: Multiple jobs ranked in strictly descending order of match_score."""
        candidate_skills = ["Python", "FastAPI", "Docker", "PostgreSQL"]
        ranked = self.service.rank_jobs(candidate_skills, self.demo_jobs, top_k=10)

        self.assertEqual(len(ranked), 10)
        # Verify scores are sorted descending
        for i in range(len(ranked) - 1):
            self.assertGreaterEqual(
                ranked[i].match_score,
                ranked[i + 1].match_score,
                f"Job {ranked[i].job_id} ({ranked[i].match_score}) not >= {ranked[i+1].job_id} ({ranked[i+1].match_score})"
            )

        # JOB-002 requires ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis", "Microservices"]
        # It should rank very near the top for this candidate
        top_job_ids = [r.job_id for r in ranked[:3]]
        self.assertIn("JOB-002", top_job_ids)

    def test_6_match_score_bounds(self):
        """Scenario 6: Match score must strictly remain between 0.0 and 100.0 across random inputs."""
        test_skill_sets = [
            [],
            ["Python"],
            ["React", "Node.js", "MongoDB"],
            ["RandomNonExistentSkill12345"],
            ["Python", "Java", "C++", "JavaScript", "SQL", "Docker", "AWS", "Kubernetes", "Git"]
        ]

        for skills in test_skill_sets:
            results = self.service.rank_jobs(skills, self.demo_jobs)
            for res in results:
                self.assertGreaterEqual(res.match_score, 0.0)
                self.assertLessEqual(res.match_score, 100.0)
                self.assertGreaterEqual(res.explicit_score, 0.0)
                self.assertLessEqual(res.explicit_score, 100.0)
                self.assertGreaterEqual(res.semantic_score, 0.0)
                self.assertLessEqual(res.semantic_score, 100.0)

    def test_7_fastapi_endpoint_post_skill_match(self):
        """Scenario 7: Test FastAPI POST /api/skill-match with UserProfile payload."""
        payload = {
            "skills": ["Python", "Django", "SQL", "Git"],
            "target_role": "Python Developer",
            "location": "Pune"
        }
        response = self.client.post("/api/skill-match", json=payload)
        self.assertEqual(response.status_code, 200)

        results = response.json()
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 50)

        top_match = results[0]
        self.assertIn("job_id", top_match)
        self.assertIn("title", top_match)
        self.assertIn("match_score", top_match)
        self.assertIn("matched_skills", top_match)
        self.assertIn("missing_skills", top_match)

        # For Python/Django/SQL/Git, JOB-001 should be #1 with high score
        self.assertEqual(top_match["job_id"], "JOB-001")
        self.assertGreaterEqual(top_match["match_score"], 80.0)

    def test_8_fastapi_endpoint_with_skill_match_request_top_k(self):
        """Scenario 8: Test FastAPI POST /api/skill-match with SkillMatchRequest and top_k filter."""
        payload = {
            "candidate_skills": ["React", "JavaScript", "TypeScript"],
            "top_k": 5
        }
        response = self.client.post("/api/skill-match", json=payload)
        self.assertEqual(response.status_code, 200)

        results = response.json()
        self.assertEqual(len(results), 5)
        # All 5 results must have valid match_score
        for r in results:
            self.assertIn("match_score", r)
            self.assertGreaterEqual(r["match_score"], 0.0)

    def test_9_fastapi_demo_jobs_endpoint(self):
        """Scenario 9: Test GET /api/skill-match/demo-jobs."""
        response = self.client.get("/api/skill-match/demo-jobs")
        self.assertEqual(response.status_code, 200)
        jobs = response.json()
        self.assertEqual(len(jobs), 50)


if __name__ == "__main__":
    unittest.main()
