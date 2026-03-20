# Maelstrom Gate Specification v0.1.0

A runtime governance standard for AI tool access. Implementations dynamically
filter which tools an AI agent can see and invoke based on an operational
mode signal.

## 1. Concepts

**Mode signal**: A scalar in [0.0, 1.0]. 0.0 is calm. 1.0 is maximum threat.

**Execution class**: A classification on each tool describing side-effect
severity. The gate uses execution class plus mode to decide visibility.

**Suppression**: A suppressed tool is removed from the agent's tool manifest
before it reaches the language model. The model cannot request what it cannot see.

## 2. Execution Classes

Every tool MUST be assigned exactly one execution class.

| Class             | Description                                      |
|-------------------|--------------------------------------------------|
| `read_only`       | No side effects. Reads data, fetches resources.  |
| `advisory`        | Produces analysis or recommendations. No action. |
| `external_action` | Communicates with external systems. Sends data.  |
| `state_mutation`  | Writes, updates, or deletes internal state.      |
| `high_impact`     | Irreversible or high-consequence operations.     |

A tool with an unrecognized execution class MUST be treated as `high_impact`.

## 3. Suppression Rule

A tool is suppressed when `mode > threshold` for its execution class.

If a class has no threshold (null), the tool is never suppressed.

```
FUNCTION is_suppressed(execution_class, mode, thresholds):
    threshold = thresholds[execution_class]
    IF threshold IS NULL:
        RETURN false
    RETURN mode > threshold
```

## 4. Default Thresholds

| Execution Class   | Threshold | Suppressed When        |
|--------------------|-----------|------------------------|
| `read_only`        | null      | Never                  |
| `advisory`         | null      | Never                  |
| `external_action`  | 0.65      | mode > 0.65            |
| `state_mutation`   | 0.65      | mode > 0.65            |
| `high_impact`      | 0.35      | mode > 0.35            |

Implementations MAY allow per-instance threshold overrides.

## 5. Mode Zones

The mode signal maps to three named zones:

| Zone       | Range            | Interpretation             |
|------------|------------------|----------------------------|
| `normal`   | mode <= 0.35     | All tools available.       |
| `elevated` | 0.35 < mode <= 0.65 | High-impact suppressed. |
| `crisis`   | mode > 0.65      | Only safe tools remain.    |

Zone boundaries are derived from the default thresholds. The zone name is
advisory metadata; suppression is always computed per-tool from thresholds.

## 6. Tool Manifest Schema

Each tool is described by a manifest object:

```json
{ "name": "deploy", "execution_class": "high_impact",
  "description": "Deploy to production", "inputs": {"version": "string"} }
```

- `name` (string, required): Unique tool identifier.
- `execution_class` (string, required): One of the five execution classes.
- `description` (string, optional): Human-readable description.
- `inputs` (object, optional): Map of parameter names to type descriptions.

See `schema/tool.schema.json` for the formal JSON Schema.

## 7. Filter Result

The output of a filter operation contains: `visible` (tool array), `suppressed`
(tool array), `mode` (float), `mode_zone` (string), and `thresholds` (object).

See `schema/filter-result.schema.json` for the formal JSON Schema.

## 8. Authorization Envelope

An authorization envelope is a signed, frozen permission set that accompanies
a tool invocation. It constrains the executor.

```json
{
  "envelope_id":     "env_session1_a1b2c3d4",
  "context_id":      "session1",
  "tool_name":       "read_file",
  "allowed_tools":   ["read_file"],
  "max_tool_calls":  20,
  "max_retries":     1,
  "budget_seconds":  30,
  "execution_mode":  "standard",
  "dry_run":         false,
  "branching":       "auto",
  "human_approved":  false,
  "signature":       "<HMAC-SHA256 hex digest>"
}
```

### Envelope Fields

| Field            | Type       | Description                                  |
|------------------|------------|----------------------------------------------|
| `envelope_id`    | string     | Unique identifier for this envelope.         |
| `context_id`     | string     | Session or context scope.                    |
| `tool_name`      | string     | Primary tool this envelope authorizes.       |
| `allowed_tools`  | string[]   | All tools permitted under this envelope.     |
| `max_tool_calls` | integer    | Maximum invocations allowed.                 |
| `max_retries`    | integer    | Maximum retry attempts per call.             |
| `budget_seconds` | integer    | Time budget for execution.                   |
| `execution_mode` | string     | One of: `standard`, `cautious`, `minimal`.   |
| `dry_run`        | boolean    | If true, execute without side effects.       |
| `branching`      | string     | `auto` or `deny`. Controls sub-task spawning.|
| `human_approved` | boolean    | Whether a human explicitly approved this.    |
| `signature`      | string     | HMAC-SHA256 signature over canonical fields. |

### Envelope Crisis Adjustments

Envelope parameters are adjusted based on the current mode zone:

| Parameter        | normal       | elevated     | crisis       |
|------------------|--------------|--------------|--------------|
| `max_tool_calls` | 20           | 10           | 5            |
| `budget_seconds` | 30           | 15           | 7            |
| `execution_mode` | `standard`   | `cautious`   | `minimal`    |
| `branching`      | per-class    | `deny`       | `deny`       |

In `normal` zone, `branching` is `auto` for `read_only` and `advisory`
tools, and `deny` for all others.

### Signature Computation

1. Construct a JSON object with fields: `envelope_id`, `context_id`,
   `tool_name`, `allowed_tools`, `max_tool_calls`, `budget_seconds`,
   `execution_mode`, `branching`, `human_approved`.
2. Serialize to canonical JSON (sorted keys, no whitespace, no NaN/Infinity).
3. Compute SHA-256 of the canonical JSON string (UTF-8 encoded).
4. Compute HMAC-SHA256 of the hash using the signing key.
5. The signature is the hex-encoded HMAC digest.

See `schema/envelope.schema.json` for the formal JSON Schema.

## 9. Ingress Validation

Before executing a tool request from the language model, validate:

1. **Registration check**: The requested tool name MUST exist in the gate's
   tool registry. Reject with `tool_not_found` if absent.
2. **Suppression check**: The requested tool MUST NOT be suppressed at the
   current mode. Reject with `execution_class_suppressed` if suppressed.

A conforming implementation MUST reject requests that fail either check
before any tool execution occurs.

## 10. Conformance

A conforming implementation MUST:

- Support all five execution classes.
- Apply the suppression rule as defined in Section 3.
- Use the default thresholds from Section 4 unless overridden.
- Clamp mode values to [0.0, 1.0].
- Treat unrecognized execution classes as `high_impact`.
- Perform ingress validation per Section 9 when validating proposals.

A conforming implementation MAY:

- Allow custom thresholds per execution class.
- Extend the tool manifest with additional fields.
- Omit authorization envelopes if not needed.
- Add additional ingress validation rules beyond the two required checks.
