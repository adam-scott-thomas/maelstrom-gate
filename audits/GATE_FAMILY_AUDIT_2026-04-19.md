---
audit_date: 2026-04-19
auditor: claude-opus-4-7
scope: gate-* family (20 directories in D:\lost_marbles\)
health: AMBER
status: open
prior_audit: AUDIT-2026-03-24.md
diff_from_prior: |
  Prior audits covered only maelstrom-gate itself. This is the first audit of the
  full 20-directory gate-* family and surfaces the architectural coherence of the
  ecosystem, plus the gate-wallet/ghostgate naming collision.
findings_added:
  - GATE-FAM-001 HIGH  19 gate-* packages missing git init
  - GATE-FAM-002 MEDIUM gate-wallet is ghostgate (naming collision)
  - GATE-FAM-003 LOW   gate-server-go polyglot spec not documented in maelstrom-gate README
  - GATE-FAM-004 LOW   No ARCHITECTURE.md explaining the 18-package suite
---

# Gate Family Audit — 2026-04-19

## Scope

All 20 directories in `D:\lost_marbles\` matching `gate*` or `maelstrom-gate`.

## Executive Summary

The user's original assumption was that the gate-* family were "versions/variants of
maelstrom-gate" — some duplication concern. **Audit refutes this**: 18 of the 20 are a
coherent, intentionally-layered product suite built around a single spec. 1 is a
polyglot reimplementation (Go). 1 is a different product (gate-wallet = GhostGate,
crypto wallet governance) that shares the directory prefix but no code.

**Bottom line:** This is a real standards-style product ecosystem (spec → reference
implementation → SDKs → operational tooling → observability → compliance), not a pile
of duplicates. It is unprotected: only 1 of 20 packages has git.

## Layer Structure

### Layer 0 — Core Specification
- **maelstrom-gate** — Python reference implementation (`Gate`, `Tool`, mode 0.0–1.0,
  suppression thresholds). Only package with git history. SPEC.md present. Published to
  PyPI. **Canonical.**

### Layer 0b — Alternate Implementation
- **gate-server-go** (Go, 1046 LOC, 10 files) — Reimplements the gate spec in Go.
  Cross-language envelope verification: Python-signed envelopes verify in Go and vice
  versa. Standalone HTTP server on `/v1/filter`, `/v1/validate`, `/v1/thresholds`,
  `/v1/envelope/*`.

### Layer 1 — Developer Interfaces
- **gate-sdk** (26 files, 1936 LOC) — `GateClient`, framework adapters (OpenAI,
  Anthropic, webhook receiver).
- **gate-cli** (19 files) — Operator's CLI built on click + httpx + rich.

### Layer 2 — Domain Logic & Policy
- **gate-policy** (19 files, 425 LOC) — Declarative policy engine over base Gate.
- **gate-schema** (7 files) — JSON Schema for tools/policies/envelopes/filter results.
  No maelstrom-gate dep (decoupled by design).

### Layer 3 — Governance & Enforcement
- **gate-guard** (7 files) — Runtime enforcement; blocks unauthorized execution, not
  just filters manifest.
- **gate-compliance** (28 files, largest package) — Audit trail, evidence reports.
- **gate-webhook** (11 files, stdlib only) — Event broadcasting.

### Layer 4 — Operational Deployment
- **gate-server** (15 files) — FastAPI HTTP service wrapping core.
- **gate-dashboard** (10 files, 676 LOC with templates) — FastAPI + Jinja2 web UI.
- **gate-metrics** (11 files) — Prometheus-compatible metrics.

### Layer 5 — Agent Examples & Demo
- **gate-agent** (11 files) — Autonomous agent governed by Gate (dogfood).
- **gate-examples** (13 files) — Onboarding integration examples.

### Layer 6 — Minimalist Variants (stdlib-only)
- **gate-dash** (7 files) — Zero-dep alternative to gate-dashboard.
- **gate-pilot** (6 files) — Minimal Gate-governed agent.
- **gatectl** (6 files) — Interactive Gate CLI (REPL + one-shot).

### Layer 7 — QA
- **gate-test** (13 files) — Cross-language spec conformance test suite.
- **gate-bench** (7 files) — Performance benchmarks.

## Outlier — NOT part of Maelstrom Gate

- **gate-wallet** (16 files) — Package name in code is `ghostgate`. Different product:
  circuit breaker between autonomous bots and on-chain wallet drainage. Ethereum/DeFi
  domain. Zero dependencies on maelstrom-gate. Shares only the "gate" vocabulary by
  concept (policy chain + kill switch), not by code.
  - **Action:** Rename directory to `ghostgate` to match package name. Remove from
    mental model of the Maelstrom Gate suite.

## Dependency Graph

```
maelstrom-gate (core, git-tracked)
  ├─ gate-schema            [no reverse dep]
  ├─ gate-guard
  ├─ gate-compliance
  ├─ gate-policy
  ├─ gate-webhook
  ├─ gate-metrics
  ├─ gate-bench
  ├─ gate-test              [conformance — any implementation]
  ├─ gate-examples          [+ gate-policy]
  ├─ gate-sdk               [+ framework adapters]
  │   └─ gate-agent         [+ gate-server optional]
  ├─ gate-server            [FastAPI]
  ├─ gate-dashboard         [+ gate-policy]
  └─ gate-cli

gate-server-go               [standalone Go reimplementation]
gate-dash / gate-pilot / gatectl  [stdlib-only minimalist alternatives]

ghostgate (formerly gate-wallet)  [separate product, unrelated to core]
```

## Findings

### GATE-FAM-001 (HIGH) — 19 packages missing git init
**Scope:** all gate-* dirs except maelstrom-gate
**Evidence:** `ls -d D:/lost_marbles/gate-*/.git` returns no results for these 19.
**Risk:** ~5,000+ LOC of real, coherent architecture lives only on D: drive with no
version history and no remote backup. Disk failure = total loss.
**Remediation:** git init each + initial commit with proper `.gitignore` (covers .env,
*.key, *.pem, __pycache__, *.egg-info, node_modules).

### GATE-FAM-002 (MEDIUM) — gate-wallet is ghostgate (naming collision)
**Scope:** gate-wallet
**Evidence:** README.md describes product as "GhostGate"; package name in pyproject.toml
is `ghostgate`; explicitly states "zero hard deps on gate-sdk, gate-policy,
gate-compliance"; different problem domain (wallet security, not tool access).
**Risk:** Owner already confused by this (stated gate-* are "all versions of
maelstrom-gate, the crypto part is just a version" — audit shows it is NOT).
**Remediation:** Rename directory to `ghostgate` to match package name.

### GATE-FAM-003 (LOW) — Polyglot spec not documented in README
**Scope:** maelstrom-gate
**Evidence:** gate-server-go reimplements SPEC in Go with cross-language envelope
verify, but maelstrom-gate/README.md does not mention Go implementation or that SPEC.md
is implementation-agnostic.
**Remediation:** Add "Implementations" section to maelstrom-gate/README.md linking to
gate-server-go.

### GATE-FAM-004 (LOW) — No ARCHITECTURE.md for the 18-package suite
**Scope:** maelstrom-gate
**Evidence:** The layered architecture (core → policy → compliance → deployment → SDKs
→ observability) is not documented anywhere outside individual package READMEs. New
contributors and even the owner can't see the full picture.
**Remediation:** Add `maelstrom-gate/ARCHITECTURE.md` with the dependency graph and
layer structure from this audit.

## Observations (not findings)

- **All packages are recent and consistent** (file mtimes 2026-04-11 through
  2026-04-16). No abandoned experiments.
- **No dead code or stubs** — all packages have real source. Smallest is 6 files
  (gatectl, gate-pilot); largest is 28 files (gate-compliance).
- **Three stdlib-only variants** (gate-dash, gate-pilot, gatectl) are deliberate "zero
  external deps for operators" alternatives, not scratch.

## Workspace-Level Impact

The `administration/AUDIT_INDEX.md` entry "Projects missing git: 34" includes all 19
gate-* packages under `action=git_init`. After remediation of GATE-FAM-001, that number
drops to ~15 and the remaining ones are genuinely unaudited (ghostlogic-revenue-engine,
reasoner, voip-pbx, etc.) rather than a coherent product suite.

## Next Actions

1. [owner] Confirm rename gate-wallet → ghostgate (done: confirmed 2026-04-19)
2. [claude] Scan each of 20 dirs for secrets (.env, private keys) before git init
3. [claude] Add `.gitignore` to each dir covering .env, *.key, *.pem, __pycache__,
   *.egg-info, node_modules
4. [claude] git init + initial commit each (local only per owner preference)
5. [owner] Decide later: push to `adam-scott-thomas/gate-*` on GitHub (public, matching
   maelstrom-gate pattern)
6. [claude] Write maelstrom-gate/ARCHITECTURE.md (GATE-FAM-004)
7. [claude] Update maelstrom-gate/README.md with Implementations section (GATE-FAM-003)
