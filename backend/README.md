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
