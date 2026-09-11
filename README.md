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

`uv` is not installed on the current machine yet, so install it before running
the backend. npm is used for the Next.js workspace.

## Prompt 0: run the scaffold

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

Open http://localhost:3000. The initial page checks the backend health endpoint
and displays its status.

## Current scope

This increment intentionally contains only the runnable scaffold and the
`GET /health` endpoint. Ingestion, retrieval, LangGraph nodes, streaming chat,
and UI workflows are implemented in later prompts and should be validated one
phase at a time.
