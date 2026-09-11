# Backend

FastAPI service for the local GraphRAG engine.

## Run locally

From this directory, install dependencies with `uv sync`, then run:

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

The initial service exposes `GET /health`. Domain logic will be added in the
subsequent implementation phases.
