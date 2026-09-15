"""Relevance Grader.

For each retrieved chunk, ask the LLM whether it contains information relevant to
answering the question. Returns a list of bool flags, one per chunk.

We batch grading in a single LLM call for speed — model returns a JSON array.
"""
from __future__ import annotations
import json
import re

from .llm import get_client
from .retriever import RetrievedChunk
from ..config import settings


GRADER_PROMPT = """You are a strict relevance grader for a retrieval system.

Given a user question and N retrieved passages, decide for each passage whether
it directly contains information useful for answering the question.

Be conservative: mark "yes" only if the passage clearly addresses some part of
the question. Background context that mentions the topic but doesn't answer is "no".

Return ONLY a JSON array of N objects, in the same order as the passages, each:
{"id": <integer index>, "relevant": <true|false>, "why": "<<= 12 words>"}

No prose. No markdown. JSON array only.
"""


async def grade(question: str, chunks: list[RetrievedChunk]) -> list[dict]:
    if not chunks:
        return []

    passages_text = "\n\n".join(
        f"[{i}] (source: {c.filename}, page {c.page})\n{c.content}"
        for i, c in enumerate(chunks)
    )
    user_msg = f"Question: {question}\n\nPassages:\n{passages_text}"

    client = get_client()
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": GRADER_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )
    raw = (resp.choices[0].message.content or "").strip()
    # Strip code fences if model added them
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            raise ValueError("not a list")
    except Exception:
        # Fallback: mark all as relevant if grader output is malformed — fail open
        return [{"id": i, "relevant": True, "why": "grader output unparseable"} for i in range(len(chunks))]

    # Normalize: pad missing ids with relevant=True (fail open)
    by_id = {int(item.get("id", -1)): item for item in parsed if isinstance(item, dict)}
    out = []
    for i in range(len(chunks)):
        item = by_id.get(i, {"id": i, "relevant": True, "why": "missing from grader output"})
        out.append({
            "id": i,
            "relevant": bool(item.get("relevant", True)),
            "why": str(item.get("why", ""))[:120],
        })
    return out
