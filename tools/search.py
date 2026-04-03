import logging
from duckduckgo_search import AsyncDDGS

logger = logging.getLogger("opennexus.tools.search")

async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Performs a web search using DuckDuckGo.
    Returns a list of dictionaries containing title, url, and snippet.
    """
    logger.info(f"Performing web search for: {query}")
    try:
        async with AsyncDDGS() as ddgs:
            results = []
            async for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return results
    except Exception as e:
        logger.error(f"Web search failed for query '{query}': {e}")
        return []
