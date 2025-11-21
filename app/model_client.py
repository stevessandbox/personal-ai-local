# app/model_client.py
import os
import subprocess

MODEL = os.getenv("MODEL_NAME", "llama3.1")

def run_local_model(prompt: str, max_tokens: int = 512, temperature: float = 0.2) -> str:
    """
    Run the local model using Ollama CLI by sending the prompt via STDIN.
    This approach is compatible across Ollama versions.
    """
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
