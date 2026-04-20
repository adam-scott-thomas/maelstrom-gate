# This example shows the pattern. Install maelstrom-gate for the full implementation.
#
# FastAPI middleware that filters tools per-request based on a threat header.
# The upstream system (your risk engine, manual toggle, etc.) sets the
# X-Threat-Level header. The middleware gates which tools the LLM can see.

from maelstrom_gate import Gate, Tool

# --- Simulated FastAPI types (replace with real imports) ---
# from fastapi import FastAPI, Request, Response
# from starlette.middleware.base import BaseHTTPMiddleware

# --- Gate setup (shared across requests) ---

gate = Gate()
gate.add_tools([
    Tool("query_db",    execution_class="read_only",       description="Query database"),
    Tool("send_slack",  execution_class="external_action",  description="Send Slack message"),
    Tool("run_migration", execution_class="high_impact",    description="Run DB migration"),
])

# --- Middleware pattern ---

def gate_middleware(request_headers: dict, handler):
    """
    Extract threat level from request headers, filter tools, and inject
    the filtered catalog into the request state.

    In real FastAPI:
        class GateMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request: Request, call_next):
                mode = float(request.headers.get("X-Threat-Level", "0.0"))
                result = gate.filter(mode=mode)
                request.state.tools = result.to_catalog()
                request.state.gate_result = result
                return await call_next(request)
    """
    mode = float(request_headers.get("X-Threat-Level", "0.0"))
    result = gate.filter(mode=mode)

    # Inject into request state -- your endpoint reads from here
    state = {
        "tools": result.to_catalog(),
        "mode_zone": result.mode_zone,
        "suppressed": result.suppressed_names,
    }
    return handler(state)

# --- Demo ---

def handle_request(state):
    tools = [t["name"] for t in state["tools"]]
    print(f"  zone={state['mode_zone']}  tools={tools}  suppressed={state['suppressed']}")

print("Request with no threat:")
gate_middleware({"X-Threat-Level": "0.0"}, handle_request)

print("Request during incident:")
gate_middleware({"X-Threat-Level": "0.8"}, handle_request)
