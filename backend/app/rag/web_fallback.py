"""Web Fallback.

Uses DuckDuckGo's HTML search (no API key) via the duckduckgo-search package.
Returns a list of (url, title, snippet) tuples shaped to look like retrieved chunks.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass
from duckduckgo_search import DDGS


@dataclass
class WebSnippet:
    url: str
    title: str
    snippet: str


def _search_sync(query: str, max_results: int) -> list[WebSnippet]:
    out: list[WebSnippet] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                out.append(WebSnippet(
                    url=r.get("href", ""),
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                ))
    except Exception:
        return []
    return out


async def web_search(query: str, max_results: int = 5) -> list[WebSnippet]:
    return await asyncio.to_thread(_search_sync, query, max_results)
