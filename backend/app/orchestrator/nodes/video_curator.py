from app.mcp_clients import search_transcripts
from app.orchestrator.state import LearningState


async def video_curator_node(state: LearningState) -> dict:
    """Real MCP call to the Video Transcript server — returns exact timestamps, not whole videos."""
    topic_name = state["parsed_objectives"]["topic_name"]
    results = await search_transcripts(topic_query=topic_name, difficulty_level="intro", max_results=5)

    videos = [
        {
            "video_id": r["video_id"],
            "title": r["video_title"],
            "start_seconds": r["chunk_start_seconds"],
            "url": f"https://youtube.com/watch?v={r['video_id']}&t={r['chunk_start_seconds']}s",
            "relevance": r["relevance"],
        }
        for r in results
    ]

    # Attach the top video timestamp to every quiz question as the "video" modality — the
    # third-tier re-explanation fallback (Section 4.5), surfaced by the UI only after the
    # learner misses a question and the analogy/diagram tiers weren't enough.
    quiz = list(state.get("quiz", []))
    if videos:
        for question in quiz:
            question["reexplanations"]["video"] = videos[0]

    return {"videos": videos, "quiz": quiz}
