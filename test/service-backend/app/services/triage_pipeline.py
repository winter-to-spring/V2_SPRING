"""
LangGraph-based triage pipeline for message classification, summarization, and embedding.

Provides a StateGraph with nodes for:
1. classify: Determine triage level (critical/high/medium/low) using OpenAI gpt-4o-mini
2. summarize: Generate 1-2 sentence summary
3. hash_embed: Create md5-based embedding hash for pgvector integration

Includes deterministic offline fallback when OPENAI_API_KEY is unavailable.
"""

import hashlib
import json
import os
import re
from enum import Enum
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END


class TriageLevel(str, Enum):
    """Triage priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChannelPriority(str, Enum):
    """Channel-derived priority hints."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TriageState(TypedDict):
    """State schema for triage pipeline."""
    raw_text: str
    channel_priority: str  # One of ChannelPriority enum values
    triage_level: str  # One of TriageLevel enum values
    summary: str
    embedding_hash: str


def _classify_with_fallback(text: str, channel_priority: str) -> str:
    """
    Classify text into triage level using OpenAI or deterministic fallback.
    
    Args:
        text: Raw text to classify
        channel_priority: Channel-derived priority hint
        
    Returns:
        Triage level (critical/high/medium/low)
    """
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    
    if api_key:
        # Use OpenAI with structured output
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=api_key)
            
            classification_schema = {
                "type": "json_schema",
                "json_schema": {
                    "name": "TriageClassification",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": ["critical", "high", "medium", "low"],
                                "description": "Triage priority level"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief reasoning for classification"
                            }
                        },
                        "required": ["level", "reasoning"]
                    },
                    "strict": True
                }
            }
            
            response = client.beta.messages.create(
                model="gpt-4o-mini",
                max_tokens=256,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Classify this message by priority.
Channel priority hint: {channel_priority}

Message:
{text}

Respond with JSON containing 'level' and 'reasoning'."""
                    }
                ],
                betas=["interleaved-thinking-2025-05-14"],
                response_model=None,
            )
            
            # Parse structured response
            try:
                response_text = response.content[0].text
                parsed = json.loads(response_text)
                level = parsed.get("level", channel_priority).lower()
                if level in ["critical", "high", "medium", "low"]:
                    return level
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
        except Exception:
            pass
    
    # Fallback: deterministic heuristic classification
    text_lower = text.lower()
    
    # Check for critical indicators
    if re.search(r"@channel|urgent|asap|critical|emergency", text_lower):
        return TriageLevel.CRITICAL
    
    # Check for high-priority indicators (mentions of specific users or teams)
    if re.search(r"@\w+|mentions?|alert|important", text_lower):
        return TriageLevel.HIGH
    
    # Use channel priority as fallback
    if channel_priority in ["critical", "high"]:
        return channel_priority
    
    return TriageLevel.LOW


def _classify_node(state: TriageState) -> TriageState:
    """Classify text into triage level."""
    triage_level = _classify_with_fallback(state["raw_text"], state["channel_priority"])
    return {
        **state,
        "triage_level": triage_level,
    }


def _summarize_node(state: TriageState) -> TriageState:
    """Generate 1-2 sentence summary."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    
    if api_key:
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=api_key)
            response = client.messages.create(
                model="gpt-4o-mini",
                max_tokens=128,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Summarize this message in 1-2 sentences:

{state['raw_text']}"""
                    }
                ]
            )
            summary = response.choices[0].message.content.strip()
            return {
                **state,
                "summary": summary,
            }
        except Exception:
            pass
    
    # Fallback: use first sentence or truncate
    text = state["raw_text"].strip()
    sentences = re.split(r"[.!?]+", text)
    summary = sentences[0].strip() if sentences[0].strip() else text[:100]
    if len(summary) > 150:
        summary = summary[:147] + "..."
    
    return {
        **state,
        "summary": summary,
    }


def _hash_embed_node(state: TriageState) -> TriageState:
    """Generate md5-based embedding hash for pgvector integration."""
    embedding_hash = hashlib.md5(state["raw_text"].encode("utf-8")).hexdigest()
    return {
        **state,
        "embedding_hash": embedding_hash,
    }


def _build_triage_graph() -> StateGraph:
    """Build the LangGraph StateGraph for triage pipeline."""
    graph = StateGraph(TriageState)
    
    # Add nodes
    graph.add_node("classify", _classify_node)
    graph.add_node("summarize", _summarize_node)
    graph.add_node("hash_embed", _hash_embed_node)
    
    # Add edges
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "summarize")
    graph.add_edge("summarize", "hash_embed")
    graph.add_edge("hash_embed", END)
    
    return graph.compile()


# Global compiled graph
_TRIAGE_GRAPH = _build_triage_graph()


async def run_triage(text: str, channel_priority: str = "low") -> dict[str, Any]:
    """
    Run the triage pipeline on input text.
    
    Args:
        text: Raw text to triage
        channel_priority: Channel-derived priority hint (default: "low")
        
    Returns:
        Dictionary with keys: raw_text, channel_priority, triage_level, summary, embedding_hash
        
    Example:
        >>> result = await run_triage("@channel urgent issue", "high")
        >>> result["triage_level"]
        'critical'
    """
    initial_state: TriageState = {
        "raw_text": text,
        "channel_priority": channel_priority,
        "triage_level": TriageLevel.LOW,
        "summary": "",
        "embedding_hash": "",
    }
    
    # Run graph synchronously (LangGraph invoke is sync)
    final_state = _TRIAGE_GRAPH.invoke(initial_state)
    
    return dict(final_state)
