from fastmcp import FastMCP
import json
import os

# 1. Initialize the MCP Server
mcp = FastMCP("Local Course Catalog Server")

def get_local_courses():
    """Helper to load the courses from the JSON file."""
    file_path = os.path.join(os.path.dirname(__file__), 'courses.json')
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# 2. Define the tool using the @mcp.tool decorator
@mcp.tool()
def search_courses(skill_query: str, limit: int = 3) -> str:
    """
    Searches the internal learning management system (NPTEL, Infosys Springboard, etc.)
    for courses matching a specific skill. Returns a structured JSON summary.
    """
    all_courses = get_local_courses()
    query_lower = skill_query.lower()
    
    matched_courses = []
    
    for course in all_courses:
        # Check if the query matches any skills taught in the course
        skills_taught = [s.lower() for s in course.get("skills_taught", [])]
        if query_lower in skills_taught:
            matched_courses.append({
                "course_name": course.get("title"),
                "provider": course.get("provider"),
                "duration_weeks": course.get("duration_weeks"),
                "url": course.get("url")
            })
            
    if not matched_courses:
        return json.dumps({"status": "no_results", "message": f"No courses found for skill: {skill_query}"})
        
    # Limit results and return
    return json.dumps({
        "provider": "Internal Course Aggregator", 
        "results": matched_courses[:limit]
    }, indent=2)

# 3. Run the server via standard input/output
if __name__ == "__main__":
    mcp.run()