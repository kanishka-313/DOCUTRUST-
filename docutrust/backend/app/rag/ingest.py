"""PDF ingestion and text chunking.

Strategy:
- Extract text per page (preserves page numbers for citations).
- Chunk each page's text into windows of `chunk_size` chars with `chunk_overlap`.
- Skip empty pages (scanned PDFs without OCR will produce empty pages — flagged).
"""
from __future__ import annotations
import io
from dataclasses import dataclass
from pypdf import PdfReader

from ..config import settings


@dataclass
class ChunkDraft:
    chunk_index: int
    page: int
    content: str


def parse_pdf(file_bytes: bytes) -> list[tuple[int, str]]:
    """Return list of (page_number_1_indexed, text)."""
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[tuple[int, str]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        pages.append((i, txt.strip()))
    return pages


def chunk_pages(pages: list[tuple[int, str]]) -> list[ChunkDraft]:
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    out: list[ChunkDraft] = []
    idx = 0
    for page_num, text in pages:
        if not text:
            continue
        # Sliding window by character; cheap and language-agnostic
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            content = text[start:end].strip()
            if len(content) >= 40:   # drop tiny tails
                out.append(ChunkDraft(chunk_index=idx, page=page_num, content=content))
                idx += 1
            if end == len(text):
                break
            start = end - overlap
    return out
