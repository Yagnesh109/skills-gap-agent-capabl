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

try:
    from .time_to_ready import calculate_time_to_ready, load_courses as ttr_load_courses
except (ImportError, ValueError):
    try:
        from training_agent.time_to_ready import calculate_time_to_ready, load_courses as ttr_load_courses
    except (ImportError, ValueError):
        import importlib
        ttr_mod = importlib.import_module("training-agent.time_to_ready")
        calculate_time_to_ready = ttr_mod.calculate_time_to_ready
        ttr_load_courses = ttr_mod.load_courses


def load_courses():
    """Loads the course catalog (Can be swapped with MCP Client)."""
    return ttr_load_courses()


def calculate_dynamic_demand(top_job_matches):
    """Dynamically calculates skill demand based on the real jobs found in the previous step."""
    demand = {}
    if not top_job_matches:
        return demand
        
    for job in top_job_matches:
        for skill in job.get("required_skills", []):
            demand[skill] = demand.get(skill, 0) + 1
    return demand


def calculate_roi_score(course, job_demand):
    """Calculates the Opportunity Score based on local market demand vs time invested."""
    jobs_unlocked = 0
    for skill in course.get("skills_taught", []):
        skill_lower = skill.lower()
        for demand_skill, count in job_demand.items():
            if demand_skill.lower() == skill_lower:
                jobs_unlocked += count
    
    if course.get("duration_weeks", 0) == 0:
        return 0, jobs_unlocked
        
    roi = (jobs_unlocked / course["duration_weeks"]) * 10
    return round(roi, 2), jobs_unlocked


def fallback_text(missing_skills, course_title, duration, jobs_unlocked):
    """Provides a safe default string if the API fails during a live demo."""
    return (f"Learning {', '.join(missing_skills)} through '{course_title}' unlocks "
            f"{jobs_unlocked} additional roles in the Solapur tech market. At only {duration} weeks of study, "
            f"this offers the highest immediate impact on your employability.")


def generate_roi_reasoning(missing_skills, course_title, duration, jobs_unlocked):
    """Calls the Gemini API with a retry mechanism for 503 Server Overload errors."""
    prompt = f"""
    You are an expert Career Strategist analyzing the local tech market.
    The user is missing these skills: {', '.join(missing_skills)}.
    We recommend the course: '{course_title}' which takes {duration} weeks to complete.
    Data shows acquiring these skills unlocks {jobs_unlocked} local job postings.
    
    Write a 2-sentence "ROI Reasoning" statement directly to the user. Explain exactly why this 
    specific course is the most efficient use of their time based on the local job market. 
    Be quantitative, persuasive, and do not use generic fluff.
    """

    if not GEMINI_API_KEY:
        print("Warning: GEMINI_API_KEY not found in environment variables.")
        return fallback_text(missing_skills, course_title, duration, jobs_unlocked)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            chat = client.chats.create(model='gemini-3.5-flash')
            response = chat.send_message(prompt)
            
            return response.text.strip()
        except Exception as e:
            if "503" in str(e) and attempt < max_retries - 1:
                print(f"API busy (503). Retrying in 2 seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"LLM API Error: {e}")
                return fallback_text(missing_skills, course_title, duration, jobs_unlocked)


def recommend_training(
    missing_skills: list,
    top_job_matches: list = None,
    user_profile: dict = None,
    opportunity_analysis: dict = None,
    free_only: bool = False,
):
    """Main execution function for the Training Recommendation Agent.
    
    Now includes Time-to-Ready calculation for the missing skills.
    """
    courses = load_courses()
    candidate_courses = [
        course for course in courses
        if not free_only or bool(course.get("is_free", False))
    ]
    
    # Calculate Time-to-Ready for the missing skills
    time_to_ready = calculate_time_to_ready(
        missing_skills=missing_skills,
        courses=courses,
        free_only=free_only,
    )
    
    # 1. Calculate dynamic demand from actual job postings (fallback to mock if empty)
    if top_job_matches:
        job_demand = calculate_dynamic_demand(top_job_matches)
    else:
        job_demand = {"React": 12, "PostgreSQL": 8, "FastAPI": 5, "Docker": 3, "Node.js": 7, "Python": 15, "SQL": 10}

    best_course = None
    highest_roi = -1
    best_jobs_unlocked = 0
    
    # 2. Find the course with the highest ROI (existing logic preserved)
    for course in candidate_courses:
        teaches_missing = any(skill.lower() in [s.lower() for s in course.get("skills_taught", [])] for skill in missing_skills)
        
        if teaches_missing:
            roi, jobs_unlocked = calculate_roi_score(course, job_demand)
            if roi > highest_roi:
                highest_roi = roi
                best_course = course
                best_jobs_unlocked = jobs_unlocked
                
    if not best_course:
        return {
            "recommendations": [], 
            "error": "No matching courses found for the missing skills.",
            "time_to_ready": time_to_ready
        }
        
    # 3. Generate the Gemini reasoning
    roi_statement = generate_roi_reasoning(
        missing_skills=missing_skills,
        course_title=best_course["title"],
        duration=best_course["duration_weeks"],
        jobs_unlocked=best_jobs_unlocked
    )
    
    # 4. Return structured data ready for LangGraph (preserving existing format + time_to_ready)
    return {
        "recommendations": [
            {
                "course_name": best_course["title"],
                "provider": best_course["provider"],
                "duration_weeks": best_course["duration_weeks"],
                "roi_score": highest_roi,
                "jobs_unlocked": best_jobs_unlocked,
                "roi_reasoning": roi_statement,
                "url": best_course.get("url", ""),
                "price_inr": best_course.get("price_inr", 0),
                "is_free": best_course.get("is_free", False),
            }
        ],
        "time_to_ready": time_to_ready,
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
