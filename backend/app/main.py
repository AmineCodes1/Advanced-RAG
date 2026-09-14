import shutil
import tempfile
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="GraphRAG Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/ingest",
    responses={
        400: {"description": "The uploaded file is not a PDF"},
        500: {"description": "The ingestion pipeline failed"},
    },
)
def ingest(file: Annotated[UploadFile, File(...)]) -> dict[str, object]:
    if not file.filename or Path(file.filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    from ingestion.pipeline import ingest_document

    with tempfile.TemporaryDirectory() as temp_dir:
        temporary_path = Path(temp_dir) / Path(file.filename).name
        with temporary_path.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)
        try:
            return ingest_document(temporary_path).to_dict()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc
