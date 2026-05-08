# This example shows the pattern. Install maelstrom-gate for the full implementation.
#
# Filter OpenAI function-calling tools before sending to chat completions.
# The model never sees suppressed tools -- it cannot request what it cannot see.

from gatekeeper import Gate, Tool

# --- Your tool definitions (map from OpenAI function schema) ---

OPENAI_TOOLS = [
    {"type": "function", "function": {"name": "get_weather",    "description": "Get weather",    "parameters": {}}},
    {"type": "function", "function": {"name": "send_alert",     "description": "Send alert",     "parameters": {}}},
    {"type": "function", "function": {"name": "restart_server", "description": "Restart server", "parameters": {}}},
]

# Map each OpenAI tool to an execution class
TOOL_CLASSES = {
    "get_weather":    "read_only",
    "send_alert":     "external_action",
    "restart_server": "high_impact",
}

# --- Gate setup ---

gate = Gate()
for oai_tool in OPENAI_TOOLS:
    name = oai_tool["function"]["name"]
    gate.add_tool(Tool(name, execution_class=TOOL_CLASSES[name]))

# --- Before calling the OpenAI API, filter tools ---

def get_filtered_tools(mode: float) -> list[dict]:
    """Return only the OpenAI tool dicts that survive the gate."""
    result = gate.filter(mode=mode)
    visible = set(result.visible_names)
    return [t for t in OPENAI_TOOLS if t["function"]["name"] in visible]

# Usage: calm -- all three tools sent to the model
print(f"calm:   {[t['function']['name'] for t in get_filtered_tools(0.1)]}")

# Usage: crisis -- only get_weather survives
print(f"crisis: {[t['function']['name'] for t in get_filtered_tools(0.8)]}")

# Then pass the filtered list to openai.chat.completions.create(tools=...)
