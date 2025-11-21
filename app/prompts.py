# app/prompts.py
"""
Prompt building utilities for constructing context-aware prompts.

This module handles:
- System prompt definition
- Context assembly from memory and search results
- Text truncation for performance optimization
"""

from typing import List

# Base system prompt that defines the assistant's behavior
SYSTEM_BASE = (
    "You are a helpful private assistant. Be concise and honest. "
    "Only reference user memory or web search results if explicit excerpts are included in the prompt. "
    "If no such excerpts are present, do not imply you accessed memory or the web. "
    "When in doubt, say 'I do not have that information.'"
)

def build_prompt(question: str, memory_texts: List[str] = None, search_texts: List[str] = None, personality: str = None) -> str:
    """
    Build a prompt with optional personality, memory context, and search results.
    
    Args:
        question: User's question
        memory_texts: Relevant memory excerpts
        search_texts: Web search result summaries
        personality: Optional personality description (e.g., "goth", "friendly", "professional")
    """
    # Build system prompt with personality if provided
    system_prompt = SYSTEM_BASE
    if personality and personality.strip():
        personality_desc = personality.strip()
        system_prompt = (
            f"You are a helpful private assistant with a {personality_desc} personality. "
            f"Respond in a {personality_desc} style while being concise and honest. "
            "Only reference user memory or web search results if explicit excerpts are included in the prompt. "
            "If no such excerpts are present, do not imply you accessed memory or the web. "
            "When in doubt, say 'I do not have that information.'"
        )
    
    parts = [system_prompt, "\n\n"]
    if memory_texts:
        parts.append("=== PREVIOUS CONVERSATIONS AND MEMORIES ===\n")
        parts.append("The following are from previous interactions with the user. Use this information to answer their questions.\n\n")
        # Limit memory texts to top 5 (increased from 2) and truncate each to 500 chars
        # This allows including older interactions that are semantically relevant
        for i, m in enumerate(memory_texts[:5], 1):  # Increased from 2 to 5
            truncated = m[:500] + "..." if len(m) > 500 else m
            parts.append(f"{i}. {truncated}\n")
        parts.append("\n=== END OF PREVIOUS CONVERSATIONS ===\n\n")
    if search_texts:
        parts.append("Search results (summaries):\n")
        # Limit search texts to top 2 and truncate each to 800 chars
        for i, s in enumerate(search_texts[:2], 1):
            truncated = s[:800] + "..." if len(s) > 800 else s
            parts.append(f"{i}. {truncated}\n")
        parts.append("\n")
    parts.append(f"User question: {question}\n")
    parts.append("Answer succinctly. If you do not have supporting context, explicitly say you do not know.\n")
    return "\n".join(parts)
