from __future__ import annotations

from typing import Any

from agent.nodes.retrieve import retrieve_vector_node
from agent.nodes.retrieve_graph import retrieve_graph_node


def retrieve_hybrid_node(state: dict[str, Any]) -> dict[str, Any]:
    vector_result = retrieve_vector_node(state)
    graph_result = retrieve_graph_node(state)
    return {"retrieved_passages": vector_result["retrieved_passages"] + graph_result["retrieved_passages"]}
