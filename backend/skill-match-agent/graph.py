from langgraph.graph import StateGraph, END
from .state import SkillMatchState


def fetch_jobs_node(state: SkillMatchState) -> dict:
    """
    Placeholder node: Queries Jooble API to fetch relevant job listings.
    Actual retrieval logic to be implemented later.
    """
    return {"raw_jobs": []}


def compute_semantic_match_node(state: SkillMatchState) -> dict:
    """
    Placeholder node: Computes semantic similarity between candidate skills and job requirements
    using Sentence Transformers (all-MiniLM-L6-v2).
    Actual matching logic to be implemented later.
    """
    return {"matched_results": []}


def rank_and_filter_node(state: SkillMatchState) -> dict:
    """
    Placeholder node: Ranks matched jobs by match score and filters top_k.
    Actual ranking logic to be implemented later.
    """
    return {"matched_results": state.get("matched_results", [])}


def build_skill_match_graph():
    """
    Constructs the LangGraph StateGraph workflow for Skill Matching.
    """
    workflow = StateGraph(SkillMatchState)

    # Register workflow nodes
    workflow.add_node("fetch_jobs", fetch_jobs_node)
    workflow.add_node("compute_semantic_match", compute_semantic_match_node)
    workflow.add_node("rank_and_filter", rank_and_filter_node)

    # Define execution edges
    workflow.set_entry_point("fetch_jobs")
    workflow.add_edge("fetch_jobs", "compute_semantic_match")
    workflow.add_edge("compute_semantic_match", "rank_and_filter")
    workflow.add_edge("rank_and_filter", END)

    return workflow.compile()


# Compiled agent graph instance placeholder
skill_match_agent = None
