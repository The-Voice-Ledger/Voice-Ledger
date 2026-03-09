"""
Voice Ledger AI Agent

Tool-calling agent that replaces the rigid NLU → switch/case pipeline.
Instead of classifying into 7 hardcoded intents, the agent reasons about
which tools to call and what arguments to pass - using OpenAI function-calling.

Architecture:
    Voice → STT → Agent(tools=[...]) → tool calls → results → response

Benefits over the old pipeline:
    - No brittle NLU system prompt with 7 intent definitions
    - Handles compound commands ("ship batch 001 AND record 50kg new batch")
    - Asks for missing info naturally (no hand-coded clarification questions)
    - New actions = new tool definitions (no rewriting NLU + handler + validation)
    - Multi-turn memory via conversation history (no separate state machine)
"""

from .executor import AgentExecutor, AgentResult
from .tools import SUPPLY_CHAIN_TOOLS
from .registry import ToolRegistry

__all__ = [
    "AgentExecutor",
    "AgentResult",
    "SUPPLY_CHAIN_TOOLS",
    "ToolRegistry",
]
