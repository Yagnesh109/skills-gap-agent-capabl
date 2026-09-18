import json
import re
from copy import deepcopy

import google.generativeai as genai

from .config import get_gemini_api_key, get_gemini_model
from .schemas import EMPTY_PROFILE


SKILL_NORMALIZATION = {
    "react js": "React",
    "reactjs": "React",
    "node js": "Node.js",
    "nodejs": "Node.js",
    "mongo db": "MongoDB",
    "mongodb": "MongoDB",
    "postgres sql": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sql": "SQL",
    "java script": "JavaScript",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "python": "Python",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "natural language processing": "NLP",
    "rest api": "REST API",
    "restapis": "REST API",
}


def normalize_skill(skill: str) -> str:
    cleaned = re.sub(r"\s+", " ", (skill or "").strip())
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    if lowered in SKILL_NORMALIZATION:
        return SKILL_NORMALIZATION[lowered]

    for key, value in SKILL_NORMALIZATION.items():
        if key in lowered:
            return value

    # Keep the original text but remove obvious extra spacing.
    return cleaned


def normalize_profile_dict(raw_data: dict) -> dict:
    """Ensure response always matches the defined structure and defaults."""
    normalized = deepcopy(EMPTY_PROFILE)
    if not isinstance(raw_data, dict):
        return normalized

    personal_info = raw_data.get("personal_info", {})
    normalized["personal_info"] = {
        "name": str(personal_info.get("name", "") or ""),
        "email": str(personal_info.get("email", "") or ""),
        "phone": str(personal_info.get("phone", "") or ""),
        "location": str(personal_info.get("location", "") or ""),
    }

    normalized["education"] = [
        {
            "degree": str(item.get("degree", "") or ""),
            "field": str(item.get("field", "") or ""),
            "institution": str(item.get("institution", "") or ""),
            "graduation_year": str(item.get("graduation_year", "") or ""),
        }
        for item in raw_data.get("education", [])
        if isinstance(item, dict)
    ]

    raw_skills = raw_data.get("skills", [])
    normalized["skills"] = [
        normalize_skill(skill) for skill in raw_skills if isinstance(skill, str) and normalize_skill(skill)
    ]

    normalized["experience"] = [
        {
            "company": str(item.get("company", "") or ""),
            "role": str(item.get("role", "") or ""),
            "duration": str(item.get("duration", "") or ""),
            "responsibilities": [
                str(resp) for resp in (item.get("responsibilities", []) or []) if isinstance(resp, str)
            ],
        }
        for item in raw_data.get("experience", [])
        if isinstance(item, dict)
    ]

    normalized["projects"] = [
        {
            "name": str(item.get("name", "") or ""),
            "description": str(item.get("description", "") or ""),
            "technologies": [
                normalize_skill(skill)
                for skill in (item.get("technologies", []) or [])
                if isinstance(skill, str) and normalize_skill(skill)
            ],
        }
        for item in raw_data.get("projects", [])
        if isinstance(item, dict)
    ]

    normalized["certifications"] = [
        str(item) for item in (raw_data.get("certifications", []) or []) if isinstance(item, str)
    ]
    normalized["interests"] = [
        str(item) for item in (raw_data.get("interests", []) or []) if isinstance(item, str)
    ]

    return normalized


def extract_json_from_text(text: str) -> dict:
    """Read JSON from Gemini output, even if wrapped in markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = re.sub(r"^json\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

    if not cleaned:
        raise ValueError("Gemini returned an empty response.")

    return json.loads(cleaned)


def parse_resume_with_gemini(resume_text: str) -> dict:
    """Send extracted text to Gemini and force a structured JSON response."""
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(get_gemini_model())
    prompt = f"""
    Extract the candidate's profile from the following resume text.
    Return valid JSON only. Use this exact structure:
    {{
      "personal_info": {{"name": "", "email": "", "phone": "", "location": ""}},
      "education": [{{"degree": "", "field": "", "institution": "", "graduation_year": ""}}],
      "skills": [],
      "experience": [{{"company": "", "role": "", "duration": "", "responsibilities": []}}],
      "projects": [{{"name": "", "description": "", "technologies": []}}],
      "certifications": [],
      "interests": []
    }}

    Rules:
    - Do not invent information that is not present in the resume.
    - Use empty strings/arrays when information is missing.
    - Normalize obvious skill variations such as 'React JS' -> 'React', 'Mongo DB' -> 'MongoDB'.
    - Return valid JSON only.
    - Do not include markdown fences or explanations.

    Resume text:
    {resume_text}
    """

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.1,
                "response_mime_type": "application/json",
            },
        )
        result = response.text
        profile = extract_json_from_text(result)
        return normalize_profile_dict(profile)
    except Exception as exc:  # pragma: no cover - external API path
        raise ValueError(f"Gemini API request failed: {exc}") from exc
