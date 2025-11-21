# app/model_client.py
"""
Wrapper around Ollama CLI for running local LLM models.
Uses subprocess to communicate with Ollama, which handles GPU acceleration.
"""

import os
import subprocess

# Model name can be overridden via MODEL_NAME environment variable
# Default is llama3.1, but you can use any model installed in Ollama
MODEL = os.getenv("MODEL_NAME", "llama3.1")

def run_local_model(prompt: str, max_tokens: int = 256, temperature: float = 0.2) -> str:
    """
    Run the local model using Ollama CLI by sending the prompt via STDIN.
    Reduced max_tokens default to 256 for faster responses.
    This approach is compatible across Ollama versions.
    """
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
        text=True
    )
    stdout, stderr = proc.communicate(prompt)
    if proc.returncode != 0:
        raise RuntimeError(f"Model run failed: {stderr.strip()}")
    return stdout.strip()
