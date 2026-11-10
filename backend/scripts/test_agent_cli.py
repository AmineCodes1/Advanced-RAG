from __future__ import annotations

import argparse
import json

from agent.graph import agent_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal GraphRAG agent")
    parser.add_argument("question", nargs="+", help="Question to ask")
    args = parser.parse_args()
    question = " ".join(args.question)
    result = agent_graph.invoke({"question": question, "metadata": {}})
    print("\nRetrieved passages:")
    for index, passage in enumerate(result.get("retrieved_passages", []), 1):
        print(f"{index}. score={passage.get('score', 0):.4f} source={passage.get('source_file')}")
    print("\nGrades:")
    for index, passage in enumerate(result.get("graded_passages", []), 1):
        print(
            f"{index}. relevant={passage.get('relevant')} "
            f"score={passage.get('score', 0):.2f} reasoning={passage.get('reasoning')}"
        )
    if result.get("rewrite_count"):
        print(f"\nRewrite loop count: {result.get('rewrite_count')}\nRewritten question: {result.get('question')}")
    print("\nAnswer:\n" + result.get("answer", ""))
    print("\nMetadata:\n" + json.dumps(result.get("metadata", {}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
