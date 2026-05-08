# This example shows the pattern. Install maelstrom-gate for the full implementation.
#
# Wrap LangChain tools with gate filtering. The agent only receives tools
# that survive the current mode level.

from gatekeeper import Gate, Tool

# --- Simulate LangChain tool objects ---
# In real code these would be @tool-decorated functions or BaseTool subclasses.

class FakeLangChainTool:
    """Stands in for a LangChain BaseTool."""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    def run(self, *args, **kwargs):
        return f"{self.name} executed"

search_tool  = FakeLangChainTool("search_web",     "Search the web")
email_tool   = FakeLangChainTool("send_email",      "Send an email")
delete_tool  = FakeLangChainTool("delete_records",   "Delete database records")

LANGCHAIN_TOOLS = [search_tool, email_tool, delete_tool]

# --- Map LangChain tools to gate tools ---

TOOL_CLASSES = {
    "search_web":     "read_only",
    "send_email":     "external_action",
    "delete_records": "high_impact",
}

gate = Gate()
for lc_tool in LANGCHAIN_TOOLS:
    gate.add_tool(Tool(lc_tool.name, execution_class=TOOL_CLASSES[lc_tool.name]))

# --- Filter before passing to the agent ---

def get_allowed_tools(mode: float) -> list:
    """Return LangChain tool objects that survive the gate."""
    result = gate.filter(mode=mode)
    visible = set(result.visible_names)
    return [t for t in LANGCHAIN_TOOLS if t.name in visible]

# Calm -- all tools
print(f"calm:   {[t.name for t in get_allowed_tools(0.1)]}")

# Elevated -- delete_records suppressed
print(f"elevated: {[t.name for t in get_allowed_tools(0.5)]}")

# Crisis -- only search_web
print(f"crisis: {[t.name for t in get_allowed_tools(0.8)]}")

# Pass get_allowed_tools(mode) to AgentExecutor(tools=...) or create_tool_calling_agent(tools=...)
