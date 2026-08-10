from langgraph.graph import END, START, StateGraph

from src.config import MAX_ATTEMPTS
from src.graph.nodes import GraphDeps, make_nodes
from src.graph.state import AgentState


def route_after_grade(state: AgentState) -> str:
    if state.get("grade") == "good":
        return "generate_answer"
    if state.get("attempt", 0) < state.get("max_attempts", MAX_ATTEMPTS):
        return "rewrite_query"
    return "cannot_answer"


def build_graph(deps: GraphDeps | None = None):
    deps = deps or GraphDeps()
    nodes = make_nodes(deps)
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", nodes["retrieve"])
    graph.add_node("grade_chunks", nodes["grade_chunks"])
    graph.add_node("rewrite_query", nodes["rewrite_query"])
    graph.add_node("generate_answer", nodes["generate_answer"])
    graph.add_node("cannot_answer", nodes["cannot_answer"])
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade_chunks")
    graph.add_conditional_edges(
        "grade_chunks",
        route_after_grade,
        {
            "generate_answer": "generate_answer",
            "rewrite_query": "rewrite_query",
            "cannot_answer": "cannot_answer",
        },
    )
    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("generate_answer", END)
    graph.add_edge("cannot_answer", END)
    return graph.compile()


def run_graph(deps: GraphDeps | None = None, question: str = "") -> AgentState:
    compiled = build_graph(deps)
    return compiled.invoke(
        {
            "question": question,
            "search_query": question,
            "attempt": 0,
            "max_attempts": MAX_ATTEMPTS,
            "retrieved_chunks": [],
            "citations": [],
            "trace": [],
        },
        config={"recursion_limit": (MAX_ATTEMPTS + 1) * 4},
    )