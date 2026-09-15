"""Query Rewriter.

When local retrieval fails, rewrite the question into a tight web search query.
Strip first-person voice, add disambiguating context, keep it short.
"""
from __future__ import annotations

from .llm import get_client
from ..config import settings


REWRITER_PROMPT = """You rewrite user questions as concise web search queries.

Rules:
- Output ONE query, 3-8 words, no quotes, no punctuation.
- Strip "please", "can you", "I want to know", etc.
- Add disambiguating context only if the original is ambiguous.
- No prose. The query only.
"""


async def rewrite(question: str) -> str:
    client = get_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        max_tokens=40,
        messages=[
            {"role": "system", "content": REWRITER_PROMPT},
            {"role": "user", "content": question},
        ],
    )
    return (resp.choices[0].message.content or question).strip().strip('"').strip("'")
