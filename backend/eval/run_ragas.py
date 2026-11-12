from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).parent
RESULTS = ROOT / "results"


def _read_sse_events(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for block in body.split("\n\n"):
        data = next((line[6:] for line in block.splitlines() if line.startswith("data: ")), None)
        if data:
            try:
                events.append(json.loads(data))
            except json.JSONDecodeError:
                continue
    return events


async def _ask(client: httpx.AsyncClient, question: str) -> dict[str, Any]:
    response = await client.post("/chat", json={"question": question})
    response.raise_for_status()
    events = _read_sse_events(response.text)
    done = next((event for event in reversed(events) if "conversation_id" in event), {})
    return done


def _validate_dataset(dataset: list[dict[str, Any]]) -> None:
    required = {"id", "question", "reference", "reference_contexts"}
    if not dataset:
        raise ValueError("The golden dataset is empty.")
    if any(not required.issubset(item) for item in dataset):
        raise ValueError("Every golden entry must contain id, question, reference, and reference_contexts.")
    if any("À REMPLACER" in json.dumps(item, ensure_ascii=False) for item in dataset):
        raise ValueError("Replace the demonstration entries in golden_dataset.json before running evaluation.")


async def _collect(dataset: list[dict[str, Any]], base_url: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=base_url, timeout=180.0) as client:
        results = []
        for item in dataset:
            answer = await _ask(client, item["question"])
            results.append({**item, "response": answer})
        return results


def _evaluate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.metrics import AnswerRelevancy, Faithfulness
    except ImportError as exc:
        raise RuntimeError("Install the evaluation extra with `uv sync --extra eval`.") from exc

    samples = [
        SingleTurnSample(
            user_input=row["question"],
            response=row["response"].get("answer", ""),
            retrieved_contexts=row["response"].get("contexts", []),
            reference=row["reference"],
        )
        for row in rows
    ]
    scores = evaluate(EvaluationDataset(samples=samples), metrics=[Faithfulness(), AnswerRelevancy()])
    records = scores.to_pandas().to_dict(orient="records")
    return [{**row, "metrics": metrics} for row, metrics in zip(rows, records, strict=True)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate GraphRAG with a Ragas golden dataset.")
    parser.add_argument("--dataset", type=Path, default=ROOT / "golden_dataset.json")
    parser.add_argument("--base-url", default=os.getenv("GRAPHRAG_API_URL", "http://localhost:8000"))
    parser.add_argument("--threshold", type=float, default=float(os.getenv("FAITHFULNESS_THRESHOLD", "0.7")))
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    _validate_dataset(dataset)
    rows = asyncio.run(_collect(dataset, args.base_url))
    evaluated = _evaluate(rows)
    metrics = {
        name: [float(row["metrics"][name]) for row in evaluated if row["metrics"].get(name) is not None]
        for name in ("faithfulness", "answer_relevancy")
    }
    summary = {
        name: {"mean": sum(values) / len(values), "min": min(values), "max": max(values)}
        for name, values in metrics.items()
    }
    output = {"generated_at": datetime.now(timezone.utc).isoformat(), "thresholds": {"faithfulness": args.threshold}, "summary": summary, "results": evaluated}
    RESULTS.mkdir(exist_ok=True)
    destination = RESULTS / f"results-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    destination.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Detailed results: {destination}")
    return 0 if summary["faithfulness"]["mean"] > args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
