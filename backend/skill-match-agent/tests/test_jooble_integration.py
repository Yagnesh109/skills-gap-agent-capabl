import sys
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
import httpx

# Add paths to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
AGENT_DIR = BACKEND_DIR / "skill-match-agent"

for p in [str(BASE_DIR), str(BACKEND_DIR), str(AGENT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from config import settings
from schemas import JobPosting, UserProfile, SkillMatchRequest, JobMatchResult
from services.skill_extractor import extract_skills_from_text, clean_html_text
from services.job_normalizer import normalize_jooble_job, normalize_jooble_jobs
from services.jooble_service import JoobleService, jooble_service
from services.job_source_service import JobSourceService, job_source_service
from services.matching_service import matching_service
from data.demo_jobs import get_demo_jobs
from fastapi.testclient import TestClient
from main import app


MOCK_RAW_JOOBLE_JOBS = [
    {
        "id": "987654321",
        "title": "Senior Python Developer",
        "company": "Tech Innovations Pvt Ltd",
        "location": "Pune",
        "snippet": "We are seeking a <b>Python Developer</b> with experience in <i>Django</i>, <b>PostgreSQL</b>, and Docker.",
        "link": "https://jooble.org/desc/987654321",
        "salary": "15-25 LPA",
        "type": "Full-time"
    },
    {
        "id": "123456789",
        "title": "React Frontend Engineer",
        "company": "CloudWave Solutions",
        "location": "Bengaluru",
        "snippet": "Looking for React.js, TypeScript, and Tailwind CSS developer for our SaaS product.",
        "link": "https://jooble.org/desc/123456789",
        "salary": "12-20 LPA",
        "type": "Full-time"
    }
]


class TestJoobleIntegration(unittest.TestCase):
    """Test suite covering Jooble API integration, normalization, error handling, and demo fallbacks."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_1_jooble_config_loaded(self):
        """Test 1: Jooble API configuration is loaded correctly from settings without crash."""
        self.assertTrue(hasattr(settings, "JOOBLE_API_KEY"))
        self.assertTrue(hasattr(settings, "JOOBLE_API_BASE_URL"))
        self.assertEqual(settings.JOOBLE_API_BASE_URL, "https://jooble.org/api")

    def test_2_api_key_never_exposed(self):
        """Test 2: API key is never exposed in output representations or health checks."""
        health_res = self.client.get("/api/skill-match/health").json()
        self.assertNotIn("JOOBLE_API_KEY", health_res)
        if settings.JOOBLE_API_KEY:
            self.assertNotIn(settings.JOOBLE_API_KEY, str(health_res))

        # Check jooble_service string representation
        svc = JoobleService(api_key="secret_test_key_12345")
        self.assertNotIn("secret_test_key_12345", str(svc.__dict__.get("masked", "")))

    def test_3_jooble_response_converted_to_jobposting(self):
        """Test 3: Jooble raw item is properly converted to standard JobPosting schema."""
        raw_item = MOCK_RAW_JOOBLE_JOBS[0]
        job = normalize_jooble_job(raw_item)

        self.assertIsInstance(job, JobPosting)
        self.assertEqual(job.job_id, "JOOBLE-987654321")
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.company, "Tech Innovations Pvt Ltd")
        self.assertEqual(job.location, "Pune")
        self.assertEqual(job.job_url, "https://jooble.org/desc/987654321")
        self.assertEqual(job.source, "jooble")
        # Skills extracted from HTML snippet: Python, Django, PostgreSQL, Docker
        self.assertIn("Python", job.required_skills)
        self.assertIn("Django", job.required_skills)
        self.assertIn("PostgreSQL", job.required_skills)
        self.assertIn("Docker", job.required_skills)

    def test_4_skill_extraction_accuracy(self):
        """Test 4: Deterministic skill extraction handles punctuation, aliases, and HTML."""
        text = "Require <b>React.js</b>, JS, Python 3, Node.js, and CI/CD experience."
        skills = extract_skills_from_text(text)
        self.assertIn("React", skills)
        self.assertIn("JavaScript", skills)
        self.assertIn("Python", skills)
        self.assertIn("Node.js", skills)
        self.assertIn("CI/CD", skills)

    def test_5_jooble_jobs_passed_to_matching_service(self):
        """Test 5: Normalized Jooble jobs are accepted by matching_service without changes."""
        jobs = normalize_jooble_jobs(MOCK_RAW_JOOBLE_JOBS)
        candidate_skills = ["Python", "Django", "PostgreSQL"]

        results = matching_service.rank_jobs(candidate_skills, jobs)
        self.assertEqual(len(results), 2)
        top_result = results[0]
        self.assertEqual(top_result.job_id, "JOOBLE-987654321")
        self.assertGreater(top_result.match_score, 60.0)
        self.assertIn("Python", top_result.matched_skills)

    @patch.object(JoobleService, "search_jobs", new_callable=AsyncMock)
    def test_6_missing_api_key_demo_fallback(self, mock_search):
        """Test 6: When API key is empty, JobSourceService immediately falls back to demo jobs."""
        service_no_key = JobSourceService(jooble_client=JoobleService(api_key=""))
        import asyncio
        jobs, source = asyncio.run(service_no_key.get_jobs(keywords="Python"))

        self.assertEqual(source, "demo")
        self.assertEqual(len(jobs), 50)
        mock_search.assert_not_called()

    @patch.object(JoobleService, "search_jobs", new_callable=AsyncMock)
    def test_7_jooble_api_failure_demo_fallback(self, mock_search):
        """Test 7: When Jooble returns an error or empty list, falls back to demo jobs safely."""
        mock_search.return_value = []
        svc = JobSourceService(jooble_client=JoobleService(api_key="dummy_key"))
        import asyncio
        jobs, source = asyncio.run(svc.get_jobs(keywords="Python"))

        self.assertEqual(source, "demo")
        self.assertEqual(len(jobs), 50)

    @patch.object(JoobleService, "search_jobs", new_callable=AsyncMock)
    def test_8_jooble_timeout_demo_fallback(self, mock_search):
        """Test 8: When Jooble request raises an exception (timeout), falls back to demo jobs."""
        mock_search.side_effect = Exception("Connection timed out")
        svc = JobSourceService(jooble_client=JoobleService(api_key="dummy_key"))
        import asyncio
        jobs, source = asyncio.run(svc.get_jobs(keywords="Python"))

        self.assertEqual(source, "demo")
        self.assertEqual(len(jobs), 50)

    def test_9_successful_jooble_response_used_in_endpoint(self):
        """Test 9: Successful Jooble response yields source='jooble' and X-Job-Source header."""
        router_module = sys.modules.get("skill-match-agent.router")
        target_client = router_module.job_source_service.jooble_client if router_module else job_source_service.jooble_client

        original_key = target_client._api_key
        target_client._api_key = "test_valid_key"

        with patch.object(target_client, "search_jobs", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = MOCK_RAW_JOOBLE_JOBS
            try:
                payload = {"skills": ["Python", "Django", "PostgreSQL"]}
                response = self.client.post("/api/skill-match", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("X-Job-Source"), "jooble")

                results = response.json()
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0]["source"], "jooble")
                self.assertTrue(results[0]["job_id"].startswith("JOOBLE-"))
            finally:
                target_client._api_key = original_key

    def test_10_existing_demo_jobs_endpoint_still_works(self):
        """Test 10: GET /api/skill-match/demo-jobs continues to return all 50 demo jobs."""
        response = self.client.get("/api/skill-match/demo-jobs")
        self.assertEqual(response.status_code, 200)
        jobs = response.json()
        self.assertEqual(len(jobs), 50)
        self.assertEqual(jobs[0]["source"], "demo")

    def test_11_get_jobs_endpoint_independent_check(self):
        """Test 11: GET /api/skill-match/jobs returns jobs with force_demo=True."""
        response = self.client.get("/api/skill-match/jobs?force_demo=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Job-Source"), "demo")
        jobs = response.json()
        self.assertEqual(len(jobs), 50)

    def test_12_match_score_bounds_with_jooble_jobs(self):
        """Test 12: Match scores remain strictly within [0.0, 100.0] on Jooble jobs."""
        jobs = normalize_jooble_jobs(MOCK_RAW_JOOBLE_JOBS)
        results = matching_service.rank_jobs(["Python", "React"], jobs)
        for r in results:
            self.assertGreaterEqual(r.match_score, 0.0)
            self.assertLessEqual(r.match_score, 100.0)
            self.assertGreaterEqual(r.explicit_score, 0.0)
            self.assertLessEqual(r.explicit_score, 100.0)
            self.assertGreaterEqual(r.semantic_score, 0.0)
            self.assertLessEqual(r.semantic_score, 100.0)

    @patch("httpx.AsyncClient")
    def test_13_jooble_rate_limit_429_fallback(self, MockAsyncClient):
        """Test 13: Jooble returns HTTP 429 (Rate Limit) → empty result → demo fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockAsyncClient.return_value = mock_client_instance

        svc = JoobleService(api_key="rate_limit_test_key")
        import asyncio
        jobs = asyncio.run(svc.search_jobs(keywords="Python", location="Pune"))

        self.assertEqual(jobs, [], "Rate-limited response must yield empty list for fallback")

    @patch("httpx.AsyncClient")
    def test_14_jooble_http_500_error_fallback(self, MockAsyncClient):
        """Test 14: Jooble returns HTTP 500 (Server Error) → empty result → demo fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal Server Error"}

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockAsyncClient.return_value = mock_client_instance

        svc = JoobleService(api_key="error500_test_key")
        import asyncio
        jobs = asyncio.run(svc.search_jobs(keywords="Python"))

        self.assertEqual(jobs, [], "HTTP 500 response must yield empty list for fallback")

    @patch("httpx.AsyncClient")
    def test_15_jooble_malformed_response_no_jobs_key(self, MockAsyncClient):
        """Test 15: Jooble returns valid JSON but missing 'jobs' key → empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "totalCount": 42}

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockAsyncClient.return_value = mock_client_instance

        svc = JoobleService(api_key="malformed_test_key")
        import asyncio
        jobs = asyncio.run(svc.search_jobs(keywords="Python"))

        self.assertEqual(jobs, [], "Malformed response (no jobs key) must yield empty list")

    @patch("httpx.AsyncClient")
    def test_16_jooble_jobs_not_a_list_fallback(self, MockAsyncClient):
        """Test 16: Jooble 'jobs' field is not a list type → empty list for fallback."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": "should_be_a_list_not_string"}

        mock_client_instance = MagicMock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        MockAsyncClient.return_value = mock_client_instance

        svc = JoobleService(api_key="nonlist_test_key")
        import asyncio
        jobs = asyncio.run(svc.search_jobs(keywords="React"))

        self.assertEqual(jobs, [], "Non-list 'jobs' field must yield empty list")

    def test_17_interests_and_education_in_user_profile_schema(self):
        """Test 17: UserProfile schema supports education and interests per Step 2 contract."""
        profile = UserProfile(
            education="B.Tech Computer Science",
            skills=["Python", "SQL", "React", "Java"],
            location="Pune",
            interests=["AI", "Web Development"]
        )
        self.assertEqual(profile.education, "B.Tech Computer Science")
        self.assertIn("AI", profile.interests)
        self.assertIn("Web Development", profile.interests)
        self.assertEqual(profile.location, "Pune")

    def test_18_job_source_uses_interests_in_keywords(self):
        """Test 18: JobSourceService enriches search keywords with user interests and skills."""
        import asyncio

        class CaptureJoobleClient:
            has_api_key = True

            async def search_jobs(self, keywords, location="", page=1):
                # Capture and expose the built query
                self.captured_keywords = keywords
                return []

        capture_client = CaptureJoobleClient()
        svc = JobSourceService(jooble_client=capture_client)
        asyncio.run(svc.get_jobs(
            keywords="Python Developer",
            location="Pune",
            candidate_skills=["Python", "Django", "SQL"],
            interests=["AI", "Machine Learning"]
        ))

        kw = capture_client.captured_keywords.lower()
        # All 4 components should appear in the combined keyword query
        self.assertIn("python developer", kw)
        self.assertIn("python", kw)
        self.assertIn("django", kw)
        self.assertIn("ai", kw)
        self.assertIn("machine learning", kw)

    def test_19_deduplication_of_keywords(self):
        """Test 19: Keyword builder deduplicates overlapping terms case-insensitively."""
        import asyncio

        class CaptureJoobleClient:
            has_api_key = True

            async def search_jobs(self, keywords, location="", page=1):
                self.captured_keywords = keywords
                return []

        capture_client = CaptureJoobleClient()
        svc = JobSourceService(jooble_client=capture_client)
        # Same word repeated across keywords, skills, and interests
        asyncio.run(svc.get_jobs(
            keywords="python developer Python",
            candidate_skills=["Python", "Django", "PYTHON"],
            interests=["Django", "Python"]
        ))

        kw_parts = capture_client.captured_keywords.split()
        python_count = sum(1 for w in kw_parts if w.lower() == "python")
        django_count = sum(1 for w in kw_parts if w.lower() == "django")
        self.assertEqual(python_count, 1, "'Python' should be deduplicated to a single occurrence")
        self.assertEqual(django_count, 1, "'Django' should be deduplicated to a single occurrence")

    def test_20_health_endpoint_confirms_jooble_status(self):
        """Test 20: /health endpoint reports jooble_configured boolean without exposing the key."""
        res = self.client.get("/api/skill-match/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("jooble_configured", body)
        self.assertIsInstance(body["jooble_configured"], bool)
        self.assertIn("demo_jobs_count", body)
        self.assertEqual(body["demo_jobs_count"], 50)
        self.assertIn("embedding_model", body)
        self.assertEqual(body["embedding_model"], "all-MiniLM-L6-v2")


if __name__ == "__main__":
    unittest.main()
