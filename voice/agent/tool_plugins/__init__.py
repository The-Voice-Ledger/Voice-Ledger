"""
Agent Tool Plugin System

Each module in this package defines tool handlers for a specific domain.
Handlers are registered with the ToolRegistry via register_tools(registry).

To add a new tool domain:
1. Create voice/agent/tool_plugins/your_domain.py
2. Define handler functions with signature:
   def handle_your_tool(db: Session, args: dict, user_id: int, user_did: str) -> tuple[str, dict]
3. Implement register_tools(registry) that calls registry.register(name, handler)
4. Import and call register_tools from register_all_plugins() below

The GPT-4o function schemas live in voice/agent/tools.py — not touched here.
"""


def register_all_plugins(registry) -> None:
    """
    Register all domain tool plugins with the registry.

    Called from ToolRegistry._register_defaults() as the single entry point
    for all tool handler registration.

    Existing handlers in ToolRegistry are NOT moved here yet — this is the
    extensibility layer for new community-contributed tools.  Migrating
    existing handlers is a follow-up task.
    """
    # Future domain modules plug in here, e.g.:
    # from voice.agent.tool_plugins.supply_chain import register_tools
    # register_tools(registry)
    pass
