import io
import json
import re
from PIL import Image
import google.generativeai as genai

from .config import get_fallback_gemini_models, get_gemini_api_key
from .schemas import UserProfile


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
    """Normalize legacy parser data into the canonical UserProfile shape."""
    normalized = UserProfile().model_dump(mode="python")
    if not isinstance(raw_data, dict):
        return normalized

    personal_info = raw_data.get("personal_info", {})
    if not isinstance(personal_info, dict):
        personal_info = {}
    normalized["name"] = str(raw_data.get("name", personal_info.get("name", "")) or "")
    normalized["email"] = str(raw_data.get("email", personal_info.get("email", "")) or "")
    normalized["phone"] = str(raw_data.get("phone", personal_info.get("phone", "")) or "")
    normalized["location"] = str(raw_data.get("location", personal_info.get("location", "")) or "")
    normalized["target_role"] = str(raw_data.get("target_role", "") or "")

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

    return UserProfile.model_validate(normalized).model_dump(mode="python")


import ast

def extract_json_from_text(text: str) -> dict:
    """Read JSON from Gemini output, repairing common LLM JSON syntax issues."""
    if not text or not isinstance(text, str):
        raise ValueError("Gemini returned an empty response.")

    cleaned = text.strip()

    # 1. Strip markdown fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    else:
        # Extract outermost { ... }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1].strip()

    # 2. Try standard json.loads
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 3. Repair common JSON issues
    repaired = cleaned
    # Remove trailing commas: , } -> } and , ] -> ]
    repaired = re.sub(r",\s*([\}\]])", r"\1", repaired)
    # Fix single quotes around keys: 'key': -> "key":
    repaired = re.sub(r"'\s*([^']+?)\s*'\s*:", r'"\1":', repaired)
    # Fix single quotes around string values: : 'value' -> : "value"
    repaired = re.sub(r":\s*'([^']*?)'", r': "\1"', repaired)

    try:
        return json.loads(repaired)
    except Exception:
        pass

    # 4. Try ast.literal_eval for python-style dicts
    try:
        val = ast.literal_eval(cleaned)
        if isinstance(val, dict):
            return val
    except Exception:
        pass

    try:
        val = ast.literal_eval(repaired)
        if isinstance(val, dict):
            return val
    except Exception as exc:
        raise ValueError(f"Could not parse valid JSON from Gemini output: {exc}") from exc


import time

def extract_fallback_profile_from_text(text: str) -> dict:
    """Deterministic local regex parser when Gemini API hits rate/quota limit (429)."""
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    phone_match = re.search(r"\(?\+?\d{1,3}\)?[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}", text)

    common_skills = [
        "Python", "JavaScript", "TypeScript", "React", "Node.js", "Express",
        "HTML", "CSS", "SQL", "PostgreSQL", "MongoDB", "Docker", "Kubernetes",
        "AWS", "FastAPI", "Django", "Git", "Java", "C++", "C#", "Machine Learning",
        "Deep Learning", "NLP", "REST API", "Tailwind", "Bootstrap", "Redux"
    ]
    detected_skills = [skill for skill in common_skills if re.search(r"\b" + re.escape(skill) + r"\b", text, re.I)]

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name = lines[0] if lines else ""
    if name and ("resume" in name.lower() or "curriculum" in name.lower() or len(name) > 50):
        name = ""

    profile = UserProfile(
        name=name[:50],
        email=email_match.group(0) if email_match else "",
        phone=phone_match.group(0) if phone_match else "",
    ).model_dump(mode="python")
    profile["skills"] = detected_skills

    # Heuristic extraction for education when AI is offline/quota reached
    edu_keywords = ["b.tech", "b.e", "bachelor", "master", "m.tech", "degree", "university", "college", "diploma", "computer science"]
    education_list = []
    for line in lines:
        if any(kw in line.lower() for kw in edu_keywords):
            education_list.append({
                "degree": line[:80],
                "field": "",
                "institution": "",
                "graduation_year": ""
            })
            if len(education_list) >= 2:
                break
    profile["education"] = education_list

    # Heuristic extraction for experience when AI is offline/quota reached
    role_keywords = ["developer", "engineer", "intern", "architect", "lead", "specialist", "consultant", "analyst"]
    experience_list = []
    for line in lines:
        if any(kw in line.lower() for kw in role_keywords) and line != name:
            experience_list.append({
                "company": "",
                "role": line[:80],
                "duration": "",
                "responsibilities": []
            })
            if len(experience_list) >= 2:
                break
    profile["experience"] = experience_list

    return UserProfile.model_validate(profile).model_dump(mode="python")


def parse_resume_with_gemini(resume_text: str) -> dict:
    """Send extracted text to Gemini and force a structured JSON response."""
    api_key = get_gemini_api_key()
    if not api_key or api_key.startswith("your_") or api_key == "dummy_test_key":
        return extract_fallback_profile_from_text(resume_text)

    try:
        genai.configure(api_key=api_key)
    except Exception:
        return extract_fallback_profile_from_text(resume_text)

    candidate_models = get_fallback_gemini_models()
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

    last_error = None
    for model_name in candidate_models:
        for attempt in range(3):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 1500,
                        "response_mime_type": "application/json",
                    },
                )
                result = response.text
                profile = extract_json_from_text(result)
                return normalize_profile_dict(profile)
            except Exception as exc:
                err_msg = str(exc)
                last_error = exc
                if "429" in err_msg or "quota" in err_msg.lower() or "resourceexhausted" in err_msg.lower():
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    break
                if "api_key_invalid" in err_msg.lower() or "api key not valid" in err_msg.lower() or "invalid api key" in err_msg.lower():
                    break
                if "json" in err_msg.lower() or "parse" in err_msg.lower() or "double quotes" in err_msg.lower():
                    if attempt < 2:
                        continue
                    break
                # On unexpected error, break to fallback
                break

    # Fallback to local regex parser on any API failure or JSON parsing exception
    return extract_fallback_profile_from_text(resume_text)



def parse_resume_image_with_gemini(image_bytes: bytes, filename: str = "") -> dict:
    """Send resume image directly to Gemini 3.6 Multimodal Vision for parsing."""
    if not image_bytes:
        raise ValueError("Image file is empty.")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    except Exception as exc:
        raise ValueError(f"Invalid image file: {exc}") from exc

    api_key = get_gemini_api_key()
    if not api_key or api_key.startswith("your_") or api_key == "dummy_test_key":
        return UserProfile().model_dump(mode="python")

    try:
        genai.configure(api_key=api_key)
    except Exception:
        return UserProfile().model_dump(mode="python")

    candidate_models = get_fallback_gemini_models()
    prompt = """
    Extract the candidate's profile from the attached resume image.
    Return valid JSON only. Use this exact structure:
    {
      "personal_info": {"name": "", "email": "", "phone": "", "location": ""},
      "education": [{"degree": "", "field": "", "institution": "", "graduation_year": ""}],
      "skills": [],
      "experience": [{"company": "", "role": "", "duration": "", "responsibilities": []}],
      "projects": [{"name": "", "description": "", "technologies": []}],
      "certifications": [],
      "interests": []
    }

    Rules:
    - Perform full OCR and visual extraction on the image text.
    - Do not invent information that is not present in the image.
    - Use empty strings/arrays when information is missing.
    - Normalize obvious skill variations such as 'React JS' -> 'React', 'Mongo DB' -> 'MongoDB'.
    - Return valid JSON only.
    - Do not include markdown fences or explanations.
    """

    last_error = None
    for model_name in candidate_models:
        for attempt in range(3):
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    [image, prompt],
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 1500,
                        "response_mime_type": "application/json",
                    },
                )
                result = response.text
                profile = extract_json_from_text(result)
                return normalize_profile_dict(profile)
            except Exception as exc:
                err_msg = str(exc)
                last_error = exc
                if "429" in err_msg or "quota" in err_msg.lower() or "resourceexhausted" in err_msg.lower():
                    if attempt < 2:
                        time.sleep(2 * (attempt + 1))
                        continue
                    break
                if "api_key_invalid" in err_msg.lower() or "api key not valid" in err_msg.lower() or "invalid api key" in err_msg.lower():
                    break
                if "json" in err_msg.lower() or "parse" in err_msg.lower() or "double quotes" in err_msg.lower():
                    if attempt < 2:
                        continue
                    break
                break

    return UserProfile().model_dump(mode="python")


