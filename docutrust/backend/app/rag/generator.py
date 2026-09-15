"""Answer Generator.

Generates the final answer from validated context, with strict citation rules.
The model is told to refuse rather than fabricate when context is insufficient.
"""
from __future__ import annotations

from .llm import get_client
from ..config import settings


GENERATOR_PROMPT = """You are a careful enterprise document assistant.

You answer ONLY from the SOURCES block below.

Rules:
- Cite every claim inline using bracketed source ids like [S1], [S2].
- If a claim spans multiple sources, cite each: [S1][S3].
- If the sources do not contain enough information, say exactly:
  "I cannot answer this from the available sources."
  Do not guess. Do not use outside knowledge.
- Be direct. No filler. Markdown allowed (lists, bold).
- Do NOT invent source ids that are not in the SOURCES block.
"""


def _format_sources(sources: list[dict]) -> str:
    lines = []
    for s in sources:
        lines.append(f"[{s['id']}] {s['label']}\n{s['content']}\n")
    return "\n".join(lines)


async def generate(question: str, sources: list[dict]) -> str:
    """
    sources: list of {"id": "S1", "label": "<filename> p.<N>" or "web: <url>", "content": "..."}
    """
    if not sources:
        return "I cannot answer this from the available sources."

    client = get_client()
    user_msg = f"Question: {question}\n\nSOURCES:\n{_format_sources(sources)}"

    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": GENERATOR_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
