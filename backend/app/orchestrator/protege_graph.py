from langgraph.graph import END, START, StateGraph

from app.orchestrator.nodes import protege_persona_node, understanding_scorer_node
from app.orchestrator.protege_state import ProtegeState


def build_protege_graph():
    """A dedicated per-turn graph rather than a branch of the main learning_graph: the main
    pipeline runs once end-to-end per session, while a Protégé Mode session is inherently
    multi-turn (learner reply -> score -> next question), so each turn invokes this small
    graph once instead of the whole session running through a single astream() pass.
    """
    graph = StateGraph(ProtegeState)

    graph.add_node("understanding_scorer", understanding_scorer_node)
    graph.add_node("protege_persona", protege_persona_node)

    graph.add_edge(START, "understanding_scorer")
    graph.add_edge("understanding_scorer", "protege_persona")
    graph.add_edge("protege_persona", END)

    return graph.compile()


protege_graph = build_protege_graph()
