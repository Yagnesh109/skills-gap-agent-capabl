from fastmcp import FastMCP
import requests
import json

# 1. Initialize the MCP Server
mcp = FastMCP("Coursera Catalog Server")

# 2. Define the tool using the @mcp.tool decorator
@mcp.tool()
def search_coursera_courses(query: str, limit: int = 3) -> str:
    """
    Searches the public Coursera Catalog API for courses matching a skill or query.
    Returns a structured summary of the top matching courses.
    """
    # Coursera's public catalog endpoint
    url = "https://api.coursera.org/api/courses.v1"
    
    # Query parameters to search and return specific fields
    params = {
        "q": "search",
        "query": query,
        "limit": limit,
        "fields": "name,description,primaryLanguages"
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Parse the response into a clean, readable format for the LLM
        courses = []
        for element in data.get("elements", []):
            courses.append({
                "course_name": element.get("name"),
                "id": element.get("id"),
                "language": element.get("primaryLanguages", ["Unknown"])[0]
            })
            
        if not courses:
            return f"No courses found on Coursera for the skill: {query}"
            
        return json.dumps({"provider": "Coursera", "results": courses}, indent=2)

    except Exception as e:
        return f"Error fetching data from Coursera API: {str(e)}"

# 3. Run the server via standard input/output (which LangGraph needs)
if __name__ == "__main__":
    mcp.run()