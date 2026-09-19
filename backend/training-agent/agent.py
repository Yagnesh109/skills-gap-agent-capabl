import json
import os
import time
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

# Automatically loads variables from your backend/.env file
current_dir = os.path.dirname(__file__)
backend_dir = os.path.dirname(current_dir)
env_path = os.path.join(backend_dir, '.env')
load_dotenv(env_path)


def get_training_api_key() -> str:
    """Return dedicated training API key or fallback."""
    return (
        os.getenv("GEMINI_API_KEY_TRAINING")
        or os.getenv("GEMINI_API_KEY_3")
        or os.getenv("GEMINI_API_KEY", "")
    ).strip()


MOCK_LOCAL_JOB_DEMAND = {
    "React": 12,
    "PostgreSQL": 8,
    "FastAPI": 5,
    "Docker": 3,
    "Node.js": 7,
    "Python": 15,
    "SQL": 10,
    "JavaScript": 14,
    "TypeScript": 9,
    "MongoDB": 6,
    "AWS": 8,
    "Kubernetes": 4,
    "HTML": 10,
    "CSS": 10,
    "Git": 12,
    "Machine Learning": 7,
}


def load_courses():
    """Loads the static course catalog."""
    file_path = os.path.join(os.path.dirname(__file__), 'courses.json')
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_roi_score(course, job_demand):
    """Calculates the Opportunity Score deterministically."""
    jobs_unlocked = 0
    for skill in course.get("skills_taught", []):
        jobs_unlocked += job_demand.get(skill, 2)
    
    if course.get("duration_weeks", 0) == 0:
        return 0, jobs_unlocked
        
    roi = (jobs_unlocked / course["duration_weeks"]) * 10
    return round(roi, 2), jobs_unlocked


def fallback_text(missing_skills, course_title, duration, jobs_unlocked):
    """Provides a safe default string if the API fails during a live demo."""
    skills_str = ", ".join(missing_skills) if missing_skills else "key technical skills"
    return (f"Learning {skills_str} through '{course_title}' unlocks "
            f"approximately {jobs_unlocked} additional local job roles. At {duration} weeks of study, "
            f"this provides a high-ROI boost to your overall profile marketability.")


def generate_roi_reasoning(missing_skills, course_title, duration, jobs_unlocked):
    """Calls the Gemini API (gemini-3.6-flash) with fallback."""
    api_key = get_training_api_key()
    if not api_key or api_key.startswith("your_") or api_key == "dummy_test_key":
        return fallback_text(missing_skills, course_title, duration, jobs_unlocked)

    prompt = f"""
    You are an expert Career Strategist.
    The candidate is missing these skills: {', '.join(missing_skills)}.
    We recommend the course: '{course_title}' which takes {duration} weeks to complete.
    Data shows these skills unlock {jobs_unlocked} local job postings.
    
    Write a concise 2-sentence "ROI Reasoning" statement directly to the user. Explain why this 
    specific course is the most efficient use of their time based on current job market demand. 
    Be quantitative and persuasive.
    """

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        print(f"Training Gemini API Error: {e}")

    return fallback_text(missing_skills, course_title, duration, jobs_unlocked)


def recommend_training(missing_skills: list, top_k: int = 5):
    """Main execution function for the Training Recommendation Agent."""
    courses = load_courses()
    
    # Normalize missing skills for matching
    norm_missing = [s.strip().lower() for s in missing_skills if s and str(s).strip()]
    
    scored_courses = []
    for course in courses:
        taught = course.get("skills_taught", [])
        matched = [s for s in taught if s.strip().lower() in norm_missing or any(m in s.strip().lower() for m in norm_missing)]
        
        if not matched:
            matched = [s for s in taught if any(s.strip().lower() in m for m in norm_missing)]

        if matched or not norm_missing:
            roi, jobs_unlocked = calculate_roi_score(course, MOCK_LOCAL_JOB_DEMAND)
            scored_courses.append({
                "course": course,
                "roi": roi,
                "jobs_unlocked": jobs_unlocked,
                "matched_skills": list(set(matched)) if matched else course.get("skills_taught", [])[:2]
            })

    scored_courses.sort(key=lambda x: x["roi"], reverse=True)
    top_candidates = scored_courses[:top_k]

    if not top_candidates:
        for course in courses[:top_k]:
            roi, jobs_unlocked = calculate_roi_score(course, MOCK_LOCAL_JOB_DEMAND)
            top_candidates.append({
                "course": course,
                "roi": roi,
                "jobs_unlocked": jobs_unlocked,
                "matched_skills": course.get("skills_taught", [])[:2]
            })

    recommendations = []
    for item in top_candidates:
        c = item["course"]
        matched_for_course = item["matched_skills"]
        roi_statement = generate_roi_reasoning(
            missing_skills=matched_for_course,
            course_title=c["title"],
            duration=c.get("duration_weeks", 4),
            jobs_unlocked=item["jobs_unlocked"]
        )

        recommendations.append({
            "course_id": c.get("course_id", ""),
            "course_name": c["title"],
            "provider": c.get("provider", "Online Provider"),
            "skills_taught": c.get("skills_taught", []),
            "matched_missing_skills": matched_for_course,
            "duration_weeks": c.get("duration_weeks", 4),
            "difficulty": c.get("difficulty", "Intermediate"),
            "roi_score": item["roi"],
            "jobs_unlocked": item["jobs_unlocked"],
            "roi_reasoning": roi_statement,
            "url": c.get("url", "#")
        })

    return {
        "missing_skills_queried": missing_skills,
        "recommendations_count": len(recommendations),
        "recommendations": recommendations
    }


if __name__ == "__main__":
    mock_input = {
        "user_name": "Alex",
        "missing_skills": ["React", "PostgreSQL"],
        "target_jobs_analyzed": 15
    }
    
    print("--- Executing ROI Calculation & Training Recommendation Agent ---")
    result = recommend_training(mock_input["missing_skills"])
    print(json.dumps(result, indent=2))