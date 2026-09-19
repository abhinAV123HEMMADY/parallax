from app.mcp_clients import find_tutors
from app.orchestrator.state import LearningState


async def tutor_matcher_node(state: LearningState) -> dict:
    """Real MCP call to the Tutor Match server — specialty + verification tier surfaced directly."""
    objectives = state["parsed_objectives"]
    results = await find_tutors(subject=objectives.get("subject", "general"), topic_query=objectives["topic_name"])
    return {"tutor_matches": results}
