"""Vector retriever over the chunks table."""
from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .embeddings import embed_one


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    filename: str
    page: int | None
    content: str
    score: float  # cosine similarity in [0, 1]


def retrieve(db: Session, question: str, k: int | None = None) -> list[RetrievedChunk]:
    k = k or settings.top_k
    qvec = embed_one(question)

    # pgvector: cosine distance = 1 - cosine similarity (when vectors normalized)
    # We stored normalized vectors, so we can rank by cosine_distance ascending.
    stmt = (
        select(
            models.Chunk.id,
            models.Chunk.document_id,
            models.Chunk.page,
            models.Chunk.content,
            models.Document.filename,
            models.Chunk.embedding.cosine_distance(qvec).label("dist"),
        )
        .join(models.Document, models.Document.id == models.Chunk.document_id)
        .order_by("dist")
        .limit(k)
    )
    rows = db.execute(stmt).all()
    return [
        RetrievedChunk(
            chunk_id=str(r.id),
            document_id=str(r.document_id),
            filename=r.filename,
            page=r.page,
            content=r.content,
            score=round(1.0 - float(r.dist), 4),
        )
        for r in rows
    ]
