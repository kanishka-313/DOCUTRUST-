"""Embedding model singleton.

Loaded once on first use to avoid repeated cold-starts. ~80MB download
on first run, then cached locally by sentence-transformers.
"""
from __future__ import annotations
import threading
from functools import lru_cache
from sentence_transformers import SentenceTransformer

from ..config import settings

_lock = threading.Lock()
_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.embed_model)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vecs.tolist()


def embed_one(text: str) -> list[float]:
    return embed_texts([text])[0]
