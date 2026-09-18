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
from agent.nodes.rewrite import rewrite_node
from agent.nodes.retrieve import retrieve_node

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


async def chat_events(
    question: str,
    conversation_id: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AsyncIterator[str]:
    conversation_id = conversation_id or str(uuid.uuid4())
    started = time.monotonic()
    state: dict[str, Any] = {"question": question, "metadata": {}}

    try:
        yield sse_event("status", {"node": "retrieve"})
        await _run_node(retrieve_node, state, started, timeout_seconds)

        yield sse_event("status", {"node": "grade"})
        await _run_node(grade_node, state, started, timeout_seconds)

        threshold = float(os.getenv("RELEVANCE_THRESHOLD", "0.5"))
        rewrite_count = int(state.get("rewrite_count", 0) or 0)
        average_score = 0.0
        while True:
            graded = state.get("graded_passages", []) or []
            relevant_scores = [float(passage.get("score", 0.0)) for passage in graded if passage.get("relevant")]
            average_score = sum(relevant_scores) / len(relevant_scores) if relevant_scores else 0.0
            rewrite_count = int(state.get("rewrite_count", 0) or 0)
            if average_score < threshold and rewrite_count < 2:
                yield sse_event("status", {"node": "rewrite", "question": state.get("question", question)})
                await _run_node(rewrite_node, state, started, timeout_seconds)
                continue
            break

        yield sse_event("status", {"node": "generate"})
        current_question = str(state.get("question", question)).strip() or question
        passages = [passage for passage in state.get("graded_passages", []) if passage.get("relevant")]
        answer_parts: list[str] = []
        async for token in _stream_generated_tokens(stream_answer(current_question, passages), started, timeout_seconds):
            answer_parts.append(token)
            yield sse_event("token", {"text": token})
        yield sse_event(
            "done",
            {
                "conversation_id": conversation_id,
                "sources": _sources(passages),
                "answer": "".join(answer_parts),
                "quality_warning": bool(state.get("quality_warning")) or (rewrite_count >= 2 and average_score < threshold),
            },
        )
    except TimeoutError:
        yield sse_event(
            "done",
            {"conversation_id": conversation_id, "sources": [], "timeout": True},
        )
    except Exception:
        yield sse_event("error", {"message": "The request could not be completed."})


async def chat_stream(
    question: str,
    conversation_id: str | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> AsyncIterator[str]:
    async for event in chat_events(question, conversation_id, timeout_seconds):
        yield event
