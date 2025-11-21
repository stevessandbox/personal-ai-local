# app/main.py

import os
import time

# Load .env early so all modules that import environment variables see them.
# This ensures TAVILY_API_KEY and other vars are available when other modules import.
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from .model_client import run_local_model
from .memory import upsert_memory, query_memory, list_all_memories, delete_memory
from .search import duckduckgo_search, fetch_best_text, tavily_search
from .prompts import build_prompt

app = FastAPI(title="Personal AI Local API (with UI)")

# Serve the static UI from app/static
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    # Also serve assets from the static directory
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

class AskRequest(BaseModel):
    question: str
    use_memory: Optional[bool] = True
    use_search: Optional[bool] = True

class MemoryAddRequest(BaseModel):
    key: str
    text: str
    metadata: Optional[dict] = None

@app.get("/")
def index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return JSONResponse({"error": "UI not found. Make sure app/static/index.html exists."}, status_code=404)

@app.post("/ask")
def ask(req: AskRequest):
    timings = {}
    t0 = time.time()
    memory_texts = []
    if req.use_memory:
        t_mem_start = time.time()
        try:
            res = query_memory(req.question, n_results=3)
            docs = res.get("documents", [])
            if docs and isinstance(docs[0], list):
                docs_flat = [d for sub in docs for d in sub]
            else:
                docs_flat = docs
            memory_texts = [d for d in docs_flat if d and d.strip()]
        except Exception:
            memory_texts = []
        timings["memory_query"] = time.time() - t_mem_start

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
    t_search_start = time.time()
    if req.use_search:
        try:
            # Use tavily_search with metadata tracking
            t_api_start = time.time()
            search_result = tavily_search(req.question, limit=3, return_metadata=True)
            timings["tavily_api"] = time.time() - t_api_start
            
            if isinstance(search_result, dict) and "metadata" in search_result:
                results = search_result.get("results", [])
                tavily_info = search_result.get("metadata", tavily_info)
                # Ensure status is set based on success
                if tavily_info.get("success"):
                    tavily_info["status"] = "success"
                elif tavily_info.get("error"):
                    tavily_info["status"] = "error"
                else:
                    tavily_info["status"] = "failed"
            else:
                # Fallback if return_metadata wasn't used
                results = search_result if isinstance(search_result, list) else []
                tavily_info["called"] = True
                tavily_info["status"] = "success" if results else "failed"
                tavily_info["success"] = bool(results)
                tavily_info["results_count"] = len(results)
            
            t_fetch_start = time.time()
            for r in results:
                txt = fetch_best_text(r["link"], use_playwright_if_js=False)
                summary = (r.get("snippet") or "") + "\n" + (txt[:2000] if isinstance(txt, str) else "")
                if summary and summary.strip():
                    search_texts.append(f"{r.get('title','')} - {summary}")
            timings["fetch_best_text_total"] = time.time() - t_fetch_start
        except Exception as e:
            tavily_info["called"] = True
            tavily_info["status"] = "error"
            tavily_info["error"] = str(e)
            search_texts = []
    timings["search_total"] = time.time() - t_search_start

    t_prompt_start = time.time()
    prompt = build_prompt(req.question, memory_texts=memory_texts if memory_texts else None,
                          search_texts=search_texts if search_texts else None)
    timings["prompt_build"] = time.time() - t_prompt_start
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
    upsert_memory(req.key, req.text, metadata=req.metadata)
    return {"status": "ok"}

@app.get("/memory/query")
def memory_query(q: str, n_results: int = 4):
    res = query_memory(q, n_results=n_results)
    return res

@app.get("/memory/list")
def memory_list():
    return list_all_memories()

@app.post("/memory/delete")
def memory_delete(req: dict):
    key = req.get("key") if isinstance(req, dict) else None
    if not key:
        raise HTTPException(status_code=400, detail="Please provide JSON body {\"key\":\"<id>\"}")
    return delete_memory(key)

@app.post("/debug-prompt")
def debug_prompt(payload: dict):
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
            results = duckduckgo_search(question, limit=3)
            for r in results:
                txt = fetch_best_text(r["link"], use_playwright_if_js=False)
                summary = (r.get("snippet") or "") + "\n" + (txt[:2000] if isinstance(txt, str) else "")
                if summary and summary.strip():
                    search_texts.append(f"{r.get('title','')} - {summary}")
        except Exception:
            search_texts = []

    prompt = build_prompt(question, memory_texts=memory_texts if memory_texts else None,
                          search_texts=search_texts if search_texts else None)
    return {"prompt": prompt, "memory_texts": memory_texts, "search_texts": search_texts}
