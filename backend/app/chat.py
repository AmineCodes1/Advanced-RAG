from __future__ import annotations

import asyncio
import json
import os
import queue
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

from agent.nodes.generate import stream_answer
from agent.nodes.grade import grade_node
from agent.nodes.hallucination_check import hallucination_check_node, prepare_regeneration_node
from agent.nodes.rewrite import rewrite_node
from agent.nodes.retrieve import retrieve_node
from agent.nodes.retrieve_graph import retrieve_graph_node
from agent.nodes.retrieve_hybrid import retrieve_hybrid_node
from agent.nodes.router import router_node
from app.trace import trace_event, trace_hub
from app.observability import LangfuseRecorder

DEFAULT_TIMEOUT_SECONDS = 120.0


def sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


def _remaining(started: float, timeout_seconds: float) -> float:
    remaining = timeout_seconds - (time.monotonic() - started)
    if remaining <= 0:
        raise TimeoutError
    return remaining


async def _run_node(
    node: Any,
    state: dict[str, Any],
    started: float,
    timeout_seconds: float,
) -> None:
    state.update(
        await asyncio.wait_for(
            asyncio.to_thread(node, state),
            _remaining(started, timeout_seconds),
        )
    )


def _start_token_producer(
    stream: Iterator[str],
    token_queue: queue.Queue[tuple[str, str]],
) -> asyncio.Task[Any]:
    def produce_tokens() -> None:
        try:
            for token in stream:
                token_queue.put(("token", token))
        except Exception as exc:
            token_queue.put(("error", str(exc)))
        finally:
            token_queue.put(("done", ""))

    return asyncio.create_task(asyncio.to_thread(produce_tokens))


async def _stream_generated_tokens(
    stream: Iterator[str],
    started: float,
    timeout_seconds: float,
) -> AsyncIterator[str]:
    token_queue: queue.Queue[tuple[str, str]] = queue.Queue()
    producer = _start_token_producer(stream, token_queue)
    try:
        while True:
            kind, value = await asyncio.wait_for(
                asyncio.to_thread(token_queue.get),
                _remaining(started, timeout_seconds),
            )
            if kind == "done":
                break
            if kind == "error":
                raise RuntimeError(value)
            yield value
        await producer
    except TimeoutError:
        producer.cancel()
        raise


def _sources(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_file": passage.get("source_file"),
            "page": passage.get("page"),
            "score": passage.get("score"),
        }
        for passage in passages
    ]


def _generation_passages(passages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vector_limit = int(os.getenv("GENERATION_VECTOR_LIMIT", "5"))
    graph_limit = int(os.getenv("GENERATION_GRAPH_LIMIT", "10"))
    vector_passages = [passage for passage in passages if passage.get("source_type") != "graph"][:vector_limit]
    graph_passages = [passage for passage in passages if passage.get("source_type") == "graph"][:graph_limit]
    return vector_passages + graph_passages


def _graph_subgraph(passages: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    graph_passages = [passage for passage in passages if passage.get("source_type") == "graph"]
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for passage in graph_passages:
        subject = str(passage.get("subject", "")).strip()
        relation = str(passage.get("relation", "")).strip()
        object_name = str(passage.get("object", "")).strip()
        if not subject or not relation or not object_name:
            continue
        nodes.setdefault(subject, {"id": subject, "label": subject, "type": "Entity"})
        nodes.setdefault(object_name, {"id": object_name, "label": object_name, "type": "Entity"})
        edge_key = (subject, object_name, relation)
        if edge_key not in seen_edges:
            edges.append({"source": subject, "target": object_name, "relation": relation})
            seen_edges.add(edge_key)
    return {"nodes": list(nodes.values()), "edges": edges}


async def chat_events(
    question: str,
    conversation_id: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AsyncIterator[str]:
    conversation_id = conversation_id or str(uuid.uuid4())
    started = time.monotonic()
    state: dict[str, Any] = {"question": question, "metadata": {}}
    recorder = LangfuseRecorder(conversation_id, question)

    try:
        async def run_traced(node_name: str, node: Any) -> AsyncIterator[str]:
            node_started = time.monotonic()
            observation = recorder.start_node(node_name, state)
            active = trace_event(node_name, "active")
            await trace_hub.publish(conversation_id, active)
            yield sse_event("status", {"node": node_name})
            try:
                await _run_node(node, state, started, timeout_seconds)
            finally:
                recorder.finish_node(observation, state)
            await trace_hub.publish(conversation_id, trace_event(node_name, "completed", node_started))

        async for event in run_traced("router", router_node):
            yield event
        route = state.get("route", "vector")
        retrieval_node = {
            "vector": retrieve_node,
            "graph": retrieve_graph_node,
            "hybrid": retrieve_hybrid_node,
        }.get(route, retrieve_node)
        async for event in run_traced(f"retrieve_{route}", retrieval_node):
            yield event

        async for event in run_traced("grade", grade_node):
            yield event

        threshold = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
        rewrite_count = int(state.get("rewrite_count", 0) or 0)
        average_score = 0.0
        while True:
            graded = state.get("graded_passages", []) or []
            relevant_scores = [float(passage.get("score", 0.0)) for passage in graded if passage.get("relevant")]
            average_score = sum(relevant_scores) / len(relevant_scores) if relevant_scores else 0.0
            rewrite_count = int(state.get("rewrite_count", 0) or 0)
            if average_score < threshold and rewrite_count < 2:
                async for event in run_traced("rewrite", rewrite_node):
                    yield event
                continue
            break

        current_question = str(state.get("question", question)).strip() or question
        passages = _generation_passages(
            [passage for passage in state.get("graded_passages", []) if passage.get("relevant")]
        )
        answer_parts: list[str] = []
        for generation_attempt in range(2):
            node_started = time.monotonic()
            generation_observation = recorder.start_node("generate", state)
            await trace_hub.publish(conversation_id, trace_event("generate", "active"))
            yield sse_event("status", {"node": "generate"})
            answer_parts = []
            async for token in _stream_generated_tokens(
                stream_answer(
                    current_question,
                    passages,
                    instruction=state.get("regeneration_instruction"),
                ),
                started,
                timeout_seconds,
            ):
                answer_parts.append(token)
                yield sse_event("token", {"text": token})
            state["answer"] = "".join(answer_parts)
            recorder.finish_node(generation_observation, state, {"answer": state["answer"]})
            await trace_hub.publish(conversation_id, trace_event("generate", "completed", node_started))
            async for event in run_traced("hallucination_check", hallucination_check_node):
                yield event
            if state.get("hallucination_supported", False) or generation_attempt == 1:
                break
            async for event in run_traced("prepare_regeneration", prepare_regeneration_node):
                yield event
            await trace_hub.publish(conversation_id, trace_event("generate", "skipped"))
            yield sse_event("status", {"node": "generate", "regenerating": True})
        yield sse_event(
            "done",
            {
                "conversation_id": conversation_id,
                "sources": _sources(passages),
                "answer": "".join(answer_parts),
                "quality_warning": bool(state.get("quality_warning"))
                or (rewrite_count >= 2 and average_score < threshold),
                "hallucination_warning": bool(state.get("hallucination_warning")),
                "unsupported_claims": state.get("unsupported_claims", []),
                "graph": _graph_subgraph(passages),
                "contexts": [str(passage.get("text", "")) for passage in passages],
            },
        )
        recorder.flush()
    except TimeoutError:
        recorder.flush()
        yield sse_event(
            "done",
            {"conversation_id": conversation_id, "sources": [], "timeout": True},
        )
    except Exception:
        recorder.flush()
        yield sse_event("error", {"message": "The request could not be completed."})


async def chat_stream(
    question: str,
    conversation_id: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AsyncIterator[str]:
    async for event in chat_events(question, conversation_id, timeout_seconds):
        yield event
