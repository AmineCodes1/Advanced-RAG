# GraphRAG Engine

Local, agentic GraphRAG engine designed for a machine with 4 GB of VRAM and no
recurring infrastructure cost.

## Architecture

- `backend/`: FastAPI service, LangGraph orchestration, embedded Qdrant and
  Ollama client.
- `frontend/`: Next.js 14 App Router interface.
- `docker/`: Neo4j only at this stage; Qdrant remains embedded in the backend.
- `graph-extraction/`: future offline Google Colab workflow for triplet
  extraction and Neo4j import.

The intended query flow is frontend -> FastAPI -> LangGraph -> Qdrant and/or
Neo4j -> Ollama -> frontend. Ollama runs on the host so local GPU access stays
simple.

## Prerequisites

- Python 3.11+ (Python 3.13 is supported by the project constraints)
- Node.js 18+
- Docker Desktop
- Ollama installed locally
- `uv` recommended for Python dependency management. It is a fast, lockfile-
based tool for reproducible Python environments; install it from
https://docs.astral.sh/uv/getting-started/installation/.

npm is used for the Next.js workspace.

## Run locally

Create the Neo4j environment file once:

```powershell
Copy-Item docker/.env.example docker/.env
```

Set a local password in `docker/.env`, then start Neo4j:

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml up -d
```

Start the backend:

```powershell
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm run dev
```

Open http://localhost:3000 to use Chat Studio.

## Start the stack with Docker

After copying `docker/.env.example` to `docker/.env` and setting a local
Neo4j password, run:

```powershell
docker compose --env-file docker/.env -f docker/docker-compose.yml up --build
```

This starts the production frontend, FastAPI backend, and Neo4j. Qdrant stays
embedded in the backend and is persisted in the `backend_data` Docker volume.
Ollama intentionally runs on the host because local GPU access is simpler and
more reliable there; the backend container reaches it through
`host.docker.internal:11434`. Langfuse is an optional external local service:
run the official self-hosted compose stack separately on port 3001 and provide
its generated keys in `docker/.env`.

The smoke test is available for a Unix-like shell or CI runner:

```sh
sh scripts/smoke_test.sh
```

## Current scope

The project currently includes PDF ingestion with embedded Qdrant, a
self-correcting retrieval and generation agent, streaming chat over SSE, a
WebSocket-backed agent execution visualizer, an optional Langfuse integration,
and the Chat Studio interface. Automated evaluation is available under
`backend/eval`.

## Langfuse observability

Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally
`LANGFUSE_HOST` in the backend environment to enable tracing. Without these
keys, the application runs normally with observability disabled. Each chat
conversation is recorded with its `conversation_id`; node spans include inputs,
outputs, configured model names, metadata, and latency. The Langfuse dashboard
can then be used to inspect retrieval routes, rewrite/regeneration frequency,
and grading or hallucination-check failures.

The official Langfuse self-hosted stack changes independently from the
application and includes Postgres, ClickHouse, Redis, and object storage. Run
the versioned compose file from the
[Langfuse repository](https://github.com/langfuse/langfuse/blob/main/docker-compose.yml)
alongside this project, expose it on port `3001`, and copy its generated API
keys into `docker/.env`; this avoids maintaining an incomplete local fork of
that multi-service stack.

## Evaluation

The starter dataset and evaluator are in [backend/eval](./backend/eval).
Replace the four marked demonstration entries with questions and references
from your documents, then run:

```powershell
cd backend
uv run --extra eval python eval/run_ragas.py
```

The evaluator saves timestamped JSON results and exits non-zero when mean
Faithfulness is not greater than `0.7`. A low Faithfulness score usually means
the retrieved context does not support the answer: inspect the selected route,
passage grading failures, `RELEVANCE_THRESHOLD`, rewrite count, and
hallucination-check warnings before changing the generation prompt.

## Project guides and data flow

- [Backend guide](./backend/README.md)
- [Frontend guide](./frontend/README.md)
- [Graph extraction guide](./graph-extraction/README.md)
- [Evaluation guide](./backend/eval)

The runtime flow is: **browser → Next.js Chat Studio → FastAPI**. FastAPI
routes each question through **LangGraph**, which selects vector, graph, or
hybrid retrieval. Vector retrieval reads embedded Qdrant; graph retrieval reads
Neo4j; both feed grading, optional rewriting, generation through host Ollama,
and hallucination checking. Responses stream back over SSE, while execution
events travel over the conversation-scoped WebSocket. Langfuse receives
optional traces, and the frontend renders sources plus any retrieved graph
subgraph.
