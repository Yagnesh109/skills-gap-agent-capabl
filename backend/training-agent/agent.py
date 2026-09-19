import json
import os
import time
import warnings
from dotenv import load_dotenv
from google import genai

warnings.filterwarnings("ignore")

# Automatically loads variables from your backend/.env file
current_dir = os.path.dirname(__file__)
backend_dir = os.path.dirname(current_dir)
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def load_courses():
    """Loads the course catalog (Can be swapped with MCP Client)."""
    file_path = os.path.join(os.path.dirname(__file__), 'courses.json')
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: courses.json not found in the directory.")
        return []

def calculate_dynamic_demand(top_job_matches):
    """Dynamically calculates skill demand based on the real jobs found in the previous step."""
    demand = {}
    if not top_job_matches:
        return demand
        
    for job in top_job_matches:
        # Assuming your Job Matcher returns a list of 'required_skills' for each job
        for skill in job.get("required_skills", []):
            demand[skill] = demand.get(skill, 0) + 1
    return demand

def _match_skill(s1: str, s2: str) -> bool:
    """Case-insensitive flexible skill matching (supports exact, substring, or token overlap)."""
    if not s1 or not s2:
        return False
    k1 = s1.strip().lower()
    k2 = s2.strip().lower()
    if k1 == k2 or k1 in k2 or k2 in k1:
        return True
    tokens1 = set(k1.replace("-", " ").replace(".", " ").split())
    tokens2 = set(k2.replace("-", " ").replace(".", " ").split())
    return bool(tokens1 & tokens2 and not tokens1.isdisjoint(tokens2 - {"development", "engineer", "framework", "programming"}))

def calculate_roi_score(course, job_demand):
    """Calculates the Opportunity Score based on local market demand vs time invested."""
    jobs_unlocked = 0
    for skill in course.get("skills_taught", []):
        for demand_skill, count in job_demand.items():
            if _match_skill(skill, demand_skill):
                jobs_unlocked += count
    
    duration = course.get("duration_weeks", 0) or 4
    # ROI Formula: (Jobs Unlocked / Weeks of Study) * 10
    roi = (jobs_unlocked / duration) * 10 if jobs_unlocked > 0 else (10.0 / duration)
    return round(roi, 2), max(jobs_unlocked, 1)

def fallback_text(missing_skills, course_title, duration, jobs_unlocked):
    """Provides a concise, high-impact ROI explanation."""
    skill_names = ", ".join(missing_skills[:3]) if missing_skills else "target technical skills"
    return (f"Mastering {skill_names} via '{course_title}' directly closes your primary market gap, "
            f"unlocking +{jobs_unlocked} target job opportunities in {duration} weeks of focused learning.")

def generate_roi_reasoning(missing_skills, course_title, duration, jobs_unlocked):
    """Returns concise ROI reasoning with Gemini or fast deterministic fallback."""
    return fallback_text(missing_skills, course_title, duration, jobs_unlocked)

def recommend_training(
    missing_skills: list,
    top_job_matches: list = None,
    user_profile: dict = None,
    opportunity_analysis: dict = None,
):
    """Main execution function for the Training Recommendation Agent."""
    courses = load_courses()
    if not courses:
        return {"recommendations": [], "error": "No courses found."}
    
    # 1. Calculate dynamic demand from actual job postings (fallback to mock if empty)
    if top_job_matches:
        job_demand = calculate_dynamic_demand(top_job_matches)
    else:
        job_demand = {"React": 12, "PostgreSQL": 8, "FastAPI": 5, "Docker": 4, "Node.js": 7, "Python": 15, "SQL": 10, "C++": 6, "Java": 9, "AWS": 8}

    # Ensure missing_skills is a clean list
    clean_missing = [s for s in (missing_skills or []) if isinstance(s, str) and s.strip()]
    
    # 2. Score and sort matching courses
    scored_courses = []
    for course in courses:
        skills_taught = course.get("skills_taught", [])
        
        # Check if course matches any missing skill
        match_count = sum(
            1 for m in clean_missing
            if any(_match_skill(m, t) for t in skills_taught)
        )
        
        roi, jobs_unlocked = calculate_roi_score(course, job_demand)
        if match_count > 0:
            # Boost score based on number of missing skills covered
            total_score = roi + (match_count * 50)
            scored_courses.append((total_score, course, jobs_unlocked))

    # If no exact match on missing skills, rank all courses by market demand
    if not scored_courses:
        for course in courses:
            roi, jobs_unlocked = calculate_roi_score(course, job_demand)
            scored_courses.append((roi, course, jobs_unlocked))

    scored_courses.sort(key=lambda x: x[0], reverse=True)
    
    best_score, best_course, best_jobs = scored_courses[0]
    
    # 3. Generate the reasoning
    roi_statement = generate_roi_reasoning(
        missing_skills=clean_missing,
        course_title=best_course["title"],
        duration=best_course.get("duration_weeks", 4),
        jobs_unlocked=best_jobs
    )
    
    # 4. Return structured recommendations
    return {
        "recommendations": [
            {
                "course_name": best_course["title"],
                "provider": best_course.get("provider", "Online Course"),
                "duration_weeks": best_course.get("duration_weeks", 4),
                "roi_score": round(best_score, 2),
                "jobs_unlocked": best_jobs,
                "roi_reasoning": roi_statement,
                "url": best_course.get("url", "")
            }
        ]
    }


if __name__ == "__main__":
    # Mock data to test the agent in isolation before connecting to LangGraph
    mock_missing_skills = ["PostgreSQL", "SQL"]
    mock_job_matches = [
        {"title": "Backend Engineer", "required_skills": ["Python", "PostgreSQL", "Docker"]},
        {"title": "Data Analyst", "required_skills": ["SQL", "Excel", "Python"]},
        {"title": "Database Admin", "required_skills": ["PostgreSQL", "Linux", "SQL"]}
    ]
    
    print("--- Executing ROI Calculation & Modern SDK Generation ---")
    result = recommend_training(missing_skills=mock_missing_skills, top_job_matches=mock_job_matches)
    print(json.dumps(result, indent=2))