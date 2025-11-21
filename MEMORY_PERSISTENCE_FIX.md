# Memory Persistence Fix

## Issue
Memory and chat history were being lost when the server restarted because ChromaDB was using an in-memory client instead of a persistent client.

## Fix Applied
Changed from:
```python
client = chromadb.Client(Settings(persist_directory=CHROMA_DIR))
```

To:
```python
client = chromadb.PersistentClient(path=CHROMA_DIR)
```

## What This Means

### Before (In-Memory)
- Data stored in RAM only
- Lost when server restarts
- No disk persistence

### After (Persistent)
- Data stored on disk in `./chroma_store/` directory
- Survives server restarts
- All interactions, memories, and personalities are preserved

## Storage Location

- **Default**: `./chroma_store/` (in project root)
- **Custom**: Set `CHROMA_DIR` environment variable in `.env`

## Verification

After restarting the server:
1. Chat history should show all previous interactions
2. Memory entries should still be available
3. Saved personalities should still be in the dropdown

## Migration

If you had previous interactions that were lost:
- They cannot be recovered (they were never persisted)
- New interactions going forward will be persisted
- The `chroma_store/` directory will be created automatically on first use


