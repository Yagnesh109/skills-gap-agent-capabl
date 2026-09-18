import json
import os
from dotenv import load_dotenv
from google import genai
import time
import warnings
warnings.filterwarnings("ignore")

# Automatically loads variables from your backend/.env file
current_dir = os.path.dirname(__file__)
backend_dir = os.path.dirname(current_dir)
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)

# Ensure your .env file has this exact key: GEMINI_API_KEY=your_actual_key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MOCK_LOCAL_JOB_DEMAND = {
    "React": 12,
    "PostgreSQL": 8,
    "FastAPI": 5,
    "Docker": 3,
    "Node.js": 7,
    "Python": 15,
    "SQL": 10
}

def load_courses():
    """Loads the static course catalog."""
    file_path = os.path.join(os.path.dirname(__file__), 'courses.json')
    with open(file_path, 'r') as f:
        return json.load(f)

def calculate_roi_score(course, job_demand):
    """Calculates the Opportunity Score deterministically."""
    jobs_unlocked = 0
    for skill in course.get("skills_taught", []):
        jobs_unlocked += job_demand.get(skill, 0)
    
    if course.get("duration_weeks", 0) == 0:
        return 0, jobs_unlocked
        
    roi = (jobs_unlocked / course["duration_weeks"]) * 10
    return round(roi, 2), jobs_unlocked

def fallback_text(missing_skills, course_title, duration, jobs_unlocked):
    """Provides a safe default string if the API fails during a live demo."""
    return (f"Learning {', '.join(missing_skills)} through '{course_title}' unlocks "
            f"{jobs_unlocked} additional local roles. At only {duration} weeks of study, "
            f"this offers the highest immediate impact on your employability.")


def generate_roi_reasoning(missing_skills, course_title, duration, jobs_unlocked):
    """Calls the Gemini API with a retry mechanism for 503 Server Overload errors."""
    prompt = f"""
    You are an expert Career Strategist.
    The user is missing these skills: {', '.join(missing_skills)}.
    We recommend the course: '{course_title}' which takes {duration} weeks to complete.
    Data shows these skills unlock {jobs_unlocked} local job postings.
    
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

def recommend_training(missing_skills: list):
    """Main execution function for the Training Recommendation Agent."""
    courses = load_courses()
    best_course = None
    highest_roi = -1
    best_jobs_unlocked = 0
    
    for course in courses:
        teaches_missing = any(skill in missing_skills for skill in course.get("skills_taught", []))
        if teaches_missing:
            roi, jobs_unlocked = calculate_roi_score(course, MOCK_LOCAL_JOB_DEMAND)
            if roi > highest_roi:
                highest_roi = roi
                best_course = course
                best_jobs_unlocked = jobs_unlocked
                
    if not best_course:
        return {"error": "No matching courses found for the missing skills."}
        
    roi_statement = generate_roi_reasoning(
        missing_skills=missing_skills,
        course_title=best_course["title"],
        duration=best_course["duration_weeks"],
        jobs_unlocked=best_jobs_unlocked
    )
    
    return {
        "recommendations": [
            {
                "course_name": best_course["title"],
                "provider": best_course["provider"],
                "duration_weeks": best_course["duration_weeks"],
                "roi_score": highest_roi,
                "roi_reasoning": roi_statement,
                "url": best_course.get("url", "")
            }
        ]
    }

if __name__ == "__main__":
    mock_input = {
        "user_name": "Alex",
        "missing_skills": ["React", "PostgreSQL"],
        "target_jobs_analyzed": 15
    }
    
    print("--- Executing ROI Calculation & Modern SDK Generation ---")
    result = recommend_training(mock_input["missing_skills"])
    print(json.dumps(result, indent=2))