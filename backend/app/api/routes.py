import asyncio
import json
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from .. import models, schemas
from ..database import get_db
from ..rag import orchestrator
from ..rag.ingest import parse_pdf, chunk_pages
from ..rag.embeddings import embed_texts

router = APIRouter(prefix="/api", tags=["docutrust"])


# --- Documents ----------------------------------------------------------------

@router.post("/documents", response_model=schemas.DocumentOut, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(413, "File too large (25MB limit)")

    pages = parse_pdf(data)
    drafts = chunk_pages(pages)
    if not drafts:
        raise HTTPException(400, "No extractable text found. Is this a scanned PDF?")

    # Embed in batches to keep memory predictable
    vectors = embed_texts([d.content for d in drafts])

    doc = models.Document(
        filename=file.filename,
        pages=len(pages),
        chunk_count=len(drafts),
        bytes=len(data),
    )
    db.add(doc)
    db.flush()  # get doc.id

    for d, v in zip(drafts, vectors):
        db.add(models.Chunk(
            document_id=doc.id,
            chunk_index=d.chunk_index,
            page=d.page,
            content=d.content,
            embedding=v,
        ))
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/documents", response_model=list[schemas.DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.query(models.Document).order_by(models.Document.uploaded_at.desc()).all()


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: UUID, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()


# --- Queries ------------------------------------------------------------------

@router.post("/queries", response_model=schemas.QuerySummary, status_code=201)
def start_query(
    payload: schemas.QueryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    q = models.Query(question=payload.question.strip(), status="pending")
    db.add(q)
    db.commit()
    db.refresh(q)

    background_tasks.add_task(_launch, q.id, q.question)
    return q


def _launch(query_id: UUID, question: str):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(orchestrator.run_crag(query_id, question))
        else:
            asyncio.run(orchestrator.run_crag(query_id, question))
    except RuntimeError:
        asyncio.run(orchestrator.run_crag(query_id, question))


@router.get("/queries", response_model=list[schemas.QuerySummary])
def list_queries(db: Session = Depends(get_db), limit: int = 30):
    return (
        db.query(models.Query)
        .order_by(models.Query.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/queries/{query_id}", response_model=schemas.QueryDetail)
def get_query(query_id: UUID, db: Session = Depends(get_db)):
    q = db.get(models.Query, query_id)
    if not q:
        raise HTTPException(404, "Query not found")
    return q


@router.get("/queries/{query_id}/stream")
async def stream_query(query_id: UUID, request: Request):
    queue = orchestrator.subscribe(str(query_id))

    async def event_gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
                    continue
                if msg.get("type") == "stream_end":
                    yield {"event": "end", "data": "{}"}
                    break
                yield {"event": msg.get("type", "message"), "data": json.dumps(msg)}
        finally:
            orchestrator.unsubscribe(str(query_id), queue)

    return EventSourceResponse(event_gen())
