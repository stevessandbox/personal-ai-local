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

def build_prompt(question: str, memory_texts: List[str] = None, search_texts: List[str] = None, personality: str = None, has_images: bool = False, file_contents: List[str] = None) -> str:
    """
    Build a prompt with optional personality, memory context, search results, image analysis, and file content.
    
    Args:
        question: User's question
        memory_texts: Relevant memory excerpts
        search_texts: Web search result summaries
        personality: Optional personality description (e.g., "goth", "friendly", "professional")
        has_images: Whether images are being provided for analysis
        file_contents: List of extracted text content from uploaded files
    """
    # Build system prompt with personality if provided
    if has_images:
        # Special system prompt for image analysis
        if personality and personality.strip():
            personality_desc = personality.strip()
            system_prompt = (
                f"You are a helpful assistant with a STRONG {personality_desc} personality and vision capabilities. "
                f"Your {personality_desc} personality is ESSENTIAL and must be evident in EVERY response, especially when analyzing images. "
                f"Respond in a {personality_desc} style while being detailed and accurate in your image analysis. "
                f"When images are provided, carefully examine them and describe what you see, but ALWAYS do so through the lens of your {personality_desc} personality. "
                f"Your personality is not optional - it defines how you communicate. Every word you write should reflect your {personality_desc} nature. "
            )
        else:
            system_prompt = (
                "You are a helpful assistant with vision capabilities. "
                "You can see and analyze images. "
                "When images are provided, carefully examine them and describe what you see. "
                "Be detailed and accurate in your analysis. "
            )
    else:
        # Standard text-only system prompt
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
        parts.append("The following are from ALL previous interactions with the user. CRITICAL: Use ALL of this context to maintain conversation continuity and provide relevant, context-aware responses. ")
        parts.append("You have access to the complete conversation history - use it comprehensively. ")
        parts.append("When the user asks follow-up questions (like 'what breed is it?' or 'tell me more'), they are referring to topics from the most recent conversation above. ")
        parts.append("ALWAYS check the most recent interaction first - it contains the immediate context for the current question. ")
        parts.append("But also reference ANY relevant details from ANY of the interactions below when they relate to the current question. ")
        parts.append("Reference specific details from these conversations when relevant.\n\n")
        # Include ALL memory texts with smart truncation based on recency
        # Recent interactions get more characters, older ones get less to fit more in
        total_interactions = len(memory_texts)
        for i, m in enumerate(memory_texts, 1):
            # Truncation strategy: Most recent get more detail, older ones get less
            # This allows including many interactions while staying within context limits
            if i <= 5:
                # Top 5 most recent: 800 chars each
                truncate_length = 800
            elif i <= 15:
                # Next 10: 500 chars each
                truncate_length = 500
            elif i <= 30:
                # Next 15: 300 chars each
                truncate_length = 300
            else:
                # Older ones: 200 chars each
                truncate_length = 200
            
            truncated = m[:truncate_length] + "..." if len(m) > truncate_length else m
            # Mark interactions by recency
            if i <= 5:
                label = f"[Recent {i}/{total_interactions}]"
            elif i <= 15:
                label = f"[Recent {i}/{total_interactions}]"
            else:
                label = f"[Context {i}/{total_interactions}]"
            parts.append(f"{label} {truncated}\n")
        parts.append("\n=== END OF PREVIOUS CONVERSATIONS ===\n")
        parts.append("IMPORTANT: Maintain conversation continuity across ALL interactions. ")
        parts.append("You have access to the complete conversation history - use it to provide comprehensive, context-aware responses. ")
        parts.append("If the user asks a short follow-up question (like 'what breed is it?', 'tell me more', 'what about X?'), ")
        parts.append("they are almost certainly referring to the MOST RECENT conversation above. ")
        parts.append("But also consider if ANY earlier interactions are relevant to the current question. ")
        parts.append("Reference previous topics from ANY interaction, maintain personality consistency, and build upon earlier discussions throughout the entire conversation history.\n\n")
    if search_texts:
        parts.append("Search results (summaries):\n")
        # Limit search texts to top 2 and truncate each to 800 chars
        for i, s in enumerate(search_texts[:2], 1):
            truncated = s[:800] + "..." if len(s) > 800 else s
            parts.append(f"{i}. {truncated}\n")
        parts.append("\n")
    # Add file contents if provided
    if file_contents and len(file_contents) > 0:
        parts.append("=== UPLOADED FILES ===\n")
        parts.append("The following content is from files uploaded by the user. Use this information to answer their questions.\n\n")
        for i, content in enumerate(file_contents, 1):
            # Truncate very long files to prevent prompt bloat (keep first 5000 chars)
            truncated = content[:5000] + "\n[File content truncated...]" if len(content) > 5000 else content
            parts.append(f"File {i} content:\n{truncated}\n\n")
        parts.append("=== END OF UPLOADED FILES ===\n\n")
    
    parts.append(f"User question: {question}\n")
    
    # Add image analysis instruction if images are provided
    if has_images:
        if personality and personality.strip():
            personality_desc = personality.strip()
            parts.append(f"\nIMPORTANT: Analyze the image(s) provided and answer the user's question based on what you see in the image(s). "
                       f"CRITICAL: You MUST respond with a {personality_desc} personality and style. "
                       f"Describe the contents, objects, text, colors, composition, or any other relevant details, but do so in a {personality_desc} manner. "
                       f"Your entire response should reflect your {personality_desc} personality - this is not optional. "
                       f"Be specific and detailed in your analysis while maintaining your {personality_desc} personality throughout.\n")
        else:
            parts.append("\nIMPORTANT: Analyze the image(s) provided and answer the user's question based on what you see in the image(s). "
                       "Describe the contents, objects, text, colors, composition, or any other relevant details. "
                       "Be specific and detailed in your analysis.\n")
    else:
        parts.append("Answer succinctly. If you do not have supporting context, explicitly say you do not know.\n")
    
    return "\n".join(parts)
