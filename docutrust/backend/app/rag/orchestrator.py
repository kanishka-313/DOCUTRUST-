"""Corrective RAG Orchestrator.

Graph:

  retrieve ──▶ grade ──▶ decide
                            │
                ┌───────────┼────────────┐
                ▼           ▼            ▼
              all-good   partial    none-good
                │           │            │
                │           │            ▼
                │           │       rewrite ─▶ web_search
                │           │            │
                ▼           ▼            ▼
              merge ◀──────────────────── 
                │
                ▼
             generate
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import SessionLocal
from . import retriever, grader, rewriter, web_fallback, generator

# In-memory pubsub: query_id -> [Queue]
_subscribers: dict[str, list[asyncio.Queue]] = {}


def subscribe(qid: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(qid, []).append(q)
    return q


def unsubscribe(qid: str, q: asyncio.Queue) -> None:
    if qid in _subscribers and q in _subscribers[qid]:
        _subscribers[qid].remove(q)
        if not _subscribers[qid]:
            del _subscribers[qid]


async def _broadcast(qid: str, event: dict) -> None:
    for q in list(_subscribers.get(qid, [])):
        await q.put(event)


async def _emit(query_id: UUID, agent: str, status: str, message: str, payload: dict | None = None) -> None:
    db = SessionLocal()
    try:
        log = models.TraceLog(
            query_id=query_id, agent=agent, status=status,
            message=message, payload=payload,
        )
        db.add(log)
        db.commit()
    finally:
        db.close()
    await _broadcast(str(query_id), {
        "type": "trace",
        "agent": agent,
        "status": status,
        "message": message,
        "payload": payload,
        "ts": datetime.utcnow().isoformat(),
    })


async def run_crag(query_id: UUID, question: str) -> None:
    """Top-level CRAG pipeline. Updates DB and broadcasts events."""
    # Mark running
    db = SessionLocal()
    try:
        q = db.get(models.Query, query_id)
        if not q:
            return
        q.status = "running"
        db.commit()
    finally:
        db.close()

    try:
        # Stage 1: Retrieve
        await _emit(query_id, "Retriever", "started", "Embedding query and searching vector store")
        db = SessionLocal()
        try:
            retrieved = await asyncio.to_thread(retriever.retrieve, db, question)
        finally:
            db.close()
        await _emit(
            query_id, "Retriever", "completed",
            f"Retrieved {len(retrieved)} chunks",
            {"chunks": [{"file": c.filename, "page": c.page, "score": c.score} for c in retrieved]},
        )

        # Stage 2: Grade
        await _emit(query_id, "Grader", "started", "Scoring chunk relevance")
        grades = await grader.grade(question, retrieved) if retrieved else []
        kept = [retrieved[g["id"]] for g in grades if g["relevant"]]
        await _emit(
            query_id, "Grader", "completed",
            f"{len(kept)}/{len(retrieved)} chunks passed",
            {"grades": grades},
        )

        # Stage 3: Decide
        decision = _decide(retrieved, kept)
        await _emit(query_id, "Decision", "completed", f"Strategy: {decision}", {"strategy": decision})

        sources: list[dict] = []
        citations: list[dict] = []

        # Add kept local chunks
        for i, c in enumerate(kept, start=1):
            sid = f"S{i}"
            label = f"{c.filename} · page {c.page}"
            sources.append({"id": sid, "label": label, "content": c.content})
            citations.append({"source": f"doc:{c.filename}:p{c.page}", "snippet": c.content[:200], "score": c.score})

        # Stage 4: Web fallback if needed
        if decision in ("partial", "web_fallback"):
            await _emit(query_id, "Query Rewriter", "started", "Rewriting question for web search")
            web_q = await rewriter.rewrite(question)
            await _emit(query_id, "Query Rewriter", "completed", f'Web query: "{web_q}"', {"web_query": web_q})

            await _emit(query_id, "Web Fallback", "started", f'Searching web for: {web_q}')
            snippets = await web_fallback.web_search(web_q, max_results=5)
            await _emit(
                query_id, "Web Fallback", "completed",
                f"Got {len(snippets)} web results",
                {"results": [{"url": s.url, "title": s.title} for s in snippets]},
            )
            offset = len(sources)
            for j, s in enumerate(snippets, start=1):
                sid = f"S{offset + j}"
                label = f"web · {s.title or s.url}"
                content = f"{s.title}\n{s.snippet}\nURL: {s.url}"
                sources.append({"id": sid, "label": label, "content": content})
                citations.append({"source": f"web:{s.url}", "snippet": s.snippet[:200], "score": None})

        # Stage 5: Generate
        await _emit(query_id, "Generator", "started", f"Composing answer from {len(sources)} sources")
        if not sources:
            answer = "I cannot answer this from the available sources."
        else:
            answer = await generator.generate(question, sources)
        await _emit(query_id, "Generator", "completed", f"Answer ready ({len(answer)} chars)")

        # Persist final
        db = SessionLocal()
        try:
            q = db.get(models.Query, query_id)
            q.status = "completed"
            q.completed_at = datetime.utcnow()
            q.answer = answer
            q.decision = decision
            q.citations = citations
            db.commit()
        finally:
            db.close()

        await _broadcast(str(query_id), {
            "type": "completed",
            "answer": answer,
            "decision": decision,
            "citations": citations,
        })

    except Exception as e:  # noqa: BLE001
        db = SessionLocal()
        try:
            q = db.get(models.Query, query_id)
            q.status = "failed"
            q.completed_at = datetime.utcnow()
            q.error = str(e)
            db.commit()
        finally:
            db.close()
        await _emit(query_id, "Orchestrator", "failed", f"Pipeline failed: {e}")
        await _broadcast(str(query_id), {"type": "failed", "error": str(e)})
    finally:
        await _broadcast(str(query_id), {"type": "stream_end"})


def _decide(retrieved, kept) -> str:
    """Decide retrieval strategy based on grader output."""
    if not retrieved:
        return "web_fallback"
    relevant_ratio = len(kept) / len(retrieved)
    if relevant_ratio >= settings.relevance_threshold and len(kept) >= 2:
        return "use_local"
    if len(kept) >= 1:
        return "partial"
    return "web_fallback"
