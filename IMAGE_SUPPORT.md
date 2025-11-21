# Image Support Guide

## Overview

The system now supports image analysis using Ollama vision models. You can upload images and ask questions about them, and the AI will analyze and comment on the images.

## Setup

### 1. Install a Vision Model in Ollama

You need to install a vision-capable model in Ollama. Recommended models:

```bash
# Install LLaVA (recommended - good balance of speed and quality)
ollama pull llava

# Or install a larger model for better quality
ollama pull llava:13b

# Or install BakLLaVA (alternative)
ollama pull bakllava
```

### 2. Configure the Vision Model

Set the `VISION_MODEL_NAME` environment variable in your `.env` file:

```env
VISION_MODEL_NAME=llava
```

Or use the default (which is `llava`).

**Note**: The vision model is separate from your text model. You can use:
- `llama3.1` (or any text model) for text-only questions
- `llava` (or any vision model) for questions with images

The system automatically uses the vision model when images are provided.

### 3. Ensure Ollama API is Running

The vision model uses the Ollama API (not CLI). Make sure Ollama is running:

```bash
# Ollama should be running on localhost:11434 by default
# If you've changed the port, set OLLAMA_API_URL in .env
```

## Usage

### In the UI

1. **Upload Images**: Click the "Images (optional)" file input and select one or more images
2. **Preview**: Uploaded images will show as thumbnails with a remove button
3. **Ask Questions**: 
   - Type a question about the image(s)
   - Or leave the question blank - it will default to "What do you see in this image?"
4. **Submit**: Click "Ask" to get the AI's analysis

### Example Questions

- "What do you see in this image?"
- "Describe this image in detail"
- "What objects are in this picture?"
- "What's the mood of this image?"
- "Can you read the text in this image?"

## How It Works

1. **Image Upload**: Images are converted to base64 format in the browser
2. **API Call**: Images are sent to the backend as base64 strings (with data URL prefix)
3. **Model Selection**: 
   - If images are provided → Uses vision model (e.g., `llava`) via Ollama API
   - If no images → Uses text model (e.g., `llama3.1`) via Ollama CLI
4. **Analysis**: The vision model analyzes the image(s) and generates a response
5. **Memory**: The interaction (question + answer) is stored in memory, but images are not stored (only the text interaction)

## Technical Details

### Backend

- **Model Client** (`app/model_client.py`):
  - `run_local_model()` now accepts an optional `images` parameter
  - Automatically uses Ollama API for vision models
  - Uses Ollama CLI for text-only models (faster)

- **API Endpoint** (`/ask`):
  - Accepts `images` field in the request (list of base64 strings)
  - Passes images to the model client

### Frontend

- **Image Upload** (`src/components/AskPanel.tsx`):
  - File input with multiple image support
  - Converts images to base64 data URLs
  - Shows image previews with remove buttons
  - Sends images in the API request

### Memory Storage

**Note**: Images are NOT stored in memory. Only the text interaction (question + answer) is stored. This keeps the memory database small and efficient.

If you want to reference images later, you could:
- Describe the image in your question (e.g., "I showed you a photo of a cat")
- The AI will remember the description and analysis

## Limitations

1. **Image Size**: Large images will increase request size. Consider resizing very large images before upload.
2. **Multiple Images**: You can upload multiple images, but processing time increases with each image.
3. **Model Performance**: Vision models are slower than text models. Expect 5-30 seconds for image analysis.
4. **Storage**: Images are not stored - only the text conversation is saved to memory.

## Troubleshooting

### "Vision model API call failed"

- **Check Ollama is running**: `ollama list` should work
- **Check model is installed**: `ollama list` should show your vision model
- **Check API URL**: Default is `http://localhost:11434`. Set `OLLAMA_API_URL` if different.

### "Model not found"

- Install the vision model: `ollama pull llava`
- Set `VISION_MODEL_NAME=llava` in `.env`

### Images not uploading

- Check browser console for errors
- Ensure images are valid image files (jpg, png, gif, webp, etc.)
- Check file size (very large files may timeout)

## Environment Variables

```env
# Vision model name (default: llava)
VISION_MODEL_NAME=llava

# Ollama API URL (default: http://localhost:11434)
OLLAMA_API_URL=http://localhost:11434

# Text model name (default: llama3.1)
MODEL_NAME=llama3.1
```

## Future Enhancements

Possible improvements:
- Store image thumbnails in memory
- Support for image URLs (not just uploads)
- Batch image analysis
- Image search in memory
- Image-to-image comparisons

