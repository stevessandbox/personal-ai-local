# app/search.py
"""
Web search utilities using the Tavily API.

This module provides:
- tavily_search(query, limit=3): Search using Tavily API, returns list of {title, snippet, link}
- duckduckgo_search: Compatibility alias (calls tavily_search)
- fetch_best_text(url): Fetches and extracts main content from web pages

Configuration:
- Set TAVILY_API_KEY environment variable for API authentication
- Default API key is provided but should be replaced with your own

The Tavily API returns structured search results with title, content, and URL fields.
We use readability-lxml and BeautifulSoup to extract clean text from fetched pages.
"""

import os
import logging
from typing import List, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from readability import Document
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Tavily API endpoint
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# Helpful timeout and headers
REQUEST_TIMEOUT = 15
HEADERS = {"User-Agent": "personal-ai-local/1.0 (+https://example.local/)"}

# Create a session with connection pooling and retry strategy (efficiency improvement)
# This reuses TCP connections instead of creating new ones for each request
session = requests.Session()
session.headers.update(HEADERS)

# Configure retry strategy for transient failures
retry_strategy = Retry(
    total=2,  # Maximum 2 retries
    backoff_factor=0.3,  # Wait 0.3s, 0.6s between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
    allowed_methods=["GET", "POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)


def _normalize_item(item: Dict[str, Any]) -> Dict[str, str]:
    """
    Normalize a Tavily API result item into a consistent format.
    
    Tavily API returns items with 'title', 'content', and 'url' fields.
    This function normalizes them to 'title', 'snippet', and 'link' for consistency.
    """
    if not isinstance(item, dict):
        return {"title": str(item), "snippet": "", "link": ""}

    # Extract fields with fallbacks for different API response formats
    title = item.get("title") or ""
    snippet = item.get("content") or item.get("snippet") or ""
    link = item.get("url") or item.get("link") or ""

    return {"title": title, "snippet": snippet, "link": link}


def tavily_search(query: str, limit: int = 3, return_metadata: bool = False) -> List[Dict[str, str]]:
    """
    Run a web search by calling the Tavily API directly.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return (default: 3)
        return_metadata: If True, returns dict with 'results' and 'metadata' keys.
                        Metadata includes API call status, HTTP status, params, etc.
    
    Returns:
        If return_metadata=False: List of normalized result dicts with {title, snippet, link}
        If return_metadata=True: Dict with 'results' (list) and 'metadata' (dict) keys
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
        # Use session for connection reuse (efficiency improvement)
        resp = session.post(TAVILY_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
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


def fetch_best_text(url: str) -> str:
    """
    Fetch a web page and extract the main textual content.
    
    Uses readability-lxml to extract article content, with BeautifulSoup as fallback.
    This approach is faster than using Playwright for most content sites.
    
    Args:
        url: URL to fetch
    
    Returns:
        Extracted text content (truncated to 30k chars max)
    """
    if not url:
        return ""

    try:
        # Use session for connection reuse (efficiency improvement)
        resp = session.get(url, timeout=10)
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
