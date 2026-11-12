import shutil
import tempfile
from pathlib import Path

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat import chat_stream
from app.trace import trace_hub

app = FastAPI(title="GraphRAG Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/agent-trace")
async def agent_trace(websocket: WebSocket) -> None:
    conversation_id = websocket.query_params.get("conversation_id")
    if not conversation_id:
        await websocket.close(code=1008, reason="conversation_id is required")
        return
    await websocket.accept()
    try:
        async for event in trace_hub.events(conversation_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@app.post(
    "/chat",
    responses={400: {"description": "The question is empty"}},
)
async def chat(request: ChatRequest) -> StreamingResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")
    return StreamingResponse(
        chat_stream(question, request.conversation_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


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
