from __future__ import annotations

import os
from typing import Any


class LangfuseRecorder:
    def __init__(self, conversation_id: str, question: str) -> None:
        self._client: Any | None = None
        self._trace: Any | None = None
        if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
            return
        from langfuse import Langfuse

        self._client = Langfuse()
        self._trace = self._client.trace(
            name="graphrag-chat",
            id=conversation_id,
            input={"question": question},
            session_id=conversation_id,
        )

    @property
    def enabled(self) -> bool:
        return self._trace is not None

    def start_node(self, node: str, state: dict[str, Any]) -> Any | None:
        if self._trace is None:
            return None
        return self._trace.span(
            name=node,
            input={"question": state.get("question"), "metadata": state.get("metadata", {})},
            metadata={"model": _model_for_node(node)},
        )

    def finish_node(
        self,
        observation: Any | None,
        state: dict[str, Any],
        output: dict[str, Any] | None = None,
    ) -> None:
        if observation is None:
            return
        metadata = dict(state.get("metadata", {}))
        if output is not None:
            observation.end(output=output, metadata=metadata)
        else:
            observation.end(output={"state": state}, metadata=metadata)

    def flush(self) -> None:
        if self._client is not None:
            self._client.flush()


def _model_for_node(node: str) -> str | None:
    if node == "router":
        return os.getenv("ROUTER_MODEL", "gemma3:4b")
    if node == "grade":
        return os.getenv("JUDGE_MODEL", "gemma3:4b")
    if node == "hallucination_check":
        return os.getenv("CHECKER_MODEL", "gemma3:4b")
    if node in {"generate", "rewrite"}:
        return os.getenv("GENERATION_MODEL", "qwen2.5:3b-instruct-q4_K_M")
    return None
