import sys
import unittest
from pathlib import Path

# Add project paths so the test runner can import modules with hyphens
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend"
GAP_AGENT_DIR = BACKEND_DIR / "gap-analysis-agent"
SKILL_AGENT_DIR = BACKEND_DIR / "skill-match-agent"

for _p in [str(BASE_DIR), str(BACKEND_DIR), str(GAP_AGENT_DIR), str(SKILL_AGENT_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient
from main import app

try:
    from services.gap_analysis_service import (
        normalize_skill,
        dedupe_skill_list,
        analyze_single_job_gap,
        analyze_multiple_jobs,
        compute_metadata,
        gap_analysis_service,
    )
    from services.analyzer_service import analyzer_service
    from schemas import (
        SingleJobGapAnalysis,
        GapAnalysisRequest,
        GapAnalysisResponse,
        GapAnalysisJobInput,
    )
except (ImportError, ModuleNotFoundError):
    # Fallback: import from hyphenated gap-analysis-agent package via importlib
    import importlib
    gap_schemas_mod = importlib.import_module("gap-analysis-agent.schemas")
    gap_svc_mod = importlib.import_module("gap-analysis-agent.services.gap_analysis_service")
    gap_analyzer_mod = importlib.import_module("gap-analysis-agent.services.analyzer_service")

    normalize_skill = gap_svc_mod.normalize_skill
    dedupe_skill_list = gap_svc_mod.dedupe_skill_list
    analyze_single_job_gap = gap_svc_mod.analyze_single_job_gap
    analyze_multiple_jobs = gap_svc_mod.analyze_multiple_jobs
    compute_metadata = gap_svc_mod.compute_metadata
    gap_analysis_service = gap_svc_mod.gap_analysis_service

    analyzer_service = gap_analyzer_mod.analyzer_service

    SingleJobGapAnalysis = gap_schemas_mod.SingleJobGapAnalysis
    GapAnalysisRequest = gap_schemas_mod.GapAnalysisRequest
    GapAnalysisResponse = gap_schemas_mod.GapAnalysisResponse
    GapAnalysisJobInput = gap_schemas_mod.GapAnalysisJobInput


class TestGapAnalysisServiceCore(unittest.TestCase):
    """Unit tests for the deterministic gap analysis service layer (no HTTP)."""

    # ------------------------------------------------------------------
    # Test 1 — Missing skills: user has partial overlap
    # ------------------------------------------------------------------
    def test_01_missing_skills_partial_overlap(self):
        """Test 1: User [Python, SQL]; Required [Python, Django, SQL, Git] → Missing [Django, Git]."""
        result = analyze_single_job_gap(
            user_skills=["Python", "SQL"],
            job_id="JOB-001",
            job_title="Python Developer",
            required_skills=["Python", "Django", "SQL", "Git"],
        )

        self.assertEqual(result["job_id"], "JOB-001")
        self.assertEqual(result["job_title"], "Python Developer")
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("SQL", result["matched_skills"])
        self.assertEqual(len(result["missing_skills"]), 2)
        self.assertIn("Django", result["missing_skills"])
        self.assertIn("Git", result["missing_skills"])
        # Explanation should mention both the matched and the missing skills
        explanation = result["gap_explanation"]
        self.assertIn("Python", explanation)
        self.assertIn("SQL", explanation)
        self.assertIn("Django", explanation)
        self.assertIn("Git", explanation)

    # ------------------------------------------------------------------
    # Test 2 — All skills available → Missing = []
    # ------------------------------------------------------------------
    def test_02_all_required_skills_available(self):
        """Test 2: User has every required skill → missing_skills empty, gap_priority None."""
        result = analyze_single_job_gap(
            user_skills=["Python", "Django", "SQL", "Git"],
            job_id="JOB-001",
            job_title="Python Developer",
            required_skills=["Python", "Django", "SQL", "Git"],
        )

        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(len(result["matched_skills"]), 4)
        self.assertEqual(result["gap_priority"], "None")
        self.assertIn("all of the required skills", result["gap_explanation"].lower())

    # ------------------------------------------------------------------
    # Test 3 — No matching skills → all required skills missing
    # ------------------------------------------------------------------
    def test_03_no_matching_skills(self):
        """Test 3: User [HTML, CSS]; Required [Python, Django, SQL] → all 3 missing."""
        result = analyze_single_job_gap(
            user_skills=["HTML", "CSS"],
            job_id="JOB-007",
            job_title="Backend Engineer",
            required_skills=["Python", "Django", "SQL"],
        )

        self.assertEqual(len(result["matched_skills"]), 0)
        self.assertEqual(set(result["missing_skills"]), {"Python", "Django", "SQL"})
        exp_lower = result["gap_explanation"].lower()
        self.assertTrue(
            ("required and currently missing" in exp_lower)
            or ("needed to qualify" in exp_lower)
            or ("are required" in exp_lower),
            f"Explanation should describe missing skills but got: {result['gap_explanation']}",
        )
        # With 3/3 missing, priority should be at least "High" or "Critical"
        self.assertIn(result["gap_priority"], {"High", "Critical"})

    # ------------------------------------------------------------------
    # Test 4 — Skill aliases are normalized consistently
    # ------------------------------------------------------------------
    def test_04_skill_aliases_normalized(self):
        """Test 4: React.js, ReactJS, Node.js, NodeJS, Python 3, JS are aliased consistently."""
        # User provides aliased variants → required uses canonical names
        result = analyze_single_job_gap(
            user_skills=["React.js", "ReactJS", "Python 3", "NodeJS", "JS"],
            job_id="JOB-006",
            job_title="Full Stack Developer",
            required_skills=[
                "React",
                "Node.js",
                "JavaScript",
                "Python",
                "Docker",  # Missing!
            ],
        )
        matched_set = {normalize_skill(s) for s in result["matched_skills"]}
        missing_set = {normalize_skill(s) for s in result["missing_skills"]}

        # All 4 aliased skills must match despite different casing/variant
        self.assertIn("react", matched_set)
        self.assertIn("nodejs", matched_set)
        self.assertIn("javascript", matched_set)
        self.assertIn("python", matched_set)
        # Only Docker is genuinely missing
        self.assertEqual(len(result["missing_skills"]), 1)
        self.assertIn("docker", missing_set)

        # React must not be flagged as missing (any variant matches)
        for ms in result["missing_skills"]:
            self.assertNotIn("react", ms.lower())

    # ------------------------------------------------------------------
    # Test 5 — Duplicate skills are deduplicated (case-insensitive)
    # ------------------------------------------------------------------
    def test_05_duplicate_skills_deduplicated(self):
        """Test 5: ['Python', 'python', 'Python'] → treated as a single skill."""
        result = analyze_single_job_gap(
            user_skills=["Python", "python", "Python", "Git", "git", "GIT"],
            job_id="JOB-001",
            job_title="Python Developer",
            required_skills=[
                "Python",
                "Django",
                "SQL",
                "Git",
                "SQL",  # duplicate in required → ignored
            ],
        )
        # user_skills list should be deduped to Python and Git only
        self.assertEqual(len(result["user_skills"]), 2)
        # required_skills list should be deduped to 4
        self.assertEqual(len(result["required_skills"]), 4)
        # Matched: Python + Git
        self.assertEqual(len(result["matched_skills"]), 2)
        # Missing: Django + SQL
        self.assertEqual(len(result["missing_skills"]), 2)
        self.assertIn("Django", result["missing_skills"])
        self.assertIn("SQL", result["missing_skills"])

    # ------------------------------------------------------------------
    # Test 6 — Multiple jobs: distinct gap analysis per job with correct job_ids
    # ------------------------------------------------------------------
    def test_06_multiple_jobs_distinct_results(self):
        """Test 6: Multiple jobs → separate analyses, correct job_ids & order preserved."""
        jobs = [
            {
                "job_id": "JOB-001",
                "job_title": "Python Developer",
                "required_skills": ["Python", "Django", "SQL", "Git"],
            },
            {
                "job_id": "JOB-002",
                "job_title": "Frontend Developer",
                "required_skills": ["React", "JavaScript", "TypeScript", "CSS"],
            },
            {
                "job_id": "JOB-003",
                "job_title": "DevOps Engineer",
                "required_skills": ["Docker", "Kubernetes", "AWS", "Git"],
            },
        ]
        user_skills = ["Python", "React", "Git", "SQL", "JavaScript"]
        analyses = analyze_multiple_jobs(user_skills=user_skills, jobs=jobs)

        self.assertEqual(len(analyses), 3)
        # Order preserved, job_ids correct
        self.assertEqual(analyses[0]["job_id"], "JOB-001")
        self.assertEqual(analyses[1]["job_id"], "JOB-002")
        self.assertEqual(analyses[2]["job_id"], "JOB-003")

        # JOB-001: matched Python, SQL, Git; missing Django
        self.assertIn("Django", analyses[0]["missing_skills"])
        self.assertEqual(len(analyses[0]["missing_skills"]), 1)

        # JOB-002: matched React, JavaScript; missing TypeScript, CSS
        missing2 = set(analyses[1]["missing_skills"])
        self.assertEqual(missing2, {"TypeScript", "CSS"})

        # JOB-003: matched Git; missing Docker, Kubernetes, AWS
        missing3 = set(analyses[2]["missing_skills"])
        self.assertEqual(missing3, {"Docker", "Kubernetes", "AWS"})

        # Metadata sanity check
        meta = compute_metadata(analyses)
        self.assertEqual(meta["count_jobs_analyzed"], 3)
        self.assertEqual(meta["total_missing_skill_occurrences"], 1 + 2 + 3)

    # ------------------------------------------------------------------
    # Edge: No user skills → explanation says "not provided any skills"
    # ------------------------------------------------------------------
    def test_07_no_user_skills_explanation_mentions(self):
        """User has no skills → gap_explanation explicitly reflects that."""
        result = analyze_single_job_gap(
            user_skills=[],
            job_id="JOB-001",
            job_title="Python Developer",
            required_skills=["Python", "Django"],
        )
        exp_lower = result["gap_explanation"].lower()
        self.assertTrue(
            ("has not provided any skills" in exp_lower)
            or ("has not provided any of the candidate skills" in exp_lower),
            f"Expected 'has not provided any skills' in explanation, got: {result['gap_explanation']}",
        )
        self.assertEqual(set(result["missing_skills"]), {"Python", "Django"})

    # ------------------------------------------------------------------
    # Edge: Precomputed match/missing lists are accepted when valid
    # ------------------------------------------------------------------
    def test_08_precomputed_match_lists_validated_and_used(self):
        """Valid precomputed matched+missing sets are reused instead of recomputed."""
        result = analyze_single_job_gap(
            user_skills=["Python"],  # intentionally not the full truth
            job_id="JOB-X",
            job_title="Senior Python Dev",
            required_skills=["Python", "Django", "FastAPI"],
            precomputed_matched=["Python", "FastAPI"],  # SkillMatching says FastAPI is matched via semantic similarity
            precomputed_missing=["Django"],
            match_score=72.3,
        )
        self.assertEqual(set(result["matched_skills"]), {"Python", "FastAPI"})
        self.assertEqual(result["missing_skills"], ["Django"])
        self.assertEqual(result["match_score"], 72.3)

    # ------------------------------------------------------------------
    # Edge: Invalid precomputed lists are discarded, result is recomputed
    # ------------------------------------------------------------------
    def test_09_invalid_precomputed_results_are_recomputed(self):
        """Precomputed matched+missing that don't cover required → recomputed deterministically."""
        result = analyze_single_job_gap(
            user_skills=["Python", "SQL"],
            job_id="JOB-001",
            job_title="Python Developer",
            required_skills=["Python", "Django", "SQL", "Git"],
            precomputed_matched=["Python"],  # Missing SQL and says nothing about others — invalid
            precomputed_missing=["Django"],  # Git unaccounted for — coverage incomplete
        )
        # Must recompute → matched=[Python, SQL] missing=[Django, Git]
        self.assertIn("SQL", result["matched_skills"])
        self.assertIn("Git", result["missing_skills"])

    # ------------------------------------------------------------------
    # Legacy analyzer_service delegate also works after refactor
    # ------------------------------------------------------------------
    def test_10_legacy_analyzer_delegate_still_works(self):
        """analyzer_service.identify_missing_skills and calculate_readiness_score work."""
        gaps = analyzer_service.identify_missing_skills(
            possessed_skills=["Python", "SQL"],
            required_skills=["Python", "Django", "SQL", "Git"],
        )
        self.assertEqual(len(gaps), 2)
        names = sorted(g["skill_name"] for g in gaps)
        self.assertEqual(names, ["Django", "Git"])
        # Readiness: 2/4 matched → 50%
        self.assertEqual(analyzer_service.calculate_readiness_score(4, 2), 50.0)
        # Edge cases
        self.assertEqual(analyzer_service.calculate_readiness_score(0, 0), 100.0)
        self.assertEqual(analyzer_service.calculate_readiness_score(5, 999), 100.0)


class TestGapAnalysisAPI(unittest.TestCase):
    """FastAPI integration tests for the Gap Analysis endpoints."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ------------------------------------------------------------------
    # Test 7 (API part 1) — valid request → 200 with correct analyses
    # ------------------------------------------------------------------
    def test_11_post_gap_analysis_valid_request_200(self):
        payload = {
            "candidate_skills": ["Python", "SQL"],
            "jobs": [
                {
                    "job_id": "JOB-001",
                    "job_title": "Python Developer",
                    "required_skills": ["Python", "Django", "SQL", "Git"],
                },
                {
                    "job_id": "JOB-002",
                    "job_title": "React Developer",
                    "required_skills": ["React", "JavaScript", "TypeScript"],
                },
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(len(body["analyses"]), 2)
        # First job: job_id JOB-001
        self.assertEqual(body["analyses"][0]["job_id"], "JOB-001")
        self.assertIn("Django", body["analyses"][0]["missing_skills"])
        self.assertIn("Git", body["analyses"][0]["missing_skills"])
        # Second job: job_id JOB-002 (all 3 required missing)
        self.assertEqual(body["analyses"][1]["job_id"], "JOB-002")
        missing2 = set(body["analyses"][1]["missing_skills"])
        self.assertEqual(missing2, {"React", "JavaScript", "TypeScript"})
        # Metadata present
        self.assertIn("count_jobs_analyzed", body["metadata"])
        self.assertEqual(body["metadata"]["count_jobs_analyzed"], 2)

    # ------------------------------------------------------------------
    # Test 7 (API part 2) — missing required fields → 422
    # ------------------------------------------------------------------
    def test_12_post_missing_required_fields_422(self):
        # No jobs list → 422
        res = self.client.post("/api/gap-analysis", json={"candidate_skills": ["Python"]})
        self.assertEqual(res.status_code, 422)

        # Empty jobs list → 422
        res = self.client.post("/api/gap-analysis", json={"candidate_skills": ["Python"], "jobs": []})
        self.assertEqual(res.status_code, 422)

        # Job missing job_id → 422
        payload = {
            "candidate_skills": ["Python"],
            "jobs": [{"job_title": "Python Dev", "required_skills": ["Python"]}],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 422)

        # Job missing job_title → 422
        payload = {
            "candidate_skills": ["Python"],
            "jobs": [{"job_id": "JOB-1", "required_skills": ["Python"]}],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 422)

    # ------------------------------------------------------------------
    # Test 7 (API part 3) — invalid skill types → 422
    # ------------------------------------------------------------------
    def test_13_post_invalid_skill_types_422(self):
        # required_skills is a string (should be a list)
        payload = {
            "candidate_skills": ["Python"],
            "jobs": [
                {
                    "job_id": "JOB-1",
                    "job_title": "Python Dev",
                    "required_skills": "Python,Django",  # invalid! must be list
                }
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 422)

        # candidate_skills is a string (should be a list)
        payload = {
            "candidate_skills": "Python",
            "jobs": [
                {
                    "job_id": "JOB-1",
                    "job_title": "Python Dev",
                    "required_skills": ["Python"],
                }
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 422)

    # ------------------------------------------------------------------
    # Test 7 (API part 4) — empty/invalid job data handled
    # ------------------------------------------------------------------
    def test_14_post_empty_job_required_skills_ok(self):
        """Job with empty required_skills → analysis succeeds with no gaps marked as missing."""
        payload = {
            "candidate_skills": ["Python"],
            "jobs": [
                {
                    "job_id": "JOB-EMPTY",
                    "job_title": "Generic Role",
                    "required_skills": [],
                }
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["analyses"][0]["missing_skills"], [])
        self.assertEqual(body["analyses"][0]["gap_priority"], "None")

    # ------------------------------------------------------------------
    # Health endpoint
    # ------------------------------------------------------------------
    def test_15_health_endpoint_200(self):
        res = self.client.get("/api/gap-analysis/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["agent"], "gap-analysis-agent")
        self.assertIn("mode", body)

    # ------------------------------------------------------------------
    # Legacy /analyze endpoint still responds 200 with structured data
    # ------------------------------------------------------------------
    def test_16_legacy_analyze_endpoint_200(self):
        payload = {
            "candidate_skills": ["Python", "SQL"],
            "target_role": "Python Developer",
            "required_skills": ["Python", "Django", "SQL", "Git"],
        }
        res = self.client.post("/api/gap-analysis/analyze", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["target_role"], "Python Developer")
        self.assertEqual(body["readiness_score"], 50.0)
        missing_names = sorted(m["skill_name"] for m in body["missing_skills"])
        self.assertEqual(missing_names, ["Django", "Git"])

    # ------------------------------------------------------------------
    # user_profile.skills is preferred over candidate_skills direct
    # ------------------------------------------------------------------
    def test_17_user_profile_skills_used(self):
        payload = {
            "candidate_skills": ["Java"],  # ignored because user_profile.skills exists
            "user_profile": {
                "education": "B.Tech Computer Science",
                "skills": ["Python", "SQL"],
                "location": "Pune",
                "interests": ["AI", "Web Development"],
            },
            "jobs": [
                {
                    "job_id": "JOB-001",
                    "job_title": "Python Developer",
                    "required_skills": ["Python", "Django", "SQL", "Git"],
                }
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # user_profile.skills = [Python, SQL] → so Python + SQL are matched
        first = body["analyses"][0]
        self.assertIn("Python", first["matched_skills"])
        self.assertIn("SQL", first["matched_skills"])
        self.assertNotIn("Java", first["matched_skills"])  # the ignored candidate_skills

    # ------------------------------------------------------------------
    # /analyze-jobs alias works identically to POST /api/gap-analysis
    # ------------------------------------------------------------------
    def test_18_analyze_jobs_alias_endpoint(self):
        payload = {
            "candidate_skills": ["Python"],
            "jobs": [
                {
                    "job_id": "JOB-1",
                    "job_title": "Python Dev",
                    "required_skills": ["Python", "Django"],
                }
            ],
        }
        res1 = self.client.post("/api/gap-analysis", json=payload)
        res2 = self.client.post("/api/gap-analysis/analyze-jobs", json=payload)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res1.json()["analyses"], res2.json()["analyses"])


class TestEndToEndFlow(unittest.TestCase):
    """Integration flow: Skill Matching → Gap Analysis, using demo jobs (no Jooble quota)."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_19_e2e_skill_match_then_gap_analysis(self):
        """Full flow currently available: UserProfile → Demo Jobs fallback → Skill Matching → Gap Analysis."""
        # Step 1: Skill Matching → this will use demo jobs fallback (no Jooble key by default)
        user_profile = {
            "education": "B.Tech Computer Science",
            "skills": ["Python", "SQL", "React", "Java"],
            "location": "Pune",
            "interests": ["AI", "Web Development"],
            "target_role": "Python Developer",
        }
        match_res = self.client.post("/api/skill-match", json=user_profile)
        self.assertEqual(match_res.status_code, 200, f"Skill match endpoint failed: {match_res.text}")
        matches = match_res.json()
        self.assertIsInstance(matches, list)
        self.assertGreater(len(matches), 0)
        # X-Job-Source header set (demo, because no real Jooble key configured)
        self.assertIn(match_res.headers.get("X-Job-Source"), {"demo", "jooble"})

        # Step 2: Take top 5 matches and build a Gap Analysis request
        top5 = matches[:5]
        gap_jobs = []
        for m in top5:
            gap_jobs.append({
                "job_id": m.get("job_id"),
                "job_title": m.get("title") or m.get("job_title"),
                "required_skills": [],  # we don't have required_skills in the match response; fetch from demo jobs
                "matched_skills": m.get("matched_skills", []),
                "missing_skills": m.get("missing_skills", []),
                "match_score": m.get("match_score"),
            })

        # To avoid missing required_skills, let's fetch from /demo-jobs endpoint and cross-populate
        demo_res = self.client.get("/api/skill-match/demo-jobs")
        self.assertEqual(demo_res.status_code, 200)
        demo_jobs = demo_res.json()
        job_req_map = {j["job_id"]: j["required_skills"] for j in demo_jobs}
        for gj in gap_jobs:
            if gj["job_id"] in job_req_map:
                gj["required_skills"] = job_req_map[gj["job_id"]]

        # Filter to jobs we can fully analyze (those in demo-jobs dataset)
        gap_jobs_valid = [gj for gj in gap_jobs if gj["required_skills"]]
        self.assertGreaterEqual(len(gap_jobs_valid), 1, "Expected at least 1 demo-backed match for e2e test")

        # Step 3: Call Gap Analysis with user_profile + valid matched jobs
        gap_payload = {
            "user_profile": user_profile,
            "jobs": gap_jobs_valid,
        }
        gap_res = self.client.post("/api/gap-analysis", json=gap_payload)
        self.assertEqual(gap_res.status_code, 200, f"Gap analysis endpoint failed: {gap_res.text}")
        gap_body = gap_res.json()
        self.assertEqual(gap_body["status"], "success")
        self.assertEqual(len(gap_body["analyses"]), len(gap_jobs_valid))

        # Every analysis must have the six Step-2 required contract fields:
        # job_id, job_title, user_skills, required_skills, missing_skills, gap_explanation
        contract_fields = [
            "job_id",
            "job_title",
            "user_skills",
            "required_skills",
            "missing_skills",
            "gap_explanation",
        ]
        for analysis in gap_body["analyses"]:
            for f in contract_fields:
                self.assertIn(f, analysis, f"Missing contract field {f} in analysis {analysis}")
            # Explanations are non-empty strings
            self.assertTrue(isinstance(analysis["gap_explanation"], str))
            self.assertTrue(len(analysis["gap_explanation"]) > 0)


if __name__ == "__main__":
    unittest.main()
