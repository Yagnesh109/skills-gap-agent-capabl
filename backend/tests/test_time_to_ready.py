import importlib
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

ttr = importlib.import_module("training-agent.time_to_ready")


class TestCourseCatalogPricing(unittest.TestCase):
    def test_existing_catalog_has_valid_price_fields(self):
        courses = ttr.load_courses()
        self.assertEqual(len(courses), 15)
        for course in courses:
            self.assertIn("price_inr", course)
            self.assertIn("is_free", course)
            self.assertIsInstance(course["price_inr"], int)
            self.assertGreaterEqual(course["price_inr"], 0)
            if course["is_free"]:
                self.assertEqual(course["price_inr"], 0)
            else:
                self.assertGreater(course["price_inr"], 0)

    def test_course_schema_accepts_price_and_free_flag(self):
        courses = ttr.validate_course_data([
            {
                "course_id": "CRS-X",
                "title": "Git Basics",
                "provider": "Example",
                "duration_weeks": 1,
                "price_inr": 0,
                "is_free": True,
                "skills_taught": ["Git"],
                "difficulty": "Beginner",
                "url": "https://example.com",
            }
        ])
        self.assertEqual(courses[0]["price_inr"], 0)
        self.assertTrue(courses[0]["is_free"])


class TestTimeToReadyCalculation(unittest.TestCase):
    def setUp(self):
        self.courses = [
            {
                "course_id": "CRS-1",
                "title": "Django and Git",
                "provider": "Example",
                "duration_weeks": 3,
                "price_inr": 0,
                "is_free": True,
                "skills_taught": ["Django", "Git"],
                "difficulty": "Beginner",
                "url": "https://example.com/django-git",
            },
            {
                "course_id": "CRS-2",
                "title": "Docker Fundamentals",
                "provider": "Example",
                "duration_weeks": 2,
                "price_inr": 499,
                "is_free": False,
                "skills_taught": ["Docker"],
                "difficulty": "Beginner",
                "url": "https://example.com/docker",
            },
            {
                "course_id": "CRS-3",
                "title": "Free Docker Overview",
                "provider": "Example",
                "duration_weeks": 5,
                "price_inr": 0,
                "is_free": True,
                "skills_taught": ["Docker"],
                "difficulty": "Beginner",
                "url": "https://example.com/free-docker",
            },
        ]

    def test_single_missing_skill_selects_matching_course(self):
        result = ttr.calculate_time_to_ready(["Docker"], self.courses)
        self.assertEqual(result["recommended_courses"][0]["course_id"], "CRS-2")
        self.assertEqual(result["total_weeks"], 2)
        self.assertEqual(result["total_cost_inr"], 499)

    def test_multiple_missing_skills_total_weeks_and_cost(self):
        result = ttr.calculate_time_to_ready(["Django", "Git", "Docker"], self.courses)
        self.assertEqual([c["course_id"] for c in result["recommended_courses"]], ["CRS-1", "CRS-2"])
        self.assertEqual(result["total_weeks"], 5)
        self.assertEqual(result["total_cost_inr"], 499)
        self.assertTrue(result["is_fully_covered"])

    def test_multi_skill_course_is_preferred(self):
        result = ttr.calculate_time_to_ready(["Django", "Git"], self.courses)
        self.assertEqual(len(result["recommended_courses"]), 1)
        self.assertEqual(result["recommended_courses"][0]["course_id"], "CRS-1")

    def test_duplicate_missing_skills_are_counted_once(self):
        result = ttr.calculate_time_to_ready(["Docker", "docker", "Docker"], self.courses)
        self.assertEqual(len(result["recommended_courses"]), 1)
        self.assertEqual(result["total_weeks"], 2)
        self.assertEqual(result["total_cost_inr"], 499)

    def test_no_missing_skills_is_already_ready(self):
        result = ttr.calculate_time_to_ready([], self.courses)
        self.assertEqual(result["total_weeks"], 0)
        self.assertEqual(result["total_cost_inr"], 0)
        self.assertTrue(result["is_fully_covered"])

    def test_missing_skill_without_course_is_uncovered(self):
        result = ttr.calculate_time_to_ready(["Kubernetes"], self.courses)
        self.assertFalse(result["is_fully_covered"])
        self.assertEqual(result["uncovered_skills"], ["Kubernetes"])

    def test_free_only_uses_only_free_courses(self):
        result = ttr.calculate_time_to_ready(["Docker"], self.courses, free_only=True)
        self.assertEqual(result["recommended_courses"][0]["course_id"], "CRS-3")
        self.assertEqual(result["total_cost_inr"], 0)

    def test_free_only_reports_uncovered_when_only_paid_course_exists(self):
        result = ttr.calculate_time_to_ready(
            ["FastAPI"],
            [{
                "course_id": "CRS-4",
                "title": "FastAPI Paid",
                "provider": "Example",
                "duration_weeks": 3,
                "price_inr": 999,
                "is_free": False,
                "skills_taught": ["FastAPI"],
            }],
            free_only=True,
        )
        self.assertFalse(result["is_fully_covered"])
        self.assertEqual(result["uncovered_skills"], ["FastAPI"])
        self.assertEqual(result["total_cost_inr"], 0)

    def test_invalid_duration_course_is_unusable_without_crashing(self):
        result = ttr.calculate_time_to_ready(
            ["Docker"],
            [{**self.courses[1], "duration_weeks": None}],
        )
        self.assertFalse(result["is_fully_covered"])
        self.assertEqual(result["uncovered_skills"], ["Docker"])

    def test_empty_catalog_does_not_crash(self):
        result = ttr.calculate_time_to_ready(["Docker"], [])
        self.assertFalse(result["is_fully_covered"])
        self.assertEqual(result["recommended_courses"], [])

    def test_per_job_calculations_are_independent(self):
        results = ttr.calculate_per_job_time_to_ready(
            [
                {"job_id": "JOB-1", "job_title": "Backend", "missing_skills": ["Django", "Git"]},
                {"job_id": "JOB-2", "job_title": "DevOps", "missing_skills": ["Docker"]},
            ],
            self.courses,
        )
        self.assertEqual(results["JOB-1"]["total_weeks"], 3)
        self.assertEqual(results["JOB-1"]["total_cost_inr"], 0)
        self.assertEqual(results["JOB-2"]["total_weeks"], 2)
        self.assertEqual(results["JOB-2"]["total_cost_inr"], 499)


if __name__ == "__main__":
    unittest.main()
