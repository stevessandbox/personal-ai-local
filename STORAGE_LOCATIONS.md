# Storage Locations

This document shows where all data is stored on your system.

## Storage Locations

### 1. Interaction Memory (ChromaDB)

**Location**: `D:\GitHubRepos\personal-ai-local\chroma_store\`

**What's stored**:
- All interactions (questions + answers)
- Memory entries (manually added)
- Personalities
- Vector embeddings for semantic search
- Metadata (timestamps, image paths, etc.)

**Format**: ChromaDB uses SQLite database + binary vector files

**Custom location**: Set `CHROMA_DIR` environment variable in `.env`:
```env
CHROMA_DIR=C:/path/to/custom/location
```

**View contents**:
- Via API: `GET http://localhost:8000/memory/list`
- Via interactions endpoint: `GET http://localhost:8000/memory/interactions?limit=50`
- Direct file access: SQLite file at `chroma_store/chroma.sqlite3`

### 2. Images

**Location**: `D:\GitHubRepos\personal-ai-local\image_store\`

**What's stored**:
- All uploaded images (up to 3 per interaction, max 10MB each)
- Stored with timestamp-based filenames

**Filename format**: `YYYYMMDD_HHMMSS_N.ext`
- Example: `20241121_143022_1.jpg`
- Example: `20241121_143022_2.png`

**Custom location**: Set `IMAGE_STORAGE_DIR` environment variable in `.env`:
```env
IMAGE_STORAGE_DIR=C:/path/to/custom/location
```

**Access images**:
- Via web: `http://localhost:8000/images/20241121_143022_1.jpg`
- Image paths are stored in interaction metadata in ChromaDB

### 3. Image Metadata in Memory

**Stored in**: ChromaDB (same as interactions)

**Metadata fields**:
- `images`: Comma-separated list of image paths (e.g., `/images/20241121_143022_1.jpg,/images/20241121_143022_2.png`)
- `image_count`: Number of images (as string)
- `timestamp`: Timestamp matching the image filenames

**Example metadata**:
```json
{
  "type": "interaction",
  "timestamp": "20241121_143022",
  "image_count": "2",
  "images": "/images/20241121_143022_1.jpg,/images/20241121_143022_2.png",
  "question": "What do you see?",
  "answer": "..."
}
```

## Directory Structure

```
D:\GitHubRepos\personal-ai-local\
├── chroma_store\              # Interaction memory (ChromaDB)
│   ├── chroma.sqlite3         # SQLite database with metadata
│   └── [vector index files]   # Binary vector embeddings
│
├── image_store\               # Uploaded images
│   ├── 20241121_143022_1.jpg
│   ├── 20241121_143022_2.png
│   └── ...
│
└── app\
    └── static\                # React UI (not data storage)
```

## Checking Storage Locations

### Check if directories exist:
```powershell
# Check ChromaDB storage
Test-Path "D:\GitHubRepos\personal-ai-local\chroma_store"

# Check image storage
Test-Path "D:\GitHubRepos\personal-ai-local\image_store"
```

### List stored images:
```powershell
Get-ChildItem "D:\GitHubRepos\personal-ai-local\image_store" | Select-Object Name, Length, LastWriteTime
```

### Check ChromaDB size:
```powershell
Get-ChildItem "D:\GitHubRepos\personal-ai-local\chroma_store" -Recurse | Measure-Object -Property Length -Sum
```

## Backup Recommendations

### To backup everything:
1. **ChromaDB**: Copy the entire `chroma_store/` directory
2. **Images**: Copy the entire `image_store/` directory

### To backup only interactions:
- Use the API: `GET /memory/list` and save the JSON
- Or copy `chroma_store/chroma.sqlite3`

### To backup only images:
- Copy the `image_store/` directory

## Environment Variables

You can customize storage locations by creating/editing `.env`:

```env
# ChromaDB storage location
CHROMA_DIR=C:/custom/path/to/memory

# Image storage location
IMAGE_STORAGE_DIR=C:/custom/path/to/images
```

**Note**: Use forward slashes (`/`) or double backslashes (`\\`) in Windows paths.

## Storage Size Estimates

- **ChromaDB**: ~1-5 KB per interaction (text + embeddings + metadata)
- **Images**: Actual file size (up to 10MB each, max 3 per interaction = 30MB per interaction with images)

## Cleanup

### Delete all interactions:
- Use API: `POST /memory/delete` for each interaction ID
- Or delete `chroma_store/` directory (will lose all memory)

### Delete all images:
- Delete files in `image_store/` directory
- Note: Image paths in memory will become broken links

### Delete specific interaction's images:
1. Get interaction metadata via API
2. Extract image paths from metadata
3. Delete image files from `image_store/`
4. (Optional) Update interaction metadata to remove image references

