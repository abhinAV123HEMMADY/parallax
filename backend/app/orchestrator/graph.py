from langgraph.graph import END, START, StateGraph

from app.orchestrator.nodes import (
    flashcard_fsrs_node,
    intent_parser_node,
    lesson_generator_node,
    prerequisite_graph_node,
    quiz_reexplain_node,
    snap_a_problem_node,
    stream_result_node,
    tutor_matcher_node,
    video_curator_node,
)
from app.orchestrator.state import LearningState


def route_by_input_mode(state: LearningState) -> str:
    return "photo" if state["input_mode"] == "photo" else "text"


def build_graph():
    graph = StateGraph(LearningState)

    graph.add_node("intent_parser", intent_parser_node)
    graph.add_node("snap_a_problem", snap_a_problem_node)
    graph.add_node("prerequisite_graph", prerequisite_graph_node)
    graph.add_node("lesson_generator", lesson_generator_node)
    graph.add_node("quiz_agent", quiz_reexplain_node)
    graph.add_node("flashcard_agent", flashcard_fsrs_node)
    graph.add_node("video_curator", video_curator_node)
    graph.add_node("tutor_matcher", tutor_matcher_node)
    graph.add_node("stream_result", stream_result_node)

    # Photo sessions run vision first: Snap-a-Problem turns the image into a diagnosed
    # concept, and THEN the intent parser derives objectives from that concept — the reverse
    # order would parse objectives from a base64 blob and never see the diagnosis.
    graph.add_conditional_edges(
        START,
        route_by_input_mode,
        {"photo": "snap_a_problem", "text": "intent_parser"},
    )

    graph.add_edge("snap_a_problem", "intent_parser")
    graph.add_edge("intent_parser", "prerequisite_graph")
    graph.add_edge("prerequisite_graph", "lesson_generator")
    graph.add_edge("lesson_generator", "quiz_agent")
    graph.add_edge("quiz_agent", "flashcard_agent")

    # Fan out: video/tutor sourcing run in parallel once flashcards exist, then converge.
    # Mastery is deliberately NOT part of generation — it only moves when the learner
    # actually answers quiz questions, reviews cards, or teaches Protégé Mode
    # (app/mastery/service.py).
    graph.add_edge("flashcard_agent", "video_curator")
    graph.add_edge("flashcard_agent", "tutor_matcher")

    graph.add_edge("video_curator", "stream_result")
    graph.add_edge("tutor_matcher", "stream_result")

    graph.add_edge("stream_result", END)

    return graph.compile()


learning_graph = build_graph()
