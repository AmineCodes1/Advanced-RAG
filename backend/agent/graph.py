from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.generate import generate_node
from agent.nodes.grade import grade_node
from agent.nodes.retrieve import retrieve_node
from agent.state import AgentState


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("generate", generate_node)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_edge("grade", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


agent_graph = build_graph()
