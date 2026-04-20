# maelstrom-gate

Runtime governance for AI tool access. Filter which tools your agent can see based on a threat signal.

## The Problem

Your AI agent has access to every tool at all times. During an incident, it can still deploy to production, send emails to customers, and delete database records. Telling the model "don't do dangerous things" is a guardrail. Removing the tool from its manifest is a gate.

## The Solution

```python
from maelstrom_gate import Gate, Tool

gate = Gate()
gate.add_tools([
    Tool("read_file", execution_class="read_only"),
    Tool("deploy",    execution_class="high_impact"),
])

gate.filter(mode=0.1).visible_names  # ['deploy', 'read_file']  -- calm
gate.filter(mode=0.5).visible_names  # ['read_file']            -- elevated
gate.filter(mode=0.8).visible_names  # ['read_file']            -- crisis
```

The model cannot request a tool it cannot see.

## How It Works

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

The mode value comes from you. It could be a manual slider, an automated risk score, an incident management system, or a full governance pipeline. The gate does not compute threat -- it enforces the consequences.

## Execution Classes

Every tool gets one execution class. The class determines when the tool disappears.

| Class             | Suppressed When | Use For                        |
|-------------------|-----------------|--------------------------------|
| `read_only`       | Never           | File reads, API GETs, queries  |
| `advisory`        | Never           | Analysis, summaries, scoring   |
| `external_action` | mode > 0.65     | Emails, webhooks, Slack posts  |
| `state_mutation`  | mode > 0.65     | DB writes, file writes, config |
| `high_impact`     | mode > 0.35     | Deploys, deletions, migrations |

Unrecognized classes are treated as `high_impact`.

## Install

```bash
pip install maelstrom-gate
```

Python 3.10+. Zero dependencies.

## Quick Start

```python
from maelstrom_gate import Gate, Tool

# Define your tools
gate = Gate()
gate.add_tools([
    Tool("read_file",  execution_class="read_only",       description="Read a file"),
    Tool("analyze",    execution_class="advisory",         description="Analyze data"),
    Tool("send_email", execution_class="external_action",  description="Send an email"),
    Tool("write_db",   execution_class="state_mutation",    description="Write to database"),
    Tool("deploy",     execution_class="high_impact",       description="Deploy to production"),
])

# Filter at current threat level
result = gate.filter(mode=0.5)

# Feed visible tools to your LLM
print(result.visible_names)     # ['analyze', 'read_file', 'send_email', 'write_db']
print(result.suppressed_names)  # ['deploy']
print(result.mode_zone)         # 'elevated'

# Export as a tool catalog for the system prompt
catalog = result.to_catalog()
```

## Framework Examples

Working examples for common agent frameworks:

- [`examples/basic_usage.py`](examples/basic_usage.py) -- standalone gate usage
- [`examples/openai_functions.py`](examples/openai_functions.py) -- filter OpenAI function-calling tools
- [`examples/langchain_tools.py`](examples/langchain_tools.py) -- wrap LangChain tools with gate filtering
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) -- per-request tool filtering via middleware

## Authorization Envelopes

Signed permission sets that constrain tool execution. The envelope travels with the tool call and tells the executor what it is allowed to do.

```python
from maelstrom_gate import build_envelope, verify_envelope, Tool

tool = Tool("read_file", execution_class="read_only")
envelope = build_envelope(tool, mode=0.5, context_id="session_1", signing_key="your-key")

envelope.budget_seconds   # 15  (reduced under elevated mode)
envelope.execution_mode   # "cautious"
envelope.max_tool_calls   # 10

verify_envelope(envelope, "your-key")   # True
verify_envelope(envelope, "wrong-key")  # False
```

Envelope parameters tighten automatically as mode increases. See [SPEC.md](SPEC.md) Section 8 for the full adjustment table.

## Ingress Validation

Validate tool requests from the model before execution. Never trust the model's tool choice -- verify it against the gate.

```python
from maelstrom_gate import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## Custom Thresholds

Override default suppression thresholds per execution class:

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## The Spec

[SPEC.md](SPEC.md) defines the Maelstrom Gate standard in language-agnostic terms. It covers execution classes, suppression rules, thresholds, envelope schemas, and ingress validation. You can implement it in any language without reading the Python.

[ARCHITECTURE.md](ARCHITECTURE.md) documents the 18-package product suite, the canonical envelope serialization rules, and the bugs we caught while making Python and Go agree on byte-identical signatures. Read it before writing a new implementation.

## JSON Schemas

Formal JSON Schema definitions for interoperability:

- [`schema/tool.schema.json`](schema/tool.schema.json) -- tool manifest
- [`schema/envelope.schema.json`](schema/envelope.schema.json) -- authorization envelope
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) -- filter result

## Implementations

`maelstrom-gate` is the Python reference implementation. The spec is language-agnostic and other implementations exist:

| Implementation | Language | Repo | Status |
|----------------|----------|------|--------|
| `maelstrom-gate` | Python 3.10+ | this repo | **reference** |
| `gate-server-go` | Go 1.22+ | `adam-scott-thomas/gate-server-go` | conformant — passes cross-language vectors; Python-built envelopes verify in Go |

Cross-language conformance is enforced via shared test vectors (`gate-test/vectors/envelope_signing.json`). Any new implementation is compliant iff it passes those vectors and can verify an envelope built by this reference. See [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations).

## The Suite

`maelstrom-gate` is one package in an 18-package product suite:

```
Layer 0 — Spec                maelstrom-gate, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

Each layer imports only from the layer(s) below it. Every package (except the stdlib-only variants gate-dash, gatectl) lives as a sibling repo under `adam-scott-thomas/gate-*`. See [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite).

## From Maelstrom

Extracted from [Maelstrom](https://github.com/adam-scott-thomas/maelstrom), a deterministic cognitive architecture for governed AI autonomy. Maelstrom computes the mode signal through a 22-node pipeline with crisis classification, regret analysis, and personality calibration. The gate is the enforcement layer -- it works standalone or as part of the full runtime.

## License

Apache 2.0 — see [LICENSE](LICENSE).
