# Memory System Information

## Storage Location

Memories are stored in the **`chroma_store`** directory (default location).

- **Default path**: `./chroma_store/` (in the project root)
- **Custom path**: Set `CHROMA_DIR` environment variable to change location
- **Storage format**: ChromaDB uses SQLite for metadata and binary files for vector embeddings

## Memory Limits

### Current Limits

1. **Storage Limit**: **No hard limit** - limited only by available disk space

   - Each interaction stores:
     - Text (question + answer)
     - Vector embedding (384 dimensions)
     - Metadata (timestamp, type, etc.)
   - Rough estimate: ~1-5 KB per interaction (depending on text length)

2. **Query Limits** (performance optimizations):

   - **Recent interactions**: Always includes the 2 most recent interactions
   - **Semantic search**: Queries up to 5 results, then returns top 3 total
   - **Prompt context**: Only top 2 memories are included in prompts (truncated to 500 chars each)

3. **In-memory cache**: Limited to 100 query results (for speed)

## Cost of "Infinite" Memory

### Current State: Effectively Unlimited

The memory system is **already effectively unlimited** for practical purposes:

- **No code changes needed** - ChromaDB handles large datasets efficiently
- **Cost**: Only disk space (free, local storage)
- **Performance**: ChromaDB uses efficient indexing, so query speed stays good even with thousands of memories

### Storage Estimates

- **1,000 interactions**: ~1-5 MB
- **10,000 interactions**: ~10-50 MB
- **100,000 interactions**: ~100-500 MB
- **1,000,000 interactions**: ~1-5 GB

### Potential Issues with Very Large Memory

1. **Query Performance**:

   - Current: Queries 5 results, returns top 3
   - With millions of memories: May need to increase `n_results` parameter
   - Solution: ChromaDB's HNSW index handles this well

2. **Prompt Size**:

   - Current: Only top 2 memories included (500 chars each)
   - This prevents prompt bloat regardless of total memory size
   - Model context window is the real limit (currently ~3000 chars)

3. **Startup Time**:
   - ChromaDB loads metadata on startup
   - With millions of memories: May add 1-2 seconds to startup
   - Not a significant issue

## Viewing Stored Memories

### Option 1: Via API Endpoint

```
GET http://localhost:8000/memory/list
```

Returns all memories with IDs, documents, and metadata.

### Option 2: Via Interactions Endpoint

```
GET http://localhost:8000/memory/interactions?limit=50
```

Returns recent interactions only (sorted by timestamp).

### Option 3: Direct File Access

The `chroma_store` directory contains:

- `chroma.sqlite3` - SQLite database with metadata
- Vector index files (binary format)
- Collection metadata

**Note**: The files are in ChromaDB's internal format. Use the API endpoints to view human-readable content.

## Recommendations

### For Most Users: Current Setup is Fine

- No changes needed
- Handles thousands of interactions efficiently
- Query performance remains fast

### For Heavy Users (10,000+ interactions):

1. **Increase query results** (if needed):

   ```python
   # In app/main.py, line 186
   res = query_memory(req.question, n_results=10)  # Increase from 5
   ```

2. **Increase prompt context** (if needed):

   ```python
   # In app/prompts.py, line 47
   for i, m in enumerate(memory_texts[:5], 1):  # Increase from 2
       truncated = m[:1000] + "..." if len(m) > 1000 else m  # Increase from 500
   ```

3. **Monitor disk usage**: Check `chroma_store` directory size periodically

### For Extreme Users (100,000+ interactions):

- Consider periodic cleanup of old interactions
- Implement memory pruning based on age or relevance
- May want to increase query `n_results` to 10-20

## Summary

✅ **Current limit**: Disk space only (effectively unlimited)  
✅ **Cost**: Free (local disk storage)  
✅ **Performance**: Good up to 100,000+ interactions  
✅ **View memories**: Use `/memory/list` or `/memory/interactions` API endpoints  
✅ **Storage location**: `./chroma_store/` directory

The system is designed to scale well without modifications!
