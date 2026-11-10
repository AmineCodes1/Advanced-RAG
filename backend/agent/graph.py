from __future__ import annotations

import os

from langgraph.graph import END, START, StateGraph

from agent.nodes.generate import generate_node
from agent.nodes.grade import grade_node
from agent.nodes.hallucination_check import (
    hallucination_check_node,
    prepare_regeneration_node,
)
from agent.nodes.rewrite import rewrite_node
from agent.nodes.retrieve import retrieve_node
from agent.state import AgentState


def _should_rewrite(state: dict[str, object]) -> str:
    graded = state.get("graded_passages", []) or []
    if not graded:
        return "generate"

    relevant_scores = [float(passage.get("score", 0.0)) for passage in graded if passage.get("relevant")]
    average_score = sum(relevant_scores) / len(relevant_scores) if relevant_scores else 0.0
    threshold = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
    rewrite_count = int(state.get("rewrite_count", 0) or 0)

    if average_score < threshold:
        if rewrite_count >= 2:
            return "generate"
        return "rewrite"
    return "generate"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("generate", generate_node)
    graph.add_node("hallucination_check", hallucination_check_node)
    graph.add_node("prepare_regeneration", prepare_regeneration_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", _should_rewrite, {"rewrite": "rewrite", "generate": "generate"})
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("generate", "hallucination_check")
    graph.add_conditional_edges(
        "hallucination_check",
        lambda state: (
            "prepare_regeneration"
            if not state.get("hallucination_supported", False)
            and int(state.get("regenerate_count", 0) or 0) < 1
            else "end"
        ),
        {"prepare_regeneration": "prepare_regeneration", "end": END},
    )
    graph.add_edge("prepare_regeneration", "generate")
    return graph.compile()


agent_graph = build_graph()
