# app/memory.py
import os
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# Directory to store the Chroma DB
CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_store")

# Embedding model (small, fast)
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

# Initialize embedder
embedder = SentenceTransformer(EMBED_MODEL_NAME)

# Modern Chroma client (new architecture)
client = chromadb.Client(Settings(persist_directory=CHROMA_DIR))

# Ensure collection exists
COLLECTION_NAME = "personal_memory"
collections = [c.name for c in client.list_collections()]
if COLLECTION_NAME not in collections:
    collection = client.create_collection(name=COLLECTION_NAME)
else:
    collection = client.get_collection(COLLECTION_NAME)


def embed_texts(texts: List[str]):
    """Embed text into vector embeddings."""
    return embedder.encode(texts, convert_to_numpy=True)


def upsert_memory(key: str, text: str, metadata: Dict[str, Any] = None):
    """
    Upsert memory into Chroma.
    Fix: Only pass metadatas to Chroma if metadata is a non-empty dict.
    """
    vecs = embed_texts([text])
    col = client.get_collection(COLLECTION_NAME)

    # Only include metadata if actually provided and non-empty
    if metadata and isinstance(metadata, dict) and len(metadata.keys()) > 0:
        col.upsert(
            ids=[key],
            documents=[text],
            metadatas=[metadata],
            embeddings=vecs.tolist()
        )
    else:
        # Do NOT send an empty dict to Chroma → it will throw a ValueError
        col.upsert(
            ids=[key],
            documents=[text],
            embeddings=vecs.tolist()
        )


def query_memory(query: str, n_results: int = 4):
    """Query the memory store using similarity search."""
    qvec = embed_texts([query])[0].tolist()
    results = client.get_collection(COLLECTION_NAME).query(
        query_embeddings=[qvec],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )
    return results


def list_all_memories():
    """
    Return all memory entries (ids, documents, metadata).
    NOTE: Chroma's `get` accept include keys: `documents`, `metadatas`, `embeddings`.
    We request documents+metadatas (and embeddings to be safe) and then return ids
    if present in the response.
    """
    col = client.get_collection(COLLECTION_NAME)
    try:
        # Request the valid include keys. Embeddings are optional but harmless for small stores.
        rows = col.get(include=["documents", "metadatas", "embeddings"])
        # Chroma typically returns 'ids' alongside these fields; fallback to empty list if missing.
        return {
            "ids": rows.get("ids", []),
            "documents": rows.get("documents", []),
            "metadatas": rows.get("metadatas", [])
        }
    except Exception as e:
        return {"error": str(e)}


def delete_memory(key: str):
    """Delete a memory entry by its ID."""
    col = client.get_collection(COLLECTION_NAME)
    col.delete(ids=[key])
    return {"deleted": key}
