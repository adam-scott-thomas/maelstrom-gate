---
audit_date: 2026-04-19
auditor: claude-opus-4-7
audit_type: adversarial / strict architectural validation
scope: gate-* family (20 directories)
target_claim: "Single, spec-driven product ecosystem with layered architecture, shared vocabulary, and no duplication. All gate-* packages conform to a unified model."
verdict: PARTIAL
prior_audit: GATE_FAMILY_AUDIT_2026-04-19.md
method: direct source reading (no agent summaries trusted), quantitative greps, cross-file field-name analysis
---

# Strict Architectural Validation — gate-* Family

## Goal

Disprove the claim that this is a coherent, spec-driven system. Assume FALSE, try to break it.

## Step 1 — Inventory (verified by direct count)

| Package | Files | Lang | LOC | dep on core (pyproject) | imports core (py) | Role |
|---|---|---|---|---|---|---|
| maelstrom-gate | 17 | Python | 1608 | self | — | core spec + reference impl |
| gate-agent | 11 | Python | 1143 | YES | 4 | dogfood agent |
| gate-bench | 7 | Python | 366 | YES | 3 | perf benchmarks |
| gate-cli | 19 | Python | 1741 | YES | 2 | CLI |
| gate-compliance | 28 | Python | 3669 | YES | 8 | audit trail (largest) |
| gatectl | 6 | Python | 892 | **NO** | 0 | stdlib-only CLI variant |
| gate-dash | 6 | Python | 550 | **NO** | 0 | stdlib-only dashboard variant (HTTP proxy) |
| gate-dashboard | 9 | Python | 604 | YES | 1 | FastAPI+Jinja dashboard |
| gate-examples | 13 | Python | 435 | YES | 9 | integration examples |
| gate-guard | 7 | Python | 533 | YES | 5 | runtime enforcement |
| gate-metrics | 11 | Python | 598 | YES | 5 | Prometheus metrics |
| gate-pilot | 6 | Python | 682 | **NO** | 0 | stdlib-only agent variant |
| gate-policy | 19 | Python | 1969 | YES | 3 | policy engine |
| gate-schema | 7 | Python | 603 | **NO (undeclared)** | 3 | JSON schemas |
| gate-sdk | 26 | Python | 1936 | YES | 7 | developer SDK |
| gate-server | 15 | Python | 1312 | YES | 4 | FastAPI server |
| gate-server-go | 8 go + 2 py | Go | 1304 | — (standalone reimpl) | — | Go reimpl |
| gate-test | 13 | Python | 830 | YES | 13 | conformance suite |
| gate-webhook | 11 | Python | 1250 | **NO (undeclared)** | 1 | webhook events |
| ghostgate | 16 | Python | 1458 | **NO** | 0 | **outlier — crypto wallet product** |

## Step 2 — Vocabulary Consistency: **FAIL**

### Finding V-1 (CRITICAL): Field name drift — `mode_status` vs `mode_zone`

Both field names are used across the ecosystem for the **same concept** (the zone label).

| Name | Total usages | Packages using it |
|---|---|---|
| `mode_status` | 93 | 14 (including maelstrom-gate core: 10) |
| `mode_zone` | 196 | 12 (including maelstrom-gate core: 4) |

**The canonical package contradicts itself:**
- `maelstrom-gate/maelstrom_gate/core.py:79` — `ToolFilter.mode_status` (Python implementation)
- `maelstrom-gate/maelstrom_gate/core.py:204` — returns `mode_status=status`
- `maelstrom-gate/schema/filter-result.schema.json:7,29` — JSON schema REQUIRES `mode_zone`
- `maelstrom-gate/SPEC.md:89` — spec text says `mode_zone`
- `maelstrom-gate/examples/fastapi_middleware.py:44` — **manually hacks around the drift**: `"mode_zone": result.mode_status`

The **reference implementation violates its own SPEC.md and its own JSON schema**. If you run `Gate().filter(0.3)` and validate the resulting dict against `maelstrom-gate/schema/filter-result.schema.json`, it fails (missing required field `mode_zone`, extra field `mode_status`).

**The spec conformance suite `gate-test` is itself schizophrenic:**
- `gate-test/gate_test/spec_section7.py:43-47` asserts `result.mode_status` (Python impl convention)
- `gate-test/gate_test/spec_section7.py:4` comment says "mode_zone (string)"
- `gate-test/gate_test/ecosystem_integration.py:102` manually renames: `"mode_zone": result.mode_status`
- `gate-test/gate_test/ecosystem_integration.py:130+` uses `mode_zone=` kwarg

The conformance suite cannot definitively answer "does implementation X conform to SPEC.md" because the suite itself is ambiguous.

### Finding V-2 (HIGH): Zone computation reimplemented ≥4 times

`maelstrom-gate` does **not** export a `zone(mode)` / `ModeZone(mode)` helper in its public API:

```
grep maelstrom-gate/maelstrom_gate/__init__.py for zone|Zone  → no match
```

As a result, zone computation is duplicated in:
- `gate-pilot/gate_pilot/agent.py:92-97` — `_zone(mode)` function
- `gate-compliance/gate_compliance/store.py:103-106` — zone-from-mode method
- `gate-compliance/gate_compliance/schema_validator.py:109` — inline ternary
- `gate-dashboard/gate_dashboard/state.py:83-85` — hardcoded boundary strings
- `gate-server-go/internal/gate/gate.go:44-51` — `ModeZone(mode)` (Go exports this; Python doesn't)

Boundaries (0.35, 0.65) hardcoded in each. If the spec ever changes thresholds, Python core updates but these 4 packages silently drift.

## Step 3 — Spec Conformance: **FAIL**

- `SPEC.md` specifies `mode_zone` as the field name.
- `filter-result.schema.json` requires `mode_zone`.
- Python core emits `mode_status` instead.
- Schema validation of real Python core output against the authoritative schema → **fails on required-field check**.

This is not theoretical drift. It is a runtime contradiction baked into the canonical package.

## Step 4 — Dependency Graph

```
No circular deps detected.

maelstrom-gate (core)
  ← gate-agent, gate-bench, gate-cli, gate-compliance, gate-dashboard,
    gate-examples, gate-guard, gate-metrics, gate-policy, gate-sdk,
    gate-server, gate-test
  ← gate-schema      [UNDECLARED in pyproject; imports anyway]
  ← gate-webhook     [UNDECLARED in pyproject; imports anyway]

gate-sdk
  ← gate-agent

gate-policy
  ← gate-dashboard, gate-examples

gate-server
  ← gate-agent (optional)

standalone (no import of maelstrom-gate):
  gate-dash, gate-pilot, gatectl   [stdlib-only variants — but gate-pilot
                                    reimplements zone logic locally]
  gate-server-go                   [Go reimplementation]
  ghostgate                        [separate product — crypto domain]
```

**Layering is real**: core → domain (policy, schema, guard, compliance, metrics, webhook) → ops (server, cli, dashboard) → consumers (agent, examples, sdk) → QA (test, bench).

**No circular dependencies.** Layering holds.

**But two packages (gate-schema, gate-webhook) fail fresh-install** because they import maelstrom-gate without declaring the dependency in pyproject.toml.

## Step 5 — Duplication & Fragmentation

- Zone computation: duplicated (see V-2).
- `gate-dash` vs `gate-dashboard`: **not** duplicates — dash is a stdlib-only HTTP proxy to gate-server; dashboard is a FastAPI+Jinja2 app with state machine. Different products, same goal.
- `gatectl` vs `gate-cli`: **not** duplicates — gatectl is stdlib-only REPL; gate-cli is click-based full CLI.
- `gate-pilot` vs `gate-agent`: partial overlap. Pilot is stdlib-only demo (zero deps); agent is full SDK-based runtime. Both implement "agent that talks to gate-server." Justifiable separation.

**No wholesale duplication.** Real fragmentation is concentrated on (a) field name and (b) zone helper.

## Step 6 — Polyglot Validation: **FAIL**

### Finding P-1 (CRITICAL): Envelope structure mismatch

`AuthorizationEnvelope` fields differ between Python and Go:

| Field | Python | Go |
|---|---|---|
| envelope_id | ✓ | ✓ |
| context_id | ✓ | ✓ |
| tool_name | ✓ | ✓ |
| allowed_tools | ✓ | ✓ |
| max_tool_calls | ✓ | ✓ |
| max_retries | ✓ | ✓ |
| budget_seconds | ✓ | ✓ |
| execution_mode | ✓ | ✓ |
| dry_run | ✓ | ✓ |
| branching | ✓ | ✓ |
| human_approved | ✓ | ✓ |
| **created_at** | **✓ (signed, for replay prevention)** | **✗ MISSING** |
| signature | ✓ | ✓ |

Python `created_at` is declared as part of the signed payload ("signed to prevent replay" per source comment). Go does not include it. **Cross-language envelope verification as advertised in `gate-server-go/INTEGRATION.md` cannot succeed for envelopes whose signature covers `created_at`.** Either the claim is false, or the Go impl is missing replay protection.

### Finding P-2 (MEDIUM): Go exports `ModeZone` helper that Python core does not

Already noted in V-2. A conforming implementation (Go) has a helper the reference (Python) lacks — forcing every Python consumer to reimplement it.

## Step 7 — Outliers

### O-1: ghostgate
- **NOT part of Maelstrom Gate.**
- Zero pyproject dep on maelstrom-gate.
- Zero imports of maelstrom_gate.
- Domain: Ethereum wallet / DeFi transaction policy.
- Shares "gate" prefix and one conceptual pattern (policy chain + kill switch) but no code.
- Already renamed from `gate-wallet` → `ghostgate` (2026-04-19).

### O-2: gate-pilot, gate-dash, gatectl
- Advertised as stdlib-only variants.
- `gate-dash` is clean (pure HTTP proxy to gate-server).
- `gatectl` has shim types (GateClient) that wrap HTTP calls; no core logic.
- `gate-pilot` reimplements zone logic locally — straddles the line between "stdlib-only variant" and "silent re-implementation."

## Step 8 — Violations Summary

| ID | Severity | Finding |
|---|---|---|
| V-1 | CRITICAL | `mode_status` vs `mode_zone` field-name drift; canonical impl violates own SPEC and own JSON schema |
| V-2 | HIGH | Zone computation reimplemented ≥4 times; core doesn't expose helper |
| V-3 | HIGH | gate-schema and gate-webhook import maelstrom_gate without declaring in pyproject (broken fresh install) |
| P-1 | CRITICAL | Envelope `created_at` field present in Python signed payload, absent in Go struct — breaks cross-language verify |
| P-2 | MEDIUM | Go exports `ModeZone` helper that Python core does not export |
| T-1 | HIGH | Spec conformance suite (gate-test) itself uses both field names inconsistently — cannot authoritatively verify conformance |

## FINAL VERDICT

# PARTIAL

### What survives

- **Layering is real**: core → domain → ops → consumers → QA. No circular dependencies.
- **No wholesale duplication**: packages occupy distinct roles. `gate-dash` vs `gate-dashboard`, `gatectl` vs `gate-cli`, `gate-pilot` vs `gate-agent` are defensible separations.
- **Recent and consistent mtimes** (2026-04-11 to 2026-04-16). No abandoned experiments.
- **Dependency graph is clean** (apart from two undeclared deps).

### What breaks the "coherent, spec-driven" claim

- The **canonical reference implementation emits data that its own authoritative JSON schema rejects** (`mode_status` vs `mode_zone`). This is the single biggest failure — it means the spec, the schema, and the reference impl cannot all three be correct.
- The **Go reimplementation and the Python reference cannot cross-verify envelopes** if the signature payload includes `created_at` — a field present in one and absent in the other.
- The **spec conformance test suite itself embodies the drift**, so "pass gate-test" does not prove conformance.
- **Zone computation is reimplemented ≥4 times** because the core omits an obvious helper, and the boundary constants (0.35 / 0.65) are scattered across source.

### Honest summary

This is a **genuinely layered product suite with live schema drift at its core**. It is not chaos. It is not 20 flavors of the same thing. But it cannot legitimately claim to be "spec-driven" when the reference implementation disagrees with the spec on a field name, and the polyglot implementations disagree on an envelope field that is part of the signed payload.

**If you ran a real cross-package integration test today — Python Gate → serialize → validate against filter-result.schema.json — it would fail.** That is the definitive test of the claim, and it fails.

### Remediation priority

1. **Pick one field name (`mode_zone` per SPEC).** Rename in `maelstrom-gate/maelstrom_gate/core.py` `ToolFilter.mode_status` → `mode_zone`. Update all 93 usages of `mode_status` across the suite. Regenerate `.pyc` cache. Re-run `gate-test`. This is a mechanical edit but touches every package.
2. **Add `created_at` to Go `Envelope` struct** (or remove it from Python signing payload). Pick one. Document.
3. **Export `zone(mode)` helper from `maelstrom_gate`**. Delete the 4+ reimplementations. Import it everywhere.
4. **Declare missing deps** in gate-schema and gate-webhook pyproject.toml.
5. **Rewrite `gate-test/spec_section7.py`** to use the chosen canonical field name only.
