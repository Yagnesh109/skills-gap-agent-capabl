import re
from typing import Dict, List, Set, Iterable


# Extensible rule-based alias mapping.
# Maps normalized lowercase variations to a standard canonical identifier.
SKILL_ALIASES: Dict[str, str] = {
    # React variants
    "react": "react",
    "react.js": "react",
    "reactjs": "react",
    "react js": "react",
    "react framework": "react",

    # Python variants
    "python": "python",
    "python 3": "python",
    "python3": "python",
    "python 3.x": "python",
    "python programming": "python",

    # JavaScript variants
    "javascript": "javascript",
    "js": "javascript",
    "ecmascript": "javascript",
    "vanilla js": "javascript",

    # TypeScript variants
    "typescript": "typescript",
    "ts": "typescript",

    # Node.js variants
    "node": "nodejs",
    "node.js": "nodejs",
    "nodejs": "nodejs",
    "node js": "nodejs",

    # SQL / Database variants
    "sql": "sql",
    "structured query language": "sql",
    "rdbms": "sql",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "postgre sql": "postgresql",
    "mysql": "mysql",
    "my sql": "mysql",
    "mongo": "mongodb",
    "mongodb": "mongodb",

    # Web & API variants
    "rest": "rest api",
    "rest api": "rest api",
    "restful api": "rest api",
    "rest apis": "rest api",
    "restful apis": "rest api",
    "graphql": "graphql",
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "tailwind": "tailwind css",
    "tailwind css": "tailwind css",
    "bootstrap": "bootstrap",

    # Frameworks
    "fastapi": "fastapi",
    "fast api": "fastapi",
    "django": "django",
    "flask": "flask",
    "spring": "spring boot",
    "spring boot": "spring boot",
    "springboot": "spring boot",
    "next": "next.js",
    "next.js": "next.js",
    "nextjs": "next.js",
    "express": "express.js",
    "express.js": "express.js",
    "expressjs": "express.js",

    # DevOps & Cloud
    "docker": "docker",
    "docker containers": "docker",
    "containerization": "docker",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "aws",
    "amazon web services": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "git": "git",
    "github": "github",
    "gitlab": "gitlab",
    "version control": "version control",
    "ci/cd": "ci/cd",
    "cicd": "ci/cd",

    # Data Science & AI
    "ml": "machine learning",
    "machine learning": "machine learning",
    "dl": "deep learning",
    "deep learning": "deep learning",
    "ai": "artificial intelligence",
    "artificial intelligence": "artificial intelligence",
    "nlp": "nlp",
    "natural language processing": "nlp",
    "computer vision": "computer vision",
    "cv": "computer vision",
    "genai": "generative ai",
    "generative ai": "generative ai",
    "llm": "llms",
    "llms": "llms",
    "large language models": "llms",
    "pytorch": "pytorch",
    "torch": "pytorch",
    "tensorflow": "tensorflow",
    "tf": "tensorflow",
    "pandas": "pandas",
    "numpy": "numpy",
    "scikit-learn": "scikit-learn",
    "scikitlearn": "scikit-learn",
    "sklearn": "scikit-learn",
    "powerbi": "powerbi",
    "power bi": "powerbi",
    "tableau": "tableau",
    "excel": "excel",
    "ms excel": "excel",

    # Core Software Engineering
    "dsa": "data structures",
    "data structures": "data structures",
    "algorithms": "algorithms",
    "oop": "object-oriented programming",
    "oops": "object-oriented programming",
    "object-oriented programming": "object-oriented programming",
    "c++": "c++",
    "cpp": "c++",
    "c": "c",
    "golang": "go",
    "go": "go",
    "java": "java",
    "core java": "java",
}


def normalize_skill(skill: str) -> str:
    """
    Normalizes a single skill string into its canonical lowercase representation.
    
    Examples:
        'React.js' -> 'react'
        'Python 3' -> 'python'
        'JS' -> 'javascript'
        'Node.js' -> 'nodejs'
    """
    if not skill or not isinstance(skill, str):
        return ""

    # Strip and convert to lower case
    cleaned = skill.strip().lower()

    # Remove enclosing quotes and redundant whitespaces
    cleaned = re.sub(r'[\'"]', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Check direct dictionary mapping
    if cleaned in SKILL_ALIASES:
        return SKILL_ALIASES[cleaned]

    # Handle common suffixes like 'framework', 'library', 'development'
    simplified = re.sub(r'\b(development|developer|programming|framework|library|technologies|technology)\b', '', cleaned).strip()
    if simplified in SKILL_ALIASES:
        return SKILL_ALIASES[simplified]

    return cleaned


def normalize_skills(skills: Iterable[str]) -> List[str]:
    """
    Normalizes an iterable of skills, returning unique non-empty canonical strings.
    """
    seen: Set[str] = set()
    result: List[str] = []
    for s in skills:
        norm = normalize_skill(s)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def build_skill_map(skills: Iterable[str]) -> Dict[str, str]:
    """
    Builds a lookup mapping from normalized skill to original casing.
    Returns {normalized_skill: original_display_skill}
    """
    skill_map = {}
    for s in skills:
        norm = normalize_skill(s)
        if norm and norm not in skill_map:
            skill_map[norm] = s.strip()
    return skill_map
