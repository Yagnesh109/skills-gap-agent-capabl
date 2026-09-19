import re
import html
from typing import List, Set

try:
    from .normalizer import SKILL_ALIASES, normalize_skill
except (ImportError, ValueError):
    from services.normalizer import SKILL_ALIASES, normalize_skill


# Canonical skill display mappings for extracted skills
CANONICAL_DISPLAY_NAMES = {
    "python": "Python",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "react": "React",
    "next.js": "Next.js",
    "javascript": "JavaScript",
    "typescript": "TypeScript",
    "nodejs": "Node.js",
    "express.js": "Express.js",
    "html": "HTML",
    "css": "CSS",
    "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "azure": "Azure",
    "gcp": "GCP",
    "git": "Git",
    "ci/cd": "CI/CD",
    "rest api": "REST API",
    "graphql": "GraphQL",
    "java": "Java",
    "spring boot": "Spring Boot",
    "c++": "C++",
    "c": "C",
    "go": "Go",
    "machine learning": "Machine Learning",
    "deep learning": "Deep Learning",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "NLP",
    "computer vision": "Computer Vision",
    "generative ai": "Generative AI",
    "llms": "LLMs",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scikit-learn": "Scikit-learn",
    "powerbi": "PowerBI",
    "tableau": "Tableau",
    "excel": "Excel",
    "data structures": "Data Structures",
    "algorithms": "Algorithms",
    "object-oriented programming": "OOP",
    "selenium": "Selenium",
    "pytest": "PyTest",
    "kafka": "Kafka",
    "airflow": "Airflow",
    "apache spark": "Apache Spark",
    "microservices": "Microservices"
}


def clean_html_text(raw_text: str) -> str:
    """Removes HTML tags, entity references, and excess whitespaces."""
    if not raw_text:
        return ""
    # Unescape HTML entities (&amp;, &nbsp;, etc.)
    text = html.unescape(raw_text)
    # Remove HTML tags (<p>, <br>, <b>, etc.)
    text = re.sub(r'<[^>]+>', ' ', text)
    # Replace non-breaking spaces and redundant whitespaces
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _build_skill_patterns():
    """Builds compiled regex patterns for vocabulary lookup."""
    patterns = []
    # Sort aliases by length descending to match multi-word phrases first (e.g. 'spring boot' before 'spring')
    sorted_aliases = sorted(SKILL_ALIASES.keys(), key=lambda k: len(k), reverse=True)
    
    for alias in sorted_aliases:
        canonical = SKILL_ALIASES[alias]
        # Handle special characters like c++, c#, .js, / in regex
        escaped = re.escape(alias)
        # Ensure word boundaries (with handling for symbols like ++ or #)
        if alias in ("c++", "c#", "ci/cd"):
            pattern = re.compile(rf'(?:^|[\s,;./(]){escaped}(?:[\s,;./)]|$)', re.IGNORECASE)
        else:
            pattern = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
        patterns.append((pattern, canonical))
    return patterns


_SKILL_PATTERNS = _build_skill_patterns()


def extract_skills_from_text(text: str) -> List[str]:
    """
    Deterministically extracts technical skills from a job title and description.
    Uses dictionary pattern matching with word boundaries.
    Returns clean, deduplicated list of display skill names.
    """
    if not text:
        return []

    cleaned = clean_html_text(text)
    matched_canonicals: Set[str] = set()

    for pattern, canonical in _SKILL_PATTERNS:
        if pattern.search(cleaned):
            matched_canonicals.add(canonical)

    # Format into user-friendly display casing
    display_skills = [
        CANONICAL_DISPLAY_NAMES.get(c, c.title())
        for c in matched_canonicals
    ]

    return sorted(display_skills)
