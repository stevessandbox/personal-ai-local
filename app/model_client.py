# app/model_client.py
"""
Wrapper around Ollama for running local LLM models.
Supports both text-only and vision models (with image analysis).
Uses Ollama API for vision models (image support) and CLI for text-only models.
"""

import os
import subprocess
import base64
import requests
import logging
from typing import Optional, List

# Model name can be overridden via MODEL_NAME environment variable
# Default is llama3.1, but you can use any model installed in Ollama
# For vision support, use a vision model like: llava, bakllava, llava:13b, etc.
MODEL = os.getenv("MODEL_NAME", "llama3.1")
# Vision model can be different from text model (e.g., "llava" for image analysis)
VISION_MODEL = os.getenv("VISION_MODEL_NAME", "llava")
# Ollama API base URL (defaults to localhost)
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")

def run_local_model(prompt: str, max_tokens: int = 256, temperature: float = 0.2, images: Optional[List[str]] = None) -> str:
    """
    Run the local model using Ollama.
    
    For vision models with images, uses Ollama API.
    For text-only models, uses Ollama CLI (faster for text-only).
    
    Args:
        prompt: Text prompt to send to the model
        max_tokens: Maximum tokens to generate (default: 256)
        temperature: Sampling temperature (default: 0.2)
        images: Optional list of base64-encoded image strings
    
    Returns:
        Model response as string
    """
    # If images are provided, use vision model via API
    if images and len(images) > 0:
        return _run_vision_model(prompt, images, max_tokens, temperature)
    else:
        return _run_text_model(prompt, max_tokens, temperature)

def _run_text_model(prompt: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
    """Run text-only model using Ollama CLI (faster for text-only)."""
    # Truncate prompt if too long to speed up processing
    # Most models work well with ~2000-3000 tokens of context
    max_prompt_length = 3000
    if len(prompt) > max_prompt_length:
        prompt = prompt[:max_prompt_length] + "\n[Context truncated for speed]"
    
    cmd = ["ollama", "run", MODEL]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'  # Replace invalid characters instead of failing
    )
    stdout, stderr = proc.communicate(prompt)
    if proc.returncode != 0:
        raise RuntimeError(f"Model run failed: {stderr.strip()}")
    return stdout.strip()

def _run_vision_model(prompt: str, images: List[str], max_tokens: int = 256, temperature: float = 0.2) -> str:
    """
    Run vision model using Ollama API with image support.
    
    Args:
        prompt: Text prompt
        images: List of base64-encoded image strings (without data URL prefix)
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
    
    Returns:
        Model response as string
    """
    # Prepare images for Ollama API (it expects base64 strings)
    # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,")
    processed_images = []
    for img in images:
        if ',' in img:
            # Remove data URL prefix
            img = img.split(',', 1)[1]
        processed_images.append(img)
    
    # Call Ollama API for vision model
    # Ollama uses /api/generate for both text and vision models
    # The images parameter in the payload tells it to use vision capabilities
    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "stream": False,
        "images": processed_images,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature
        }
    }
    
    try:
        # First, check if Ollama is running
        try:
            health_check = requests.get(f"{OLLAMA_API_URL}/api/tags", timeout=5)
            if health_check.status_code != 200:
                raise RuntimeError(f"Ollama API not accessible. Status: {health_check.status_code}. Is Ollama running?")
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Ollama API at {OLLAMA_API_URL}. Is Ollama running? Start it with: ollama serve")
        
        # Try the generate endpoint
        api_url = f"{OLLAMA_API_URL}/api/generate"
        response = requests.post(
            api_url,
            json=payload,
            timeout=300  # 5 minute timeout for vision models (they're slower)
        )
        
        if response.status_code == 404:
            # Endpoint not found - might be API version issue
            raise RuntimeError(
                f"Ollama API endpoint not found. "
                f"Make sure Ollama is running and the vision model '{VISION_MODEL}' is installed. "
                f"Install it with: ollama pull {VISION_MODEL}"
            )
        
        response.raise_for_status()
        result = response.json()
        
        # Handle response format
        if "response" in result:
            return result.get("response", "").strip()
        elif "message" in result and isinstance(result["message"], dict) and "content" in result["message"]:
            return result["message"]["content"].strip()
        else:
            # Fallback: return string representation
            logging.warning(f"Unexpected Ollama response format: {list(result.keys())}")
            return str(result).strip()
            
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            f"Cannot connect to Ollama API at {OLLAMA_API_URL}. "
            f"Is Ollama running? Start it with: ollama serve"
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Vision model API call failed: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Vision model failed: {str(e)}")
