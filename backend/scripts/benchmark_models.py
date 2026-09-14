"""Benchmark the local Ollama models used by the GraphRAG engine.

This script intentionally has no dependency on FastAPI, LangGraph, Qdrant, or
any application node. Run it manually from the backend directory with:

    uv run python scripts/benchmark_models.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import ollama

QWEN_MODEL = "qwen2.5:3b-instruct-q4_K_M"
GEMMA_MODEL = "gemma3:4b"
DEFAULT_PROMPT = (
    "Explain in concise terms why source grounding matters in a retrieval "
    "augmented generation system."
)
JSON_PROMPTS = [
    ("What is the capital of France?", "Paris is the capital of France."),
    ("Is water liquid at room temperature?", "Water is liquid at typical room temperature."),
    ("Does the passage mention a database?", "The passage describes a database and an index."),
    ("Is the claim supported?", "The source explicitly supports the stated claim."),
    ("Is a bicycle a vehicle?", "A bicycle is a human-powered vehicle."),
    ("Does the text discuss local inference?", "The document discusses inference on a local GPU."),
    ("Is seven greater than ten?", "Seven is less than ten."),
    ("Does the source contain a date?", "The source contains no date."),
    ("Is Neo4j a graph database?", "Neo4j is a graph database."),
    ("Does this passage answer the question?", "The passage does not address the question."),
]


@dataclass
class GenerationMeasurement:
    model: str
    first_token_ms: float | None
    tokens_per_second: float | None
    token_count: int | None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None, help="Ollama host, defaults to OLLAMA_HOST")
    parser.add_argument("--tokens", type=int, default=200, help="Maximum generated tokens")
    return parser.parse_args()


def make_client(host: str | None) -> ollama.Client:
    return ollama.Client(host=host) if host else ollama.Client()


def available_models(client: ollama.Client) -> set[str]:
    response = client.list()
    models = response.get("models", []) if isinstance(response, dict) else response.models
    names: set[str] = set()
    for model in models:
        name = model.get("name") if isinstance(model, dict) else getattr(model, "model", None)
        if name:
            names.add(name)
    return names


def format_model_names(names: set[str]) -> str:
    return ", ".join(sorted(names)) if names else "(none)"


def measure_generation(client: ollama.Client, model: str, token_limit: int) -> GenerationMeasurement:
    started = time.perf_counter()
    first_token_ms: float | None = None
    final_chunk: dict[str, Any] = {}

    try:
        stream = client.generate(
            model=model,
            prompt=DEFAULT_PROMPT,
            stream=True,
            options={"num_predict": token_limit, "temperature": 0},
            keep_alive="5m",
        )
        for chunk in stream:
            if isinstance(chunk, dict):
                final_chunk = chunk
            else:
                final_chunk = chunk.model_dump()
            if first_token_ms is None and final_chunk.get("response"):
                first_token_ms = (time.perf_counter() - started) * 1000

        eval_count = final_chunk.get("eval_count")
        eval_duration = final_chunk.get("eval_duration")
        tokens_per_second = None
        if eval_count and eval_duration:
            tokens_per_second = eval_count / (eval_duration / 1_000_000_000)
        return GenerationMeasurement(model, first_token_ms, tokens_per_second, eval_count)
    except Exception as exc:
        return GenerationMeasurement(model, first_token_ms, None, None, str(exc))


def memory_snapshot() -> str:
    ollama_path = shutil.which("ollama")
    if ollama_path:
        try:
            result = subprocess.run(
                [ollama_path, "ps"], capture_output=True, text=True, timeout=10, check=False
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass

    nvidia_path = shutil.which("nvidia-smi")
    if nvidia_path:
        try:
            result = subprocess.run(
                [nvidia_path, "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return "unavailable (ollama ps and nvidia-smi are not available)"


def run_json_reliability_test(client: ollama.Client, model: str) -> tuple[int, int]:
    valid = 0
    total = len(JSON_PROMPTS)
    for question, passage in JSON_PROMPTS:
        prompt = (
            "Return ONLY one JSON object with exactly these keys: relevant (boolean), "
            "score (number from 0 to 1), reasoning (string).\n"
            f"Question: {question}\nPassage: {passage}"
        )
        try:
            response = client.generate(
                model=model,
                prompt=prompt,
                format="json",
                options={"temperature": 0},
                keep_alive="5m",
            )
            raw = response.get("response", "") if isinstance(response, dict) else response.response
            parsed = json.loads(raw)
            if (
                isinstance(parsed, dict)
                and isinstance(parsed.get("relevant"), bool)
                and isinstance(parsed.get("score"), (int, float))
                and 0 <= parsed["score"] <= 1
                and isinstance(parsed.get("reasoning"), str)
            ):
                valid += 1
        except (ValueError, TypeError, json.JSONDecodeError, Exception):
            continue
    return valid, total


def warm_model(client: ollama.Client, model: str) -> float | None:
    started = time.perf_counter()
    try:
        client.generate(model=model, prompt="Reply with OK.", options={"num_predict": 2}, keep_alive="5m")
        return time.perf_counter() - started
    except Exception:
        return None


def main() -> int:
    args = parse_args()
    try:
        client = make_client(args.host)
        installed = available_models(client)
    except Exception as exc:
        print(f"Ollama is not reachable: {exc}")
        print(f"Install Ollama, start it, then run: ollama pull {QWEN_MODEL}")
        print(f"Also run: ollama pull {GEMMA_MODEL}")
        return 0

    required = [QWEN_MODEL, GEMMA_MODEL]
    missing = [model for model in required if model not in installed]
    print(f"Installed Ollama models: {format_model_names(installed)}")
    if missing:
        print("Missing required models:")
        for model in missing:
            print(f"  ollama pull {model}")
        return 0

    measurements = [measure_generation(client, model, args.tokens) for model in required]
    print("\nGeneration benchmark")
    print("model | first token | tokens/sec | tokens | error")
    for result in measurements:
        print(
            f"{result.model} | {result.first_token_ms or '-'} ms | "
            f"{result.tokens_per_second or '-'} | {result.token_count or '-'} | {result.error or '-'}"
        )

    before_memory = memory_snapshot()
    valid, total = run_json_reliability_test(client, GEMMA_MODEL)
    print(f"\nGemma JSON reliability: {valid}/{total} ({valid / total:.1%})")
    print(f"Memory snapshot: {before_memory}")

    qwen_load = warm_model(client, QWEN_MODEL)
    client.generate(model=QWEN_MODEL, prompt="Unload this model.", keep_alive=0)
    switch_started = time.perf_counter()
    gemma_load = warm_model(client, GEMMA_MODEL)
    switch_seconds = time.perf_counter() - switch_started if gemma_load is not None else None
    print(f"Sequential load: Qwen={qwen_load or '-'} s, Gemma={gemma_load or '-'} s")
    print(f"Qwen to Gemma switch: {switch_seconds or '-'} s")

    option_a = switch_seconds is not None and switch_seconds <= 30 and valid / total >= 0.95
    recommendation = "Option A (sequential model swap)" if option_a else "Option B (Gemma for all roles)"
    print(f"\nRecommendation: {recommendation}")
    print("Reason: sequential swap must be <= 30 seconds and JSON parsing must reach 95% for Option A.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
