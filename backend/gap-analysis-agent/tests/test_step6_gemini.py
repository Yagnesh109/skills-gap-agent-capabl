"""Step 6 — Gemini Integration tests.

All API calls to Gemini are mocked. No real Google API quota is ever consumed.
"""

from __future__ import annotations

import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Path setup (matches existing test_gap_analysis.py)
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
    from services.gemini_service import (
        GeminiService,
        GEMINI_SYSTEM_PROMPT,
        _parse_gemini_json,
        _normalize_ai_reasoning_shape,
        _build_fallback_ai_reasoning,
        _build_user_prompt_payload,
    )
except (ImportError, ModuleNotFoundError):
    import importlib
    _gemini_mod = importlib.import_module("gap-analysis-agent.services.gemini_service")
    GeminiService = _gemini_mod.GeminiService
    GEMINI_SYSTEM_PROMPT = _gemini_mod.GEMINI_SYSTEM_PROMPT
    _parse_gemini_json = _gemini_mod._parse_gemini_json
    _normalize_ai_reasoning_shape = _gemini_mod._normalize_ai_reasoning_shape
    _build_fallback_ai_reasoning = _gemini_mod._build_fallback_ai_reasoning
    _build_user_prompt_payload = _gemini_mod._build_user_prompt_payload


class TestGeminiServiceInit(unittest.TestCase):
    """Test 1 — Gemini service initialization and configuration."""

    def test_01_service_init_with_key_reports_configured(self):
        """API key present → is_configured is True, model name & masked key are sane."""
        svc = GeminiService(api_key="ABcdefgh1234567890", model_name="gemini-3.6-flash")
        self.assertTrue(svc.is_configured)
        self.assertEqual(svc.model_name, "gemini-3.6-flash")
        # Masked key must never contain more than first 3 + last 2 chars
        masked = svc._api_key_masked
        self.assertNotIn("efgh1234567890", masked)
        self.assertTrue(masked.startswith("ABc"))
        self.assertTrue(masked.endswith("90"))

    def test_02_service_init_without_key_not_configured(self):
        """No API key → is_configured False; does not attempt to load SDK."""
        svc = GeminiService(api_key="")
        self.assertFalse(svc.is_configured)
        # _model_instance must still be None (no SDK call attempted)
        self.assertIsNone(svc._model_instance)

    def test_03_service_picks_up_env_based_defaults(self):
        """Defaults for model / temperature / timeout come from settings when args omitted."""
        # With explicit key but omitting the rest, expect env defaults (no crash)
        svc = GeminiService(api_key="some-test-key")
        self.assertTrue(svc.model_name)  # any string
        self.assertIsInstance(svc.temperature, float)
        self.assertIsInstance(svc.timeout_seconds, float)


class TestGeminiFallbackPaths(unittest.TestCase):
    """Tests 2, 4, 5, 6 — Missing key, API error, timeout, malformed JSON → safe fallback."""

    def test_04_missing_api_key_produces_deterministic_fallback(self):
        """Test 2 — Missing GEMINI_API_KEY → graceful fallback, no crash, deterministic payloads."""
        svc = GeminiService(api_key="")
        reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
            user_profile={"skills": ["Python", "SQL"], "location": "Pune"},
            job={
                "title": "Python Developer",
                "required_skills": ["Python", "Django", "SQL", "Git"],
            },
            matching={
                "match_score": 78.5,
                "matched_skills": ["Python", "SQL"],
                "missing_skills": ["Django", "Git"],
            },
            gap_analysis={"matched_skills": ["Python", "SQL"], "missing_skills": ["Django", "Git"]},
        ))
        self.assertFalse(ok, "Expected success=False when key is missing.")
        # ai_reasoning dict must always be complete
        for key in ("summary", "strengths", "priority_gaps", "learning_focus"):
            self.assertIn(key, reasoning)
        self.assertEqual(reasoning["source"], "deterministic_fallback")
        # Strengths = matched_skills
        self.assertEqual(sorted(reasoning["strengths"]), ["Python", "SQL"])
        # Missing skills are covered as priority_gaps entries
        missing_entries = [pg["skill"] for pg in reasoning["priority_gaps"]]
        self.assertEqual(sorted(missing_entries), ["Django", "Git"])
        # Explanations always mention 'fallback' or 'unavailable' clearly
        self.assertTrue(
            "unavailable" in reasoning["note"].lower()
            or "unavailable" in reasoning["summary"].lower()
        )

    @patch.object(GeminiService, "_load_sdk")
    def test_05_gemini_api_error_falls_back(self, mock_load_sdk):
        """Test 4 — Gemini SDK call raises arbitrary exception → safe fallback, no success flag."""
        # Configure a model that, when generate_content_async is called, raises
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(side_effect=RuntimeError("google API down!"))
        mock_load_sdk.return_value = (MagicMock(), mock_model)

        svc = GeminiService(api_key="valid-looking-key")
        reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
            user_profile={"skills": ["Python"]},
            job={"title": "X", "required_skills": ["Python", "Git"]},
            matching={"match_score": 50, "matched_skills": ["Python"], "missing_skills": ["Git"]},
            gap_analysis={"matched_skills": ["Python"], "missing_skills": ["Git"]},
        ))
        self.assertFalse(ok)
        self.assertEqual(reasoning["source"], "deterministic_fallback")
        self.assertEqual(len(reasoning["priority_gaps"]), 1)
        self.assertEqual(reasoning["priority_gaps"][0]["skill"], "Git")

    @patch.object(GeminiService, "_load_sdk")
    def test_06_gemini_timeout_falls_back(self, mock_load_sdk):
        """Test 5 — Mock call that never completes → timeout → fallback succeeds gracefully."""
        async def _sleep_forever(*a, **kw):
            await asyncio.sleep(999)

        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(side_effect=_sleep_forever)
        mock_load_sdk.return_value = (MagicMock(), mock_model)

        # Very short timeout (0.05s) to make test fast
        svc = GeminiService(api_key="k", timeout_seconds=0.05)
        reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
            user_profile={"skills": []},
            job={"title": "Role", "required_skills": ["A", "B"]},
            matching={"match_score": 0, "matched_skills": [], "missing_skills": ["A", "B"]},
            gap_analysis={"matched_skills": [], "missing_skills": ["A", "B"]},
        ))
        self.assertFalse(ok)
        self.assertEqual(reasoning["source"], "deterministic_fallback")

    @patch.object(GeminiService, "_load_sdk")
    def test_07_gemini_malformed_response_falls_back(self, mock_load_sdk):
        """Test 6 — Invalid unparseable response (not JSON) → fallback + success=False."""
        mock_resp = MagicMock()
        mock_resp.text = "Sure! Here's your answer. No JSON, just text. " * 5
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_resp)
        mock_load_sdk.return_value = (MagicMock(), mock_model)

        svc = GeminiService(api_key="k")
        reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
            user_profile={"skills": ["Python"]},
            job={"title": "R", "required_skills": ["Python", "Java"]},
            matching={"match_score": 50, "matched_skills": ["Python"], "missing_skills": ["Java"]},
            gap_analysis={"matched_skills": ["Python"], "missing_skills": ["Java"]},
        ))
        self.assertFalse(ok)
        self.assertEqual(reasoning["source"], "deterministic_fallback")


class TestGeminiSuccessFlow(unittest.TestCase):
    """Test 3, 7 — Structured mock success + hallucination protection."""

    def _make_svc_returning_json(self, json_dict):
        """Create a GeminiService that, when _load_sdk is called, returns a model whose
        generate_content_async returns json.dumps(json_dict) .text."""
        mock_resp = MagicMock()
        mock_resp.text = json.dumps(json_dict)
        mock_model = MagicMock()
        mock_model.generate_content_async = AsyncMock(return_value=mock_resp)
        return mock_model, mock_resp

    def test_08_mock_gemini_success_returns_structured_reasoning(self):
        """Test 3 — Valid structured JSON → success=True, fields pass through cleanly."""
        expected = {
            "summary": "Candidate is strong in Python/SQL, learn Django/Git for this role.",
            "strengths": ["Python", "SQL"],
            "priority_gaps": [
                {"skill": "Django", "reason": "Django powers the backend framework for this role."},
                {"skill": "Git", "reason": "Collaborative workflow tool required by the team."},
            ],
            "learning_focus": ["Django fundamentals", "Git branching and PRs"],
        }
        mock_model, _ = self._make_svc_returning_json(expected)

        svc = GeminiService(api_key="k")
        with patch.object(svc, "_load_sdk", return_value=(MagicMock(), mock_model)):
            reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
                user_profile={"skills": ["Python", "SQL"]},
                job={"title": "Python Dev", "required_skills": ["Python", "Django", "SQL", "Git"]},
                matching={
                    "match_score": 75,
                    "matched_skills": ["Python", "SQL"],
                    "missing_skills": ["Django", "Git"],
                },
                gap_analysis={"matched_skills": ["Python", "SQL"], "missing_skills": ["Django", "Git"]},
            ))
        self.assertTrue(ok)
        self.assertEqual(reasoning["source"], "gemini")
        self.assertIn("strong in Python/SQL", reasoning["summary"])
        self.assertEqual(sorted(reasoning["strengths"]), ["Python", "SQL"])
        self.assertEqual(len(reasoning["priority_gaps"]), 2)
        self.assertEqual(
            [pg["skill"] for pg in reasoning["priority_gaps"]],
            ["Django", "Git"],
        )
        self.assertEqual(len(reasoning["learning_focus"]), 2)

    def test_09_hallucination_protection_does_not_alter_deterministic_facts(self):
        """Test 7 — Hallucination guard: if Gemini invents missing skills / strengths, they are stripped.

        Deterministic: matched=[Python, SQL], missing=[Django, Git]
        Gemini mocked to return:
            strengths=["Python","SQL","C++"]    (C++ invented)
            priority_gaps=[{"skill":"Django"},  (okay)
                           {"skill":"Docker"},    (Docker invented, not in missing)
                           {"skill":"Git"}]      (okay)
        Expected output: C++ removed from strengths, Docker removed from priority_gaps.
        """
        hallucinated = {
            "summary": "Invented C++ and Docker.",
            "strengths": ["Python", "SQL", "C++"],   # C++ is hallucinated
            "priority_gaps": [
                {"skill": "Django", "reason": "ok"},
                {"skill": "Docker", "reason": "INVENTED, should be removed"},
                {"skill": "Git", "reason": "ok"},
            ],
            "learning_focus": ["Django", "Docker basics", "Git"],
        }
        mock_model, _ = self._make_svc_returning_json(hallucinated)
        svc = GeminiService(api_key="k")
        with patch.object(svc, "_load_sdk", return_value=(MagicMock(), mock_model)):
            reasoning, ok = asyncio.run(svc.analyze_gap_reasoning(
                user_profile={"skills": ["Python", "SQL"]},
                job={
                    "title": "Python Dev",
                    "required_skills": ["Python", "Django", "SQL", "Git"],
                },
                matching={
                    "match_score": 70.0,
                    "matched_skills": ["Python", "SQL"],
                    "missing_skills": ["Django", "Git"],
                },
                gap_analysis={"matched_skills": ["Python", "SQL"], "missing_skills": ["Django", "Git"]},
            ))

        self.assertTrue(ok)
        # Hallucinated C++ removed → only Python/SQL left
        self.assertEqual(sorted(reasoning["strengths"]), ["Python", "SQL"])
        # Hallucinated Docker removed from priority_gaps
        pg_skills = [pg["skill"] for pg in reasoning["priority_gaps"]]
        self.assertEqual(sorted(pg_skills), ["Django", "Git"])
        # Learning focus: still allowed free-form, just capped by len(missing_skills)=2
        self.assertLessEqual(len(reasoning["learning_focus"]), 2)


class TestGeminiParsingHelpers(unittest.TestCase):
    """Unit tests for JSON parser + normalizer."""

    def test_10_parse_plain_json(self):
        raw = '{"summary":"abc","strengths":["A"],"priority_gaps":[],"learning_focus":[]}'
        out, ok = _parse_gemini_json(raw)
        self.assertTrue(ok)
        self.assertEqual(out["summary"], "abc")

    def test_11_parse_markdown_fenced_json(self):
        raw = (
            "Certainly! Here is the object:\n"
            "```json\n"
            '{"summary":"xyz","strengths":["P"],"priority_gaps":[{"skill":"R","reason":"w"}],"learning_focus":["x"]}\n'
            "```\n"
            "Let me know if you want more.\n"
        )
        out, ok = _parse_gemini_json(raw)
        self.assertTrue(ok)
        self.assertEqual(out["summary"], "xyz")
        self.assertEqual(out["strengths"], ["P"])

    def test_12_parse_rejects_non_dict(self):
        out, ok = _parse_gemini_json('["a", "list"]')
        self.assertFalse(ok)

    def test_13_parse_rejects_garbage(self):
        out, ok = _parse_gemini_json("hello world, no json")
        self.assertFalse(ok)

    def test_14_normalize_shape_casts_types_safely(self):
        malformed = {
            "summary": None,
            "strengths": "not a list",
            "priority_gaps": [
                {"skill": "Git", "reason": "r"},
                "Unexpected bare string skill",
                {"skill": ""},  # empty, dropped
            ],
            "learning_focus": "Single focus string",
        }
        out = _normalize_ai_reasoning_shape(malformed)
        self.assertEqual(out["summary"], "")
        self.assertEqual(out["strengths"], [])
        # Only the first non-empty dict item + bare string
        self.assertEqual(len(out["priority_gaps"]), 2)
        self.assertEqual(out["priority_gaps"][0]["skill"], "Git")
        self.assertEqual(out["priority_gaps"][1]["skill"], "Unexpected bare string skill")
        self.assertEqual(out["learning_focus"], ["Single focus string"])

    def test_15_build_user_prompt_payload_is_deterministic(self):
        """Prompt builder doesn't leak hidden fields; uses only whitelisted keys."""
        prompt = _build_user_prompt_payload(
            user_profile={
                "education": "B.Tech",
                "skills": ["Python"],
                "location": "Pune",
                "interests": ["AI"],
                "LEAKY": "SHOULD NOT APPEAR",
            },
            job={
                "title": "Python Dev",
                "company": "C",
                "required_skills": ["Python"],
                "description": "desc",
                "location": "Pune",
                "LEAK": "X",
            },
            matching={
                "match_score": 90.0,
                "matched_skills": ["Python"],
                "missing_skills": [],
            },
            gap_analysis={
                "missing_skills": [],
                "matched_skills": ["Python"],
                "gap_priority": "None",
            },
        )
        # Prompt should be a string that is valid JSON-encoded block
        self.assertIsInstance(prompt, str)
        # No leakage
        self.assertNotIn("SHOULD NOT APPEAR", prompt)
        self.assertNotIn('"LEAK"', prompt)
        # Sanity: contains education value (B.Tech)
        self.assertIn("B.Tech", prompt)


class TestGeminiEndpointIntegration(unittest.TestCase):
    """Test the FastAPI router integration: Gap Analysis endpoints now return ai_reasoning."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_16_endpoint_returns_ai_reasoning_block_for_deterministic_fallback(self):
        """Missing Gemini key → endpoint still returns ai_reasoning (source=deterministic_fallback)."""
        # Build a real gap analysis API call: since no GEMINI_API_KEY in env,
        # we should receive a fallback ai_reasoning with source == deterministic_fallback
        payload = {
            "candidate_skills": ["Python", "SQL"],
            "jobs": [
                {
                    "job_id": "JOB-001",
                    "job_title": "Python Developer",
                    "required_skills": ["Python", "Django", "SQL", "Git"],
                    "matched_skills": ["Python", "SQL"],
                    "missing_skills": ["Django", "Git"],
                    "match_score": 78.5,
                }
            ],
        }
        res = self.client.post("/api/gap-analysis", json=payload)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "success")
        analysis = body["analyses"][0]
        # Deterministic fields must remain authoritative (unchanged)
        self.assertEqual(analysis["job_id"], "JOB-001")
        self.assertEqual(analysis["match_score"], 78.5)
        self.assertEqual(set(analysis["matched_skills"]), {"Python", "SQL"})
        self.assertEqual(set(analysis["missing_skills"]), {"Django", "Git"})
        self.assertEqual(set(analysis["required_skills"]), {"Python", "Django", "SQL", "Git"})
        # ai_reasoning block must exist (fallback) and not crash
        ai = analysis.get("ai_reasoning")
        self.assertIsNotNone(ai, "Expected ai_reasoning block even when Gemini unavailable.")
        self.assertIn("summary", ai)
        self.assertIn("priority_gaps", ai)
        # Should be deterministic fallback since no real key
        self.assertIn(ai.get("source"), {"deterministic_fallback", "gemini"})
        # Metadata exposes gemini_configured bool without the key
        self.assertIn("gemini_configured", body["metadata"])
        self.assertIsInstance(body["metadata"]["gemini_configured"], bool)
        self.assertIn("ai_enabled", body["metadata"])

    def test_17_health_endpoint_reports_gemini(self):
        res = self.client.get("/api/gap-analysis/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("gemini_configured", body)
        self.assertIn("gemini_model", body)
        self.assertIsInstance(body["gemini_configured"], bool)
        # NEVER include the actual key anywhere
        response_str = json.dumps(body)
        self.assertNotIn("ABcdef", response_str)
        self.assertNotIn("GEMINI_API_KEY", response_str)


if __name__ == "__main__":
    unittest.main()
