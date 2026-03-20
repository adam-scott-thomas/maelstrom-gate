# maelstrom-gate

Runtime governance gate for AI tool access. Dynamically filter which tools an LLM can see and use based on a threat/mode signal.

The LLM doesn't refuse. The tool disappears before the LLM can think about it.

## Install

```bash
pip install maelstrom-gate
```

## Quick Start

```python
from maelstrom_gate import Gate, Tool

gate = Gate()
gate.add_tools([
    Tool("read_file", execution_class="read_only", description="Read a file"),
    Tool("send_email", execution_class="external_action", description="Send email"),
    Tool("deploy", execution_class="high_impact", description="Deploy to production"),
])

# Calm — all tools visible
result = gate.filter(mode=0.1)
print(result.visible_names)   # ['deploy', 'read_file', 'send_email']

# Elevated — high_impact suppressed
result = gate.filter(mode=0.5)
print(result.visible_names)   # ['read_file', 'send_email']
print(result.suppressed_names)  # ['deploy']

# Crisis — only safe tools remain
result = gate.filter(mode=0.8)
print(result.visible_names)   # ['read_file']
print(result.suppressed_names)  # ['deploy', 'send_email']
```

## Execution Classes

| Class | Suppressed Above | Examples |
|-------|-----------------|----------|
| `read_only` | Never | File reads, API GETs |
| `advisory` | Never | Analysis, summaries |
| `external_action` | 0.65 | Emails, webhooks |
| `state_mutation` | 0.65 | File writes, DB updates |
| `high_impact` | 0.35 | Deployments, deletions |

## Custom Thresholds

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploy earlier
```

## Authorization Envelopes

Signed permission sets that tell the executor exactly what it's allowed to do:

```python
from maelstrom_gate import build_envelope, verify_envelope

tool = Tool("read_file", execution_class="read_only")
envelope = build_envelope(tool, mode=0.5, context_id="session_1", signing_key="your-key")

print(envelope.budget_seconds)   # 15 (halved under elevated mode)
print(envelope.execution_mode)   # "cautious"

assert verify_envelope(envelope, "your-key")
```

## Ingress Validation

Validate tool requests from the LLM — never trust the model:

```python
from maelstrom_gate import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
print(result.accepted)  # False
print(result.reason)    # "execution_class_suppressed"
```

## Catalog Export

Generate a tool catalog for your LLM prompt:

```python
result = gate.filter(mode=0.5)
catalog = result.to_catalog()
# Feed this to your LLM system prompt — suppressed tools are absent.
```

## How It Works

```
Your signals → mode value → Gate.filter() → filtered tool list → LLM prompt
                                          → suppressed tools (logged, not shown)
```

The mode value comes from you. It could be a manual slider, an automated risk assessment, or a governance pipeline.

## Zero Dependencies

Python 3.10+. Standard library only. Works with any agent framework.

## From the Maelstrom Project

Extracted from [Maelstrom](https://github.com/adam-scott-thomas/maelstrom) — a governed autonomy runtime. The gate filters tools; Maelstrom computes the mode value through a 22-node deterministic pipeline with crisis classification, regret analysis, and personality calibration.

## License

MIT
