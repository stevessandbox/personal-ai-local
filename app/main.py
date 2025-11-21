# app/main.py
"""
Main FastAPI application with routes for:
- Question answering with optional memory and web search
- Memory management (add, query, list, delete)
- Debug prompt building
"""

import os
import time
import hashlib
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load .env early so all modules that import environment variables see them.
# This ensures TAVILY_API_KEY and other vars are available when other modules import.
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel
from typing import Optional
from .model_client import run_local_model
from .memory import upsert_memory, query_memory, list_all_memories, delete_memory
from .search import fetch_best_text, tavily_search
from .prompts import build_prompt

# Simple in-memory cache for query results (efficiency improvement)
# Cache size limited to prevent memory issues
_query_cache = {}
_cache_max_size = 100  # Maximum number of cached queries

# Initialize FastAPI app
app = FastAPI(title="Personal AI Local API (with UI)")

# Add response compression middleware (efficiency improvement)
# Compresses responses > 1000 bytes to reduce bandwidth
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Serve the static UI from app/static (React build output)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Also serve assets from the static directory (JS/CSS bundles from Vite)
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# Request/Response models
class AskRequest(BaseModel):
    """Request model for asking questions."""
    question: str
    use_memory: Optional[bool] = True  # Whether to query memory store
    use_search: Optional[bool] = True   # Whether to use web search

class MemoryAddRequest(BaseModel):
    """Request model for adding memories."""
    key: str
    text: str
    metadata: Optional[dict] = None

@app.get("/")
def index():
    """
    Serve the React UI index page.
    In production, this serves the built React app from app/static/index.html.
    """
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"error": "UI not found. Make sure app/static/index.html exists."}, status_code=404)

def _fetch_search_result(r: dict) -> str:
    """
    Helper function to fetch and format a single search result.
    
    Optimized for speed:
    - Uses snippet first (from Tavily API)
    - Only fetches full page if snippet is too short
    - Limits fetched text to reduce processing time
    
    Args:
        r: Search result dict with 'snippet', 'link', 'title' keys
        
    Returns:
        Formatted string with title and summary, or None if fetch fails
    """
    try:
        snippet = r.get("snippet", "")
        if len(snippet) > 300:
            # Good snippet available, use it with minimal additional fetch
            txt = fetch_best_text(r["link"])
            # Only use first 1000 chars from fetched text to save time
            txt_preview = (txt[:1000] if isinstance(txt, str) else "")
            summary = f"{snippet}\n{txt_preview}"
        else:
            # Short snippet, fetch more content but limit to 1500 chars
            txt = fetch_best_text(r["link"])
            summary = (snippet + "\n" + (txt[:1500] if isinstance(txt, str) else "")).strip()
        
        if summary and summary.strip():
            return f"{r.get('title','')} - {summary}"
    except Exception:
        # Fallback to just snippet if page fetch fails
        if snippet:
            return f"{r.get('title','')} - {snippet}"
    return None

@app.post("/ask")
def ask(req: AskRequest):
    """
    Main endpoint for asking questions with optional memory and web search.
    
    Performance optimizations:
    - Memory and search queries run in parallel when both are enabled
    - Web page fetching is parallelized (3 workers)
    - Context is truncated to reduce model processing time
    
    Returns:
        JSON with answer, tavily_info, search_texts, memory_texts, and timings
    """
    timings = {}
    t0 = time.time()
    
    # Initialize response structures
    memory_texts = []
    search_texts = []
    tavily_info = {
        "called": False,
        "status": "not called",
        "success": False,
        "params": None,
        "http_status": None,
        "results_count": 0,
        "error": None
    }
    
    def fetch_memory():
        """Fetch relevant memories from vector store."""
        if not req.use_memory:
            return []
        try:
            # Simple cache key based on question hash
            cache_key = f"mem:{hashlib.md5(req.question.encode()).hexdigest()}"
            if cache_key in _query_cache:
                return _query_cache[cache_key]
            
            res = query_memory(req.question, n_results=3)
            docs = res.get("documents", [])
            # Handle nested list structure from Chroma
            if docs and isinstance(docs[0], list):
                docs_flat = [d for sub in docs for d in sub]
            else:
                docs_flat = docs
            result = [d for d in docs_flat if d and d.strip()]
            
            # Cache result (with size limit)
            if len(_query_cache) >= _cache_max_size:
                # Remove oldest entry (simple FIFO)
                _query_cache.pop(next(iter(_query_cache)))
            _query_cache[cache_key] = result
            return result
        except Exception:
            return []
    
    def fetch_search():
        """Fetch web search results from Tavily API."""
        if not req.use_search:
            return [], tavily_info, {}
        try:
            search_timings = {}
            # Call Tavily API
            t_api_start = time.time()
            search_result = tavily_search(req.question, limit=3, return_metadata=True)
            search_timings["tavily_api"] = time.time() - t_api_start
            
            results = []
            info = tavily_info.copy()
            
            # Extract results and metadata from Tavily response
            if isinstance(search_result, dict) and "metadata" in search_result:
                results = search_result.get("results", [])
                info = search_result.get("metadata", info)
                # Set status based on success/error
                if info.get("success"):
                    info["status"] = "success"
                elif info.get("error"):
                    info["status"] = "error"
                else:
                    info["status"] = "failed"
            else:
                # Fallback for non-metadata response format
                results = search_result if isinstance(search_result, list) else []
                info["called"] = True
                info["status"] = "success" if results else "failed"
                info["success"] = bool(results)
                info["results_count"] = len(results)
            
            # Parallelize page fetching for multiple results (performance optimization)
            t_fetch_start = time.time()
            search_texts_list = []
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(_fetch_search_result, r) for r in results]
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        search_texts_list.append(result)
            search_timings["fetch_best_text_total"] = time.time() - t_fetch_start
            
            return search_texts_list, info, search_timings
        except Exception as e:
            # Return error info if search fails
            info = tavily_info.copy()
            info["called"] = True
            info["status"] = "error"
            info["error"] = str(e)
            return [], info, {}
    
    # Execute memory and search in parallel if both are enabled (performance optimization)
    if req.use_memory and req.use_search:
        t_parallel_start = time.time()
        with ThreadPoolExecutor(max_workers=2) as executor:
            mem_future = executor.submit(fetch_memory)
            search_future = executor.submit(fetch_search)
            memory_texts = mem_future.result()
            search_texts, tavily_info, search_timings = search_future.result()
        timings["parallel_fetch"] = time.time() - t_parallel_start
        timings.update(search_timings)
        if req.use_memory:
            timings["memory_query"] = timings.get("parallel_fetch", 0)
        timings["search_total"] = timings.get("parallel_fetch", 0)
    elif req.use_memory:
        t_mem_start = time.time()
        memory_texts = fetch_memory()
        timings["memory_query"] = time.time() - t_mem_start
    elif req.use_search:
        t_search_start = time.time()
        search_texts, tavily_info, search_timings = fetch_search()
        timings.update(search_timings)
        timings["search_total"] = time.time() - t_search_start

    # Build prompt with context from memory and/or search
    t_prompt_start = time.time()
    prompt = build_prompt(req.question, memory_texts=memory_texts or None,
                          search_texts=search_texts or None)
    timings["prompt_build"] = time.time() - t_prompt_start
    
    # Run model inference via Ollama
    t_model_start = time.time()
    try:
        out = run_local_model(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    timings["model_run"] = time.time() - t_model_start
    timings["total"] = time.time() - t0
    
    return {
        "answer": out,
        "tavily_info": tavily_info,
        "search_texts": search_texts,
        "memory_texts": memory_texts,
        "timings": timings
    }

@app.post("/memory/add")
def add_memory(req: MemoryAddRequest):
    """Add or update a memory entry in the vector store."""
    upsert_memory(req.key, req.text, metadata=req.metadata)
    return {"status": "ok"}

@app.get("/memory/query")
def memory_query(q: str, n_results: int = 4):
    """Query the memory store using semantic similarity search."""
    res = query_memory(q, n_results=n_results)
    return res

@app.get("/memory/list")
def memory_list():
    """List all memory entries with their IDs, documents, and metadata."""
    return list_all_memories()

@app.post("/memory/delete")
def memory_delete(req: dict):
    """Delete a memory entry by its key/ID."""
    key = req.get("key") if isinstance(req, dict) else None
    if not key:
        raise HTTPException(status_code=400, detail="Please provide JSON body {\"key\":\"<id>\"}")
    return delete_memory(key)

@app.post("/debug-prompt")
def debug_prompt(payload: dict):
    """
    Debug endpoint to see the constructed prompt without running the model.
    Useful for testing and understanding how context is built.
    """
    question = payload.get("question")
    use_memory = payload.get("use_memory", False)
    use_search = payload.get("use_search", False)
    memory_texts = []
    if use_memory:
        try:
            res = query_memory(question, n_results=3)
            docs = res.get("documents", [])
            if docs and isinstance(docs[0], list):
                docs_flat = [d for sub in docs for d in sub]
            else:
                docs_flat = docs
            memory_texts = [d for d in docs_flat if d and d.strip()]
        except Exception:
            memory_texts = []

    search_texts = []
    if use_search:
        try:
            # Use tavily_search directly (same as main /ask endpoint)
            search_result = tavily_search(question, limit=3, return_metadata=False)
            for r in search_result:
                txt = fetch_best_text(r["link"])
                summary = (r.get("snippet") or "") + "\n" + (txt[:2000] if isinstance(txt, str) else "")
                if summary and summary.strip():
                    search_texts.append(f"{r.get('title','')} - {summary}")
        except Exception:
            search_texts = []

    prompt = build_prompt(question, memory_texts=memory_texts or None,
                          search_texts=search_texts or None)
    return {"prompt": prompt, "memory_texts": memory_texts, "search_texts": search_texts}
