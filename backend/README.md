# Backend

FastAPI service for the local GraphRAG engine.

## Run locally

From this directory, install dependencies with `uv sync`, then run:

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

The initial service exposes `GET /health`. Domain logic will be added in the
subsequent implementation phases.

## Model benchmark

The isolated Ollama benchmark belongs to the model-selection phase and does
not depend on the application:

```powershell
ollama pull qwen2.5:3b-instruct-q4_K_M
ollama pull gemma3:4b
uv run python scripts/benchmark_models.py
```

It reports first-token latency, generation throughput, available memory
information, Gemma JSON parsing reliability, and the sequential model-switch
time used to choose between the two VRAM strategies.

## PDF ingestion

The vector-only ingestion pipeline uses Docling, a real token counter, FastEmbed,
and embedded Qdrant persisted under `backend/data/qdrant`:

```powershell
uv run python scripts/ingest_cli.py C:\path\to\document.pdf
```

The same pipeline is available through `POST /ingest` as a multipart upload.
The first implementation stores dense vectors; sparse BM25 fusion is reserved
for the retrieval phase. Docling preserves structured markdown and tables. When
the installed Docling release does not expose stable page-level exports, the
chunk provenance uses `page: null` rather than inventing a page number.

## Minimal agent

The MVP agent uses the measured Option A model split: Gemma 3 (`gemma3:4b`) for
structured grading and Qwen (`qwen2.5:3b-instruct-q4_K_M`) for answer generation.
Both calls use `keep_alive=0` so the models are swapped sequentially within the
4 GB VRAM constraint.

```powershell
uv run python scripts/test_agent_cli.py "What does the document say about data engineering?"
```

The graph routes each question to vector, graph, or hybrid retrieval, then
performs passage grading, conditional query rewriting, grounded generation,
and a single hallucination-check/regeneration cycle. Rewrite and regeneration
counters prevent unbounded loops. Graph retrieval requires Neo4j credentials
through `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`.

## Chat streaming

`POST /chat` returns Server-Sent Events. It emits `status` events for routing,
the selected retrieval source, grading, optional rewriting, generation, and
hallucination checking, `token` events as the answer is generated, then a
`done` event containing the conversation ID, source metadata, and any quality
or hallucination warnings.

The router can be tuned with `RETRIEVAL_LIMIT`, `GRAPH_RETRIEVAL_LIMIT`,
`GENERATION_VECTOR_LIMIT`, and `GENERATION_GRAPH_LIMIT`. The default context
cap is five vector passages plus ten graph triplets.

```powershell
curl.exe -N -X POST http://localhost:8000/chat `
	-H "Content-Type: application/json" `
	-d '{"question":"What does the document say about data engineering?"}'
```

Requests have a 120-second global timeout to accommodate sequential local model
swaps. Ollama, Qdrant, and model failures are converted into an SSE `error`
event rather than an unhandled stream crash.

The execution visualizer can subscribe to `WS /ws/agent-trace?conversation_id=...`
while a chat request is running. It receives node lifecycle events with the
status (`active`, `completed`, or `skipped`), timestamp, and duration.

## Langfuse tracing

The Langfuse SDK is optional at runtime. Configure `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` to record each conversation and
agent node. Use the local Langfuse dashboard at `http://localhost:3001` when
running a self-hosted instance; leave the keys empty to disable tracing.

Evaluation fixtures and the Ragas runner are in `eval/`. Replace the marked
entries in `eval/golden_dataset.json`, then run `uv run --extra eval
python eval/run_ragas.py`. The command exits non-zero when mean Faithfulness is
at or below 0.7 and stores detailed timestamped output under `eval/results/`.
