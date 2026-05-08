# This example shows the pattern. Install maelstrom-gate for the full implementation.
#
# Basic usage: register tools, filter by mode, inspect results.

from gatekeeper import Gate, Tool

# Register tools with execution classes
gate = Gate()
gate.add_tools([
    Tool("read_file",  execution_class="read_only",       description="Read a file"),
    Tool("analyze",    execution_class="advisory",         description="Analyze data"),
    Tool("send_email", execution_class="external_action",  description="Send an email"),
    Tool("write_db",   execution_class="state_mutation",    description="Write to database"),
    Tool("deploy",     execution_class="high_impact",       description="Deploy to production"),
])

# Normal operation (mode=0.1) -- all tools visible
result = gate.filter(mode=0.1)
print(f"[normal]   visible: {result.visible_names}")
# ['analyze', 'deploy', 'read_file', 'send_email', 'write_db']

# Elevated threat (mode=0.5) -- high_impact suppressed
result = gate.filter(mode=0.5)
print(f"[elevated] visible: {result.visible_names}")
print(f"           suppressed: {result.suppressed_names}")
# visible: ['analyze', 'read_file', 'send_email', 'write_db']
# suppressed: ['deploy']

# Crisis (mode=0.8) -- only read_only and advisory remain
result = gate.filter(mode=0.8)
print(f"[crisis]   visible: {result.visible_names}")
print(f"           suppressed: {result.suppressed_names}")
# visible: ['analyze', 'read_file']
# suppressed: ['deploy', 'send_email', 'write_db']

# Export the filtered catalog as dicts (feed to your LLM system prompt)
catalog = result.to_catalog()
print(f"\nCatalog for LLM: {catalog}")
