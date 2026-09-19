from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END

# Import the working agent you just built!
# Since graph.py is in the backend folder, we import from the training-agent folder
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'training-agent'))
from agent import recommend_training

# 1. Define the State
class SkillGapState(TypedDict):
    user_name: str
    current_skills: List[str]
    top_job_matches: List[Dict[str, Any]]
    missing_skills: List[str]
    training_recommendations: List[Dict[str, Any]]

# 2. Define the Nodes
# (Mocking Node 1 and 2 for now since the parser isn't merged yet)
def node_match_jobs(state: SkillGapState):
    print("--- 1. Matching Local Jobs (Mock) ---")
    # Simulating the output of the job matching agent
    return {
        "top_job_matches": [
            {"title": "Backend Engineer", "required_skills": ["Python", "PostgreSQL", "Docker"]},
            {"title": "Data Analyst", "required_skills": ["SQL", "Excel", "Python"]}
        ]
    }

def node_analyze_gaps(state: SkillGapState):
    print("--- 2. Analyzing Skill Gaps (Mock) ---")
    # Simulating the output of the gap analysis agent
    return {"missing_skills": ["PostgreSQL", "SQL"]}

def node_recommend_training(state: SkillGapState):
    print("--- 3. Recommending Training & Calculating ROI ---")
    # Calling YOUR actual code from agent.py!
    recommendations = recommend_training(
        missing_skills=state["missing_skills"],
        top_job_matches=state["top_job_matches"] # Passing dynamic demand
    )
    return {"training_recommendations": recommendations.get("recommendations", [])}

# 3. Build the Graph
workflow = StateGraph(SkillGapState)

workflow.add_node("MatchJobs", node_match_jobs)
workflow.add_node("AnalyzeGaps", node_analyze_gaps)
workflow.add_node("RecommendTraining", node_recommend_training)

workflow.set_entry_point("MatchJobs")
workflow.add_edge("MatchJobs", "AnalyzeGaps")
workflow.add_edge("AnalyzeGaps", "RecommendTraining")
workflow.add_edge("RecommendTraining", END)

app = workflow.compile()

# 4. Run the Pipeline!
if __name__ == "__main__":
    # Ensure you have langgraph installed: pip install langgraph
    test_input = {
        "user_name": "Harsh",
        "current_skills": ["Python", "C", "PHP", "HTML"]
    }
    
    print("\nStarting Skill-Gap-to-Job Matching Pipeline...")
    final_state = app.invoke(test_input)
    
    print("\n====== PIPELINE COMPLETE ======")
    print(f"Candidate: {final_state['user_name']}")
    print(f"Identified Gaps: {final_state['missing_skills']}")
    
    if final_state["training_recommendations"]:
        best_course = final_state["training_recommendations"][0]
        print("\n🏆 Top Course Recommendation:")
        print(f"-> {best_course['course_name']} ({best_course['provider']})")
        print(f"-> ROI Reasoning: {best_course['roi_reasoning']}")