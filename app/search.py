# app/search.py
"""
Search utilities using the Tavily API.
This module provides:
- tavily_search(query, limit=3): returns list of {title, snippet, link}
- duckduckgo_search alias kept for compatibility (calls tavily_search)
- fetch_best_text(url, use_playwright_if_js=True): fetches and extracts the main article text

It calls the Tavily API directly. Configure the API key by setting the environment
variable TAVILY_API_KEY.

Example payload (POST):
    { "api_key": "...", "query": "weather in Singapore", "max_results": 3, "search_depth": "basic" }

The API returns JSON with a "results" array. Each result has title, content, url fields.
"""

import os
import logging
from typing import List, Dict, Any
import requests
from readability import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tavily API endpoint
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# Helpful timeout and headers
REQUEST_TIMEOUT = 15
HEADERS = {"User-Agent": "personal-ai-local/1.0 (+https://example.local/)"}


def _normalize_item(item: Dict[str, Any]) -> Dict[str, str]:
    """Normalize a Tavily result item into {title, snippet, link}."""
    if not isinstance(item, dict):
        return {"title": str(item), "snippet": "", "link": ""}

    # Tavily API returns: title, content, url
    title = item.get("title") or ""
    snippet = item.get("content") or item.get("snippet") or ""
    link = item.get("url") or item.get("link") or ""

    return {"title": title, "snippet": snippet, "link": link}


def tavily_search(query: str, limit: int = 3, return_metadata: bool = False) -> List[Dict[str, str]]:
    """
    Run a search by calling the Tavily API directly.
    Returns normalized list of {title, snippet, link}.
    If return_metadata is True, returns a dict with 'results' and 'metadata' keys.
    """
    if not TAVILY_API_KEY:
        logger.error("No Tavily API key configured (TAVILY_API_KEY).")
        if return_metadata:
            return {"results": [], "metadata": {"error": "No API key configured"}}
        return []

    # Tavily API expects: api_key, query, search_depth, max_results
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "basic",  # or "advanced" for deeper search
        "max_results": limit
    }

    metadata = {
        "called": True,
        "endpoint": TAVILY_API_URL,
        "params": {
            "query": query,
            "search_depth": "basic",
            "max_results": limit,
            "api_key": "***masked***"  # Don't expose API key
        },
        "http_status": None,
        "success": False,
        "results_count": 0,
        "error": None
    }

    try:
        resp = requests.post(TAVILY_API_URL, headers=HEADERS, json=payload, timeout=REQUEST_TIMEOUT)
        metadata["http_status"] = resp.status_code
        
        if resp.status_code != 200:
            logger.warning("Tavily API returned status %s: %s", resp.status_code, resp.text)
            metadata["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if return_metadata:
                return {"results": [], "metadata": metadata}
            return []

        j = resp.json()
        # Tavily returns results in a "results" key
        results = j.get("results", [])
        metadata["results_count"] = len(results)
        
        if not results:
            logger.warning("Tavily returned no results for query: %s", query)
            metadata["success"] = False
            if return_metadata:
                return {"results": [], "metadata": metadata}
            return []

        # Normalize each result
        normalized = [_normalize_item(it) for it in results][:limit]
        metadata["success"] = True
        
        if return_metadata:
            return {"results": normalized, "metadata": metadata}
        return normalized

    except requests.RequestException as e:
        logger.exception("Network error when contacting Tavily API: %s", e)
        metadata["error"] = str(e)
        if return_metadata:
            return {"results": [], "metadata": metadata}
        return []
    except Exception as e:
        logger.exception("Unexpected error in tavily_search: %s", e)
        metadata["error"] = str(e)
        if return_metadata:
            return {"results": [], "metadata": metadata}
        return []


# Compatibility alias so the rest of the app doesn't need to change:
def duckduckgo_search(query: str, limit: int = 3) -> List[Dict[str, str]]:
    try:
        return tavily_search(query, limit=limit)
    except Exception as e:
        logger.exception("Search alias failed: %s", e)
        return []


def fetch_best_text(url: str, use_playwright_if_js: bool = False) -> str:
    """
    Fetch a web page and extract the main textual content.
    - prefer requests + readability + BeautifulSoup.
    - If a JS-heavy page is required and Playwright is configured, we could extend this path.
    """
    if not url:
        return ""

    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            logger.warning("fetch_best_text: non-200 status %s for url %s", resp.status_code, url)
            return ""

        # Use readability to extract main content
        doc = Document(resp.text)
        content_html = doc.summary()
        # Fallback: if readability returns empty, use the full page text
        if not content_html or len(content_html) < 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            return soup.get_text(separator="\n").strip()[:30000]

        # Clean the HTML and return plain text
        soup = BeautifulSoup(content_html, "html.parser")
        text = soup.get_text(separator="\n").strip()
        # Trim to a reasonable slice to avoid sending huge context to the model
        return text[:30000]
    except Exception as e:
        logger.exception("fetch_best_text error for url %s: %s", url, e)
        return ""
