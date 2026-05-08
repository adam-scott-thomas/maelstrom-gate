# Gatekeeper — Architecture

> This document describes the full Gatekeeper product suite: what it is,
> how the 18 packages fit together, and the canonical rules implementations
> must obey to remain interoperable.
>
> Reference implementation: `gate-keeper` (Python).
> Alternate implementation: `gate-server-go` (Go).

---

## 1. What Gatekeeper is

Gatekeeper is a **runtime governance standard for AI tool access**.

Instead of telling a language model *"please don't do dangerous things"* (a
guardrail the model can ignore), Gate **removes the tool from its manifest**
before the prompt ever reaches the model. The model cannot request a tool it
cannot see.

```
  AGENT PROMPT                       LLM
  ┌──────────────┐   filter(mode)   ┌───────────┐
  │  user input  │ ───────────────▶ │           │
  │  tool list   │                  │  MODEL    │
  └──────┬───────┘                  │           │
         │                          └───────────┘
         ▼
  ┌──────────────┐        ╔════ mode=0.1 calm ═════╗
  │     GATE     │  ────▶ ║  read · write · deploy  ║
  │              │        ╚═════════════════════════╝
  │  mode signal │        ╔════ mode=0.5 elevated ══╗
  │  + threshold │  ────▶ ║  read · write           ║
  │              │        ╚═════════════════════════╝
  │   tool list  │        ╔════ mode=0.9 crisis ════╗
  └──────────────┘  ────▶ ║  read                   ║
                          ╚═════════════════════════╝
```

A scalar **mode signal** in `[0.0, 1.0]` rises with operational threat. Each
tool is tagged with an **execution class** describing side-effect severity.
When mode exceeds the threshold for a class, every tool in that class is
suppressed from the manifest.

- `read_only`       — never suppressed
- `advisory`        — never suppressed
- `external_action` — suppressed above `T_UP = 0.65`
- `state_mutation`  — suppressed above `T_UP = 0.65`
- `high_impact`     — suppressed above `T_DOWN = 0.35`

Mode maps to three named zones: `normal` (≤ 0.35), `elevated` (≤ 0.65),
`crisis` (> 0.65).

---

## 2. The 18-package suite

Gatekeeper is not a single library. It's a standards-style product suite
with clean separation between the **spec**, the **implementations**, and
everything else that consumes or operates on them.

```
                    ┌────────────────────────────────────────────────┐
                    │            LAYER 0 — SPECIFICATION             │
                    │                                                │
                    │   gate-keeper   (Python reference impl +    │
                    │                     SPEC.md + JSON schemas)    │
                    │   gate-server-go   (Go reimplementation)       │
                    │                                                │
                    └────────────┬────────────┬──────────────────────┘
                                 │            │
     ┌───────────────────────────┼────────────┼─────────────────────────┐
     │                           │            │                         │
     ▼                           ▼            ▼                         ▼
┌───────────┐             ┌────────────┐ ┌──────────────┐        ┌────────────┐
│  LAYER 1  │             │  LAYER 2   │ │   LAYER 3    │        │  LAYER 4   │
│           │             │            │ │              │        │            │
│  gate-sdk │             │ gate-policy│ │ gate-guard   │        │ gate-server│
│  gate-cli │             │ gate-schema│ │ gate-webhook │        │ gate-      │
│           │             │            │ │ gate-        │        │ dashboard  │
│           │             │            │ │ compliance   │        │ gate-dash  │
│           │             │            │ │ gate-metrics │        │ gatectl    │
└─────┬─────┘             └────────────┘ └──────────────┘        └────────────┘
      │
      ▼
┌───────────────────────────────────┐
│         LAYER 5 — AGENTS          │
│                                   │
│  gate-agent  (SDK-based)          │
│  gate-pilot  (minimal demo)       │
│  gate-examples                    │
└───────────────────────────────────┘
                    │
                    ▼
         ┌────────────────────┐
         │  LAYER 6 — QA      │
         │                    │
         │  gate-test         │
         │  gate-bench        │
         └────────────────────┘

OUTLIER (different product, shares "gate" prefix only):
  ghostgate  — circuit breaker between autonomous bot and on-chain wallet
```

### Package roles

| Layer | Package | Role | Lang | LOC |
|-------|---------|------|------|-----|
| 0 | `gate-keeper` | Core spec + Python reference impl | Python | 1,639 |
| 0 | `gate-server-go` | Go reimplementation (polyglot) | Go | 1,366 |
| 1 | `gate-sdk` | Framework adapters (OpenAI, Anthropic, webhook) | Python | 1,936 |
| 1 | `gate-cli` | Operator's CLI (click-based) | Python | 1,741 |
| 2 | `gate-policy` | Declarative policy engine (YAML rules) | Python | 1,969 |
| 2 | `gate-schema` | JSON Schema validation for artifacts | Python | 603 |
| 3 | `gate-guard` | Runtime enforcement (blocks unauthorized execution) | Python | 533 |
| 3 | `gate-webhook` | Event broadcasting | Python | 1,245 |
| 3 | `gate-compliance` | Audit trail + evidence reports (largest) | Python | 3,669 |
| 3 | `gate-metrics` | Prometheus metrics | Python | 598 |
| 4 | `gate-server` | FastAPI HTTP server | Python | 1,312 |
| 4 | `gate-dashboard` | FastAPI + Jinja2 web UI | Python | 604 |
| 4 | `gate-dash` | Stdlib-only HTTP proxy dashboard | Python | 551 |
| 4 | `gatectl` | Stdlib-only interactive CLI (REPL) | Python | 892 |
| 5 | `gate-agent` | SDK-based autonomous agent (dogfood) | Python | 1,143 |
| 5 | `gate-pilot` | Minimal governance-loop demo | Python | 676 |
| 5 | `gate-examples` | Integration examples | Python | 435 |
| 6 | `gate-test` | Cross-language conformance suite | Python | 889 |
| 6 | `gate-bench` | Performance benchmarks | Python | 366 |

**Total: ~22,500 LOC across 18 packages.**

---

## 3. Canonical envelope serialization

An `AuthorizationEnvelope` is a signed, frozen permission set tied to a specific
tool invocation. Two implementations must produce byte-identical canonical JSON
and signatures for the same inputs. The rules below are non-negotiable.

### 3.1 Fields (SPEC.md §8)

| Field            | Type   | JSON example |
|------------------|--------|--------------|
| `envelope_id`    | string | `"env_ctx-1_aaaaaaaa"` |
| `context_id`     | string | `"ctx-1"` |
| `tool_name`      | string | `"deploy"` |
| `allowed_tools`  | `[]string` | `["deploy"]` |
| `max_tool_calls` | int | `20` |
| `max_retries`    | int | `1` |
| `budget_seconds` | int | `30` |
| `execution_mode` | string | `"standard"` |
| `dry_run`        | bool | `false` |
| `branching`      | string | `"deny"` |
| `human_approved` | bool | `false` |
| `created_at`     | **int64 (microseconds)** | `1713568999000000` |
| `signature`      | string (hex HMAC-SHA256) | `"b4a29e…"` |

### 3.2 Signed payload

The signature covers a subset of the envelope — **NOT** `max_retries`, `dry_run`,
or `signature` itself. The exact payload is:

```
envelope_id, context_id, tool_name, allowed_tools,
max_tool_calls, budget_seconds, execution_mode,
branching, human_approved, created_at
```

### 3.3 Algorithm

```
1. Build a map with exactly the fields listed in 3.2.
2. Emit canonical JSON:
     - keys sorted alphabetically
     - no whitespace between tokens
     - UTF-8 encoding
3. sha256 → raw 32-byte digest (NOT hex-encoded)
4. HMAC-SHA256(signing_key, raw_digest_bytes) → sig_bytes
5. hex-encode sig_bytes → signature string
```

**Python**:
```python
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
digest    = hashlib.sha256(canonical.encode()).digest()       # raw 32 bytes, NOT hexdigest
sig       = hmac.new(key.encode(), digest, hashlib.sha256).hexdigest()
```

**Go**:
```go
canonical, _ := json.Marshal(payload)       // map[string]any sorts keys alphabetically
digest       := sha256.Sum256(canonical)     // raw 32 bytes
mac          := hmac.New(sha256.New, []byte(key))
mac.Write(digest[:])
sig          := hex.EncodeToString(mac.Sum(nil))
```

### 3.4 Why these choices specifically

Every rule above was chosen to be reproducible across languages. We learned the
hard way by actually running both implementations against shared vectors.

---

## 4. Bugs caught during polyglot verification

Two real bugs only surfaced when the Go test ran against the same vectors the
Python test was already passing. Both are documented so future implementations
(Rust, TypeScript, etc.) don't re-introduce them.

### Bug 1 — `mode_status` vs `mode_zone` (pre-polyglot)

**Symptom:** `Gate().filter()` in Python emitted a dict with key `mode_status`;
`SPEC.md` §7 and `schema/filter-result.schema.json` required `mode_zone`. An
example file (`examples/fastapi_middleware.py`) already contained a manual hack
(`"mode_zone": result.mode_status`) — evidence the author noticed but didn't fix.

**Impact:** the reference implementation did not conform to its own
authoritative schema. Any schema validation of real core output failed on a
missing required field.

**Fix:** rename `ToolFilter.mode_status` → `ToolFilter.mode_zone` throughout the
reference implementation and all 17 dependent packages (93 call sites across
41 files).

### Bug 2 — Python HMAC'd the hex digest, Go HMAC'd the raw bytes

**Symptom:** Python's `verify_envelope` computed:
```python
hmac.new(key.encode(), _canonical_hash(data).encode(), sha256).hexdigest()
# where _canonical_hash returned a HEX STRING (64 bytes when UTF-8 encoded)
```
Go's `sign` function computed:
```go
hash := sha256.Sum256(data)                  // 32 raw bytes
mac  := hmac.New(sha256.New, []byte(key))
mac.Write(hash[:])                           // HMAC of 32 raw bytes
```

**Impact:** identical data produced different HMAC outputs. Cross-language
verification was **structurally impossible**, regardless of anything else.

**Fix:** change Python `_canonical_hash` to return raw bytes (`.digest()` instead
of `.hexdigest()`). Now both languages HMAC the same 32 bytes.

### Bug 3 — Float `.0` divergence (caught by the Go test)

**Symptom:** with `created_at` typed as `float`, Python and Go disagreed on
trailing-zero serialization:

```
Python  json.dumps(1713568999.0)  →  "1713568999.0"
Go      json.Marshal(float64(1713568999.0))  →  "1713568999"
```

The first cross-language test run caught this immediately. Python's `json`
module preserves the `.0` to distinguish float from int; Go's `encoding/json`
elides it.

**Fix attempt 1 (failed):** switch `created_at` to `int64` nanoseconds.

### Bug 4 — int64 nanoseconds overflow float64 precision

**Symptom:** Unix nanoseconds have 19 digits. `float64` has ~15.95 decimal
digits of precision. When an envelope JSON round-tripped through a decoder that
uses `map[string]any` (Go's default when no struct is provided), `created_at`
was coerced to float64 and **lost precision**. Re-marshaling produced a
different canonical JSON. Signatures no longer matched.

**Fix (final):** use **int64 microseconds** (16 digits). Microseconds fit
safely within float64 precision (2⁵³ ≈ 9×10¹⁵ > 1.7×10¹⁵ current µs
timestamp). Still integer, so no trailing `.0` issue. Sub-second granularity
is more than enough for the 5-minute replay-prevention window the freshness
check cares about.

### Summary

```
┌──────────────────────────────────────────────────────────────────────┐
│  PROBLEM                    │  FIX                                   │
├──────────────────────────────────────────────────────────────────────┤
│  mode_status ≠ mode_zone    │  rename to mode_zone (spec wins)       │
│  Python hex vs Go raw HMAC  │  Python HMACs raw bytes (.digest())    │
│  float .0 divergence        │  switch to integer timestamps          │
│  int64 ns overflow float64  │  use int64 microseconds (16 digits)    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Cross-language verification path

Two mechanisms enforce cross-language conformance. Both must be green for any
new implementation to be considered compliant.

### 5.1 Vector conformance (static)

Both implementations load the same file — `gate-test/vectors/envelope_signing.json` —
and assert their canonical-JSON output and HMAC signature match the expected
values byte-for-byte.

```
  gate-test/vectors/envelope_signing.json
            │
            ├──▶ gate-test/gate_test/test_cross_language_envelope.py  (Python)
            │        pytest → PASS
            │
            └──▶ gate-server-go/internal/envelope/vectors_test.go     (Go)
                     go test → PASS
```

If either side drifts from the vectors, its CI fails.

### 5.2 Live interoperability (dynamic)

Static vectors only prove "both produce X for input Y." They don't prove one
implementation can verify the other's output in real time. Live interop is
demonstrated by having Python actually build an envelope and Go actually verify
its signature:

```
  ┌────────────────────┐                    ┌────────────────────┐
  │      PYTHON        │                    │         GO         │
  │  gate-keeper    │                    │  gate-server-go    │
  │                    │                    │                    │
  │  Tool("deploy",    │                    │                    │
  │   high_impact)     │                    │                    │
  │         │          │                    │                    │
  │         ▼          │                    │                    │
  │  build_envelope()  │                    │                    │
  │         │          │                    │                    │
  │         │   JSON   │                    │                    │
  │         └─────────────────────────────▶ │  envelope.Verify() │
  │                    │                    │         │          │
  │                    │                    │         ▼          │
  │                    │                    │       true         │
  └────────────────────┘                    └────────────────────┘
```

Observed with a real envelope:
```
python envelope id=env_live-test_16173637 created_at=1776664222613140
Go verification result: true
--- PASS: TestVerifyPythonBuiltEnvelope
```

---

## 6. Conformance requirements for new implementations

A new implementation (e.g. Rust, TypeScript, Java) is **spec-compliant** if and
only if **all** of the following hold:

1. Emits canonical JSON for the filter result with the five required keys
   (`visible`, `suppressed`, `mode`, `mode_zone`, `thresholds`) and no others
   that aren't defined in `schema/filter-result.schema.json`.

2. Implements the suppression rule from SPEC.md §3 exactly (`mode > threshold`
   for the tool's execution class; `null` threshold means never suppress).

3. Implements the `zone(mode)` function per SPEC.md §5 with the **strict
   inequalities and the specific boundary values** 0.35 and 0.65.

4. For envelope signing:
   - Serializes the payload in §3.2 above
   - Emits JSON per §3.3 steps 1-2
   - HMACs the **raw 32-byte digest** per §3.3 steps 3-4
   - Encodes `created_at` as **int64 microseconds**

5. Passes `gate-test/vectors/envelope_signing.json` with byte-identical
   canonical JSON and signatures.

6. Can verify an envelope built by `gate-keeper` (Python reference) and
   vice versa.

7. When outputs are shared as JSON over the wire, uses a **typed decoder**
   (not `map[string]any` / untyped dict) so int64 fields don't lose
   precision.

---

## 7. Stability & versioning

- **Specification version** is tracked in `SPEC.md`.
- **Reference implementation version** is in `gate-keeper/pyproject.toml`.
- Both are currently **0.1.0**. Spec changes require a minor version bump on
  both.
- Breaking changes to canonical serialization (payload field list, algorithm
  details) require a major version bump and an updated vectors file.

## 8. References

- `SPEC.md` — the authoritative specification
- `schema/filter-result.schema.json` — filter output schema
- `schema/envelope.schema.json` — envelope schema
- `schema/tool.schema.json` — tool declaration schema
- `audits/STRICT_VALIDATION_2026-04-20.md` — re-validation audit with live
  interop proof
- `audits/GATE_FAMILY_AUDIT_2026-04-19.md` — initial 20-directory audit
