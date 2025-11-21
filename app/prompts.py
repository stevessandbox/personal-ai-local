# app/prompts.py
from typing import List

SYSTEM_BASE = (
    "You are a helpful private assistant. Be concise and honest. "
    "Only reference user memory or web search results if explicit excerpts are included in the prompt. "
    "If no such excerpts are present, do not imply you accessed memory or the web. "
    "When in doubt, say 'I do not have that information.'"
)

def build_prompt(question: str, memory_texts: List[str] = None, search_texts: List[str] = None) -> str:
    parts = [SYSTEM_BASE, "\n\n"]
    if memory_texts:
        parts.append("User memory (relevant excerpts):\n")
        for i, m in enumerate(memory_texts, 1):
            parts.append(f"{i}. {m}\n")
        parts.append("\n")
    if search_texts:
        parts.append("Search results (summaries):\n")
        for i, s in enumerate(search_texts, 1):
            parts.append(f"{i}. {s}\n")
        parts.append("\n")
    parts.append(f"User question: {question}\n")
    parts.append("Answer succinctly. If you do not have supporting context, explicitly say you do not know.\n")
    return "\n".join(parts)
