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
import logging
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
from typing import Optional, List
from .model_client import run_local_model
from .memory import upsert_memory, query_memory, list_all_memories, delete_memory
from .search import fetch_best_text, tavily_search
from .prompts import build_prompt
from .file_parser import parse_file

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

# Image storage directory (for storing uploaded images with timestamps)
IMAGE_STORAGE_DIR = os.getenv("IMAGE_STORAGE_DIR", "./image_store")
os.makedirs(IMAGE_STORAGE_DIR, exist_ok=True)

# File storage directory (for storing uploaded documents with timestamps)
FILE_STORAGE_DIR = os.getenv("FILE_STORAGE_DIR", "./file_store")
os.makedirs(FILE_STORAGE_DIR, exist_ok=True)

# Serve stored images and files
app.mount("/images", StaticFiles(directory=IMAGE_STORAGE_DIR), name="images")
app.mount("/files", StaticFiles(directory=FILE_STORAGE_DIR), name="files")

# Request/Response models
class FileData(BaseModel):
    """File data model for uploaded files."""
    name: str
    content: str  # Base64-encoded file content
    type: str     # MIME type

class AskRequest(BaseModel):
    """Request model for asking questions."""
    question: str
    use_memory: Optional[bool] = True  # Whether to query memory store
    use_search: Optional[bool] = True   # Whether to use web search
    personality: Optional[str] = None  # Optional personality description (e.g., "goth", "friendly")
    images: Optional[List[str]] = None  # Optional list of base64-encoded images (with data URL prefix)
    files: Optional[List[FileData]] = None  # Optional list of uploaded files

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
    
    # Validate request - allow empty question if images are provided
    has_images = req.images is not None and len(req.images) > 0
    has_question = req.question and req.question.strip()
    if not has_question and not has_images:
        raise HTTPException(status_code=400, detail="Question or images required")
    
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
        """Fetch relevant memories from vector store, including past interactions."""
        if not req.use_memory:
            return []
        try:
            # Strategy: Always include the most recent interaction(s) for context continuity
            # Then add semantically similar memories
            
            # Step 1: Get the most recent interactions directly (by timestamp)
            # Cache the full memory list to avoid repeated calls
            all_memories = list_all_memories()
            ids = all_memories.get("ids", [])
            documents = all_memories.get("documents", [])
            metadatas = all_memories.get("metadatas", [])
            
            # Early return if no memories
            if not metadatas or len(metadatas) == 0:
                return []
            
            # Filter and sort interactions by timestamp (newest first)
            recent_interactions = []
            for i, meta in enumerate(metadatas):
                if meta and meta.get("type") == "interaction":
                    doc = documents[i] if i < len(documents) else ""
                    if doc and doc.strip():
                        timestamp = meta.get("timestamp", "")
                        recent_interactions.append({
                            "doc": doc,
                            "timestamp": timestamp,
                            "id": ids[i] if i < len(ids) else None
                        })
            
            # Sort by timestamp (newest first) - timestamp format is YYYYMMDD_HHMMSS
            # This ensures most recent interactions come first
            recent_interactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Debug: Log what interactions we found
            logging.info(f"Total memories: {len(metadatas)}, Interactions found: {len(recent_interactions)}")
            if recent_interactions:
                logging.info(f"Most recent interaction timestamp: {recent_interactions[0].get('timestamp', 'no timestamp')}")
                logging.info(f"Most recent interaction preview: {recent_interactions[0].get('doc', '')[:100]}...")
            else:
                logging.warning("No interactions found in memory store")
            
            # Get the 5 most recent interaction texts (for strong context continuity)
            # Always prioritize recent interactions to maintain conversation flow
            recent_docs = [x["doc"] for x in recent_interactions[:5]]
            recent_docs_set = set(recent_docs)  # For deduplication
            
            # Step 2: Also do semantic search for similar memories
            # Increased n_results to 20 to better find older interactions (50+ interactions ago)
            semantic_results = []
            semantic_with_distances = []  # Store with similarity scores
            try:
                res = query_memory(req.question, n_results=20)  # Increased from 15 to 20 for better coverage
                docs = res.get("documents", [])
                metadatas_sem = res.get("metadatas", [])
                distances = res.get("distances", [])
                
                # Handle nested list structure from Chroma
                if docs and isinstance(docs[0], list):
                    docs_flat = [d for sub in docs for d in sub]
                    distances_flat = [d for sub in distances for d in sub] if distances else []
                else:
                    docs_flat = docs
                    distances_flat = distances if distances else []
                
                # Collect semantically similar memories with their similarity scores
                # Lower distance = higher similarity
                for i, doc in enumerate(docs_flat):
                    if doc and doc.strip() and doc not in recent_docs_set:
                        distance = distances_flat[i] if i < len(distances_flat) else 1.0
                        semantic_with_distances.append((doc, distance))
                
                # Sort by similarity (lower distance = more similar)
                semantic_with_distances.sort(key=lambda x: x[1])
                semantic_results = [doc for doc, _ in semantic_with_distances]
            except Exception as e:
                logging.warning(f"Semantic memory query failed: {e}")
            
            # Step 3: Combine: recent interactions first (up to 5), then best semantic matches (up to 10 total)
            # Increased total from 5 to 10 to include more context for stronger continuity
            result = list(recent_docs)  # Start with recent interactions (up to 5)
            
            # Add semantically similar memories (up to 10 total)
            # This ensures we can find interactions from 50+ interactions ago if they're semantically relevant
            # while still maintaining strong recent context
            for sem_doc in semantic_results:
                if len(result) >= 10:  # Increased from 5 to 10
                    break
                if sem_doc and sem_doc.strip():
                    result.append(sem_doc)
            
            # Debug logging
            logging.info(f"Memory query: Found {len(recent_interactions)} interactions, returning {len(result)} memories")
            if result:
                logging.info(f"First memory preview: {result[0][:100]}...")
            
            return result
        except Exception as e:
            logging.error(f"Memory query failed: {e}", exc_info=True)
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

    # Process uploaded files: save to disk and extract text content
    file_contents = []
    stored_file_paths = []
    if req.files and len(req.files) > 0:
        try:
            import base64
            from datetime import datetime
            file_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            for i, file_data in enumerate(req.files):
                try:
                    # Decode base64 file content
                    file_bytes = base64.b64decode(file_data["content"])
                    
                    # Determine file extension from name or type
                    filename = file_data.get("name", f"file_{i+1}")
                    ext = os.path.splitext(filename)[1] or ".txt"
                    if not ext.startswith('.'):
                        ext = '.' + ext
                    
                    # Create filename with timestamp
                    safe_filename = f"{file_timestamp}_{i+1}_{filename.replace(' ', '_').replace('/', '_')}"
                    filepath = os.path.join(FILE_STORAGE_DIR, safe_filename)
                    
                    # Save file to disk
                    with open(filepath, 'wb') as f:
                        f.write(file_bytes)
                    
                    # Parse file and extract text content
                    text_content, error = parse_file(filepath)
                    if text_content:
                        file_contents.append(text_content)
                        stored_file_paths.append(f"/files/{safe_filename}")
                        logging.info(f"Stored and parsed file: {safe_filename} ({len(file_bytes)} bytes, {len(text_content)} chars extracted)")
                    else:
                        logging.warning(f"Failed to parse file {filename}: {error}")
                        stored_file_paths.append(f"/files/{safe_filename}")  # Still store path even if parsing failed
                except Exception as e:
                    logging.warning(f"Failed to process file {i+1}: {e}")
        except Exception as e:
            logging.warning(f"Failed to process files: {e}")
    
    # Build prompt with context from memory and/or search, and personality
    t_prompt_start = time.time()
    # Debug: Log what memory texts we're including (only in debug mode to reduce logging overhead)
    if memory_texts and logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f"Building prompt with {len(memory_texts)} memory texts")
        for i, mem in enumerate(memory_texts):
            logging.debug(f"  Memory {i+1}: {mem[:150]}...")
    
    # Check if images are provided for prompt customization
    has_images = req.images is not None and len(req.images) > 0
    if has_images and logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f"Building prompt with image analysis instructions for {len(req.images)} image(s)")
    
    if file_contents and logging.getLogger().isEnabledFor(logging.DEBUG):
        logging.debug(f"Building prompt with {len(file_contents)} file(s) content")
    
    # Ensure personality is passed even when images are present
    prompt = build_prompt(
        req.question, 
        memory_texts=memory_texts or None,
        search_texts=search_texts or None, 
        personality=req.personality,  # Explicitly pass personality
        has_images=has_images, 
        file_contents=file_contents if file_contents else None
    )
    
    # Log personality usage for debugging
    if req.personality and req.personality.strip():
        logging.info(f"Using personality: {req.personality.strip()}")
    timings["prompt_build"] = time.time() - t_prompt_start
    
    # Run model inference via Ollama (with image support if images provided)
    t_model_start = time.time()
    try:
        # Pass images to model if provided (for vision model analysis)
        # Only pass images parameter if images are actually provided and not empty
        if req.images is not None and len(req.images) > 0:
            logging.info(f"Running vision model with {len(req.images)} image(s)")
            out = run_local_model(prompt, images=req.images)
        else:
            logging.info("Running text-only model")
            out = run_local_model(prompt)
    except Exception as e:
        logging.error(f"Model inference failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Model inference failed: {str(e)}")
    timings["model_run"] = time.time() - t_model_start
    timings["total"] = time.time() - t0
    
    # Store images to disk if provided (before storing interaction in memory)
    stored_image_paths = []
    from datetime import datetime
    import base64
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if req.images and len(req.images) > 0:
        try:
            
            for i, img_data in enumerate(req.images):
                try:
                    # Extract base64 data and determine file extension
                    if ',' in img_data:
                        header, data = img_data.split(',', 1)
                        # Get mime type from header (e.g., "data:image/jpeg;base64")
                        mime_type = header.split(';')[0].split(':')[1]
                        ext_map = {
                            'image/jpeg': 'jpg',
                            'image/jpg': 'jpg',
                            'image/png': 'png',
                            'image/gif': 'gif',
                            'image/webp': 'webp'
                        }
                        ext = ext_map.get(mime_type, 'jpg')
                    else:
                        data = img_data
                        ext = 'jpg'  # Default extension
                    
                    # Create filename with timestamp
                    filename = f"{timestamp}_{i+1}.{ext}"
                    filepath = os.path.join(IMAGE_STORAGE_DIR, filename)
                    
                    # Decode and save image
                    image_bytes = base64.b64decode(data)
                    with open(filepath, 'wb') as f:
                        f.write(image_bytes)
                    
                    # Store relative path for serving
                    stored_image_paths.append(f"/images/{filename}")
                    logging.info(f"Stored image: {filename} ({len(image_bytes)} bytes)")
                except Exception as e:
                    logging.warning(f"Failed to store image {i+1}: {e}")
        except Exception as e:
            logging.warning(f"Failed to store images: {e}")
    
    # Store the interaction (question + answer) in memory for future reference
    # This happens AFTER getting the answer, so it will be available for future questions
    # Use the same timestamp as image storage for consistency
    try:
        interaction_id = f"interaction_{timestamp}_{hashlib.md5(req.question.encode()).hexdigest()[:8]}"
        
        # Store as a conversation pair: question and answer together
        # Include both question and answer in the text for better semantic matching
        interaction_text = f"Q: {req.question}\nA: {out}"
        
        # ChromaDB only accepts str, int, or float in metadata - convert booleans to strings
        metadata = {
            "type": "interaction",
            "question": req.question,
            "answer": out,
            "timestamp": timestamp,
            "used_memory": "true" if req.use_memory else "false",
            "used_search": "true" if req.use_search else "false"
        }
        if req.personality:
            metadata["personality"] = req.personality
        
        # Add image paths if images were stored
        if stored_image_paths:
            metadata["image_count"] = str(len(stored_image_paths))
            metadata["images"] = ",".join(stored_image_paths)  # Comma-separated list of image paths
        
        # Add file paths if files were stored
        if stored_file_paths:
            metadata["file_count"] = str(len(stored_file_paths))
            metadata["files"] = ",".join(stored_file_paths)  # Comma-separated list of file paths
        
        upsert_memory(
            interaction_id,
            interaction_text,
            metadata=metadata
        )
        # Invalidate cache for this question to ensure fresh results next time
        cache_key = f"mem:{hashlib.md5(req.question.encode()).hexdigest()}"
        if cache_key in _query_cache:
            del _query_cache[cache_key]
        logging.info(f"Stored interaction: {interaction_id[:50]}... | Memory texts found: {len(memory_texts)}")
    except Exception as e:
        # Don't fail the request if interaction storage fails
        logging.error(f"Failed to store interaction: {e}", exc_info=True)
    
    # Store personality in memory if provided (for future use in dropdown)
    if req.personality and req.personality.strip():
        try:
            personality_key = f"personality:{hashlib.md5(req.personality.strip().lower().encode()).hexdigest()}"
            upsert_memory(
                personality_key,
                req.personality.strip(),
                metadata={"type": "personality", "created_from": "interaction"}
            )
        except Exception:
            # Don't fail the request if personality storage fails
            pass
    
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

@app.get("/memory/interactions")
def list_interactions(limit: int = 10):
    """List recent interactions (for debugging)."""
    try:
        all_memories = list_all_memories()
        ids = all_memories.get("ids", [])
        documents = all_memories.get("documents", [])
        metadatas = all_memories.get("metadatas", [])
        
        # Filter for interactions only
        interactions = []
        for i, meta in enumerate(metadatas):
            if meta and meta.get("type") == "interaction":
                interactions.append({
                    "id": ids[i] if i < len(ids) else None,
                    "document": documents[i] if i < len(documents) else None,
                    "metadata": meta
                })
        
        # Sort by timestamp (newest first) and limit
        interactions.sort(key=lambda x: x.get("metadata", {}).get("timestamp", ""), reverse=True)
        return {"interactions": interactions[:limit], "total": len(interactions)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/chat/history")
def get_chat_history(limit: int = 100):
    """
    Get chat history with all interactions formatted for display.
    Returns interactions sorted by timestamp (oldest first for chat view).
    """
    try:
        all_memories = list_all_memories()
        ids = all_memories.get("ids", [])
        documents = all_memories.get("documents", [])
        metadatas = all_memories.get("metadatas", [])
        
        # Filter for interactions only
        interactions = []
        for i, meta in enumerate(metadatas):
            if meta and meta.get("type") == "interaction":
                doc = documents[i] if i < len(documents) else ""
                # Parse Q: and A: from document
                question = ""
                answer = ""
                if doc:
                    if "Q: " in doc and "A: " in doc:
                        parts = doc.split("A: ", 1)
                        question = parts[0].replace("Q: ", "").strip()
                        answer = parts[1].strip() if len(parts) > 1 else ""
                    else:
                        # Fallback: use metadata
                        question = meta.get("question", "")
                        answer = meta.get("answer", "")
                
                # Extract image and file paths
                image_paths = []
                file_paths = []
                if meta.get("images"):
                    image_paths = [img.strip() for img in meta.get("images", "").split(",") if img.strip()]
                if meta.get("files"):
                    file_paths = [f.strip() for f in meta.get("files", "").split(",") if f.strip()]
                
                # Format timestamp for display
                timestamp_str = meta.get("timestamp", "")
                display_timestamp = ""
                if timestamp_str:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        display_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        display_timestamp = timestamp_str
                
                interactions.append({
                    "id": ids[i] if i < len(ids) else None,
                    "timestamp": timestamp_str,
                    "display_timestamp": display_timestamp,
                    "question": question or meta.get("question", ""),
                    "answer": answer or meta.get("answer", ""),
                    "images": image_paths,
                    "files": file_paths,
                    "personality": meta.get("personality"),
                    "used_memory": meta.get("used_memory") == "true",
                    "used_search": meta.get("used_search") == "true"
                })
        
        # Sort by timestamp (oldest first for chat view - chronological order)
        interactions.sort(key=lambda x: x.get("timestamp", ""))
        logging.info(f"Chat history: Found {len(interactions)} interactions, returning last {min(limit, len(interactions))}")
        return {"interactions": interactions[-limit:], "total": len(interactions)}
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}", exc_info=True)
        return {"error": str(e), "interactions": []}

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
    personality = payload.get("personality")
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

    # Debug endpoint doesn't support images, so has_images is always False
    prompt = build_prompt(question, memory_texts=memory_texts or None,
                          search_texts=search_texts or None, personality=personality,
                          has_images=False)
    return {"prompt": prompt, "memory_texts": memory_texts, "search_texts": search_texts}

@app.get("/personalities")
def list_personalities():
    """
    Endpoint to list all stored personalities.
    Returns all memories with metadata type 'personality'.
    """
    all_memories = list_all_memories()
    personalities = []
    ids = all_memories.get("ids", [])
    docs = all_memories.get("documents", [])
    metas = all_memories.get("metadatas", [])
    
    # Extract unique personalities (deduplicate by text content)
    seen = set()
    for i, meta in enumerate(metas):
        if meta and meta.get("type") == "personality":
            personality_text = docs[i] if i < len(docs) else ""
            # Use lowercase for deduplication
            key = personality_text.lower().strip()
            if key and key not in seen:
                seen.add(key)
                personalities.append({
                    "id": ids[i] if i < len(ids) else f"personality_{i}",
                    "text": personality_text
                })
    
    # Sort by text for consistent ordering
    personalities.sort(key=lambda x: x["text"].lower())
    return {"personalities": personalities}
