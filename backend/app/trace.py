from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any


class TraceHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, conversation_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[conversation_id].add(queue)
        return queue

    def unsubscribe(self, conversation_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(conversation_id)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(conversation_id, None)

    async def publish(self, conversation_id: str, payload: dict[str, Any]) -> None:
        for queue in tuple(self._subscribers.get(conversation_id, ())):
            await queue.put(payload)

    async def events(self, conversation_id: str) -> AsyncIterator[dict[str, Any]]:
        queue = self.subscribe(conversation_id)
        try:
            while True:
                yield await queue.get()
        finally:
            self.unsubscribe(conversation_id, queue)


trace_hub = TraceHub()


def trace_event(node: str, status: str, started: float | None = None) -> dict[str, Any]:
    return {
        "node": node,
        "status": status,
        "timestamp": time.time(),
        "duration_ms": round((time.monotonic() - started) * 1000, 1) if started else None,
    }
