from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    pages: int
    chunk_count: int
    bytes: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)


class TraceLogOut(BaseModel):
    agent: str
    status: str
    message: str
    payload: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuerySummary(BaseModel):
    id: UUID
    question: str
    status: str
    decision: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Citation(BaseModel):
    source: str  # "doc:<filename>:p<page>" or "web:<url>"
    snippet: str
    score: Optional[float] = None


class QueryDetail(QuerySummary):
    answer: Optional[str] = None
    error: Optional[str] = None
    citations: Optional[list[Citation]] = None
    logs: list[TraceLogOut] = []
