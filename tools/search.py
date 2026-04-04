import logging
import asyncio
from duckduckgo_search import DDGS

logger = logging.getLogger("opennexus.tools.search")

async def web_search(query: str, max_results: int = 5) -> list[dict]:
    logger.info(f"Performing web search for: {query}")
    try:
        def _search():
            with DDGS() as ddgs:
                results = []
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                return results
        
        return await asyncio.to_thread(_search)
    except Exception as e:
        logger.error(f"Web search failed for query '{query}': {e}")
        return []
