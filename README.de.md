# gate-keeper

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Русский](README.ru.md) · **Deutsch**

Runtime Governance für den Tool-Zugriff von AI-Agenten. Filtere anhand eines Threat-Signals, welche Tools dein Agent überhaupt sieht.

## Das Problem

Dein AI-Agent hat jederzeit Zugriff auf jedes Tool. Auch mitten in einem Incident kann er noch in Production deployen, Kunden-E-Mails verschicken und Datenbank-Einträge löschen. Dem Modell zu sagen „tu nichts Gefährliches" ist eine Guardrail. Das Tool aus seinem Manifest zu entfernen, ist ein Gate.

## Die Lösung

```python
from gatekeeper import Gate, Tool

gate = Gate()
gate.add_tools([
    Tool("read_file", execution_class="read_only"),
    Tool("deploy",    execution_class="high_impact"),
])

gate.filter(mode=0.1).visible_names  # ['deploy', 'read_file']  -- calm
gate.filter(mode=0.5).visible_names  # ['read_file']            -- elevated
gate.filter(mode=0.8).visible_names  # ['read_file']            -- crisis
```

Das Modell kann kein Tool anfordern, das es nicht sieht.

## Funktionsweise

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

Den Mode-Wert lieferst du selbst. Er kann von einem manuellen Slider kommen, von einem automatisierten Risiko-Score, von einem Incident-Management-System oder aus einer kompletten Governance-Pipeline. Das Gate berechnet die Bedrohung nicht — es setzt nur ihre Konsequenzen durch.

## Execution Classes

Jedes Tool bekommt genau eine Execution Class. Die Class bestimmt, wann das Tool verschwindet.

| Class             | Unterdrückt, wenn | Einsatz für                      |
|-------------------|-------------------|----------------------------------|
| `read_only`       | Nie               | Datei-Reads, API-GETs, Queries   |
| `advisory`        | Nie               | Analysen, Zusammenfassungen, Scoring |
| `external_action` | mode > 0.65       | E-Mails, Webhooks, Slack-Posts   |
| `state_mutation`  | mode > 0.65       | DB-Writes, File-Writes, Config   |
| `high_impact`     | mode > 0.35       | Deploys, Löschungen, Migrationen |

Unbekannte Classes werden wie `high_impact` behandelt.

## Installation

```bash
pip install gate-keeper
```

Python 3.10+. Keine Abhängigkeiten.

## Quick Start

```python
from gatekeeper import Gate, Tool

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

## Framework-Beispiele

Lauffähige Beispiele für gängige Agent-Frameworks:

- [`examples/basic_usage.py`](examples/basic_usage.py) — Gate eigenständig nutzen
- [`examples/openai_functions.py`](examples/openai_functions.py) — OpenAI-Function-Calling-Tools filtern
- [`examples/langchain_tools.py`](examples/langchain_tools.py) — LangChain-Tools mit Gate-Filterung umhüllen
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) — per-Request Tool-Filterung via Middleware

## Authorization Envelopes

Signierte Berechtigungs-Sets, die die Tool-Ausführung einschränken. Das Envelope reist mit dem Tool-Call mit und sagt dem Executor, was er tun darf.

```python
from gatekeeper import build_envelope, verify_envelope, Tool

tool = Tool("read_file", execution_class="read_only")
envelope = build_envelope(tool, mode=0.5, context_id="session_1", signing_key="your-key")

envelope.budget_seconds   # 15  (reduced under elevated mode)
envelope.execution_mode   # "cautious"
envelope.max_tool_calls   # 10

verify_envelope(envelope, "your-key")   # True
verify_envelope(envelope, "wrong-key")  # False
```

Die Envelope-Parameter ziehen sich automatisch enger, wenn mode steigt. Die vollständige Anpassungstabelle steht in [SPEC.md](SPEC.md), Abschnitt 8.

## Ingress-Validierung

Validiere Tool-Requests vom Modell, bevor sie ausgeführt werden. Vertraue der Tool-Wahl des Modells nie — prüfe sie gegen das Gate.

```python
from gatekeeper import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## Eigene Schwellenwerte

Überschreibe die Default-Schwellen der Unterdrückung pro Execution Class:

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## Die Spec

[SPEC.md](SPEC.md) definiert den Maelstrom-Gate-Standard sprachunabhängig. Abgedeckt sind Execution Classes, Unterdrückungsregeln, Schwellenwerte, Envelope-Schemata und Ingress-Validierung. Du kannst das Ganze in einer beliebigen Sprache implementieren, ohne den Python-Code zu lesen.

[ARCHITECTURE.md](ARCHITECTURE.md) dokumentiert die 18 Pakete umfassende Produkt-Suite, die kanonischen Regeln der Envelope-Serialisierung und die Bugs, die wir gefunden haben, während wir Python und Go dazu gebracht haben, byte-identische Signaturen zu erzeugen. Lies das Dokument, bevor du eine neue Implementierung schreibst.

## JSON-Schemas

Formale JSON-Schema-Definitionen für Interoperabilität:

- [`schema/tool.schema.json`](schema/tool.schema.json) — Tool-Manifest
- [`schema/envelope.schema.json`](schema/envelope.schema.json) — Authorization Envelope
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) — Filterergebnis

## Implementierungen

`gate-keeper` ist die Python-Referenzimplementierung. Die Spec ist sprachunabhängig, und weitere Implementierungen existieren bereits:

| Implementierung   | Sprache      | Repository | Status |
|-------------------|--------------|------|------|
| `gate-keeper`  | Python 3.10+ | dieses Repo | **Referenz** |
| `gate-server-go`  | Go 1.22+     | `adam-scott-thomas/gate-server-go` | konform — besteht die sprachübergreifenden Vectors; von Python erzeugte Envelopes werden in Go verifiziert |

Cross-Language-Konformität wird über gemeinsame Test-Vectors (`gate-test/vectors/envelope_signing.json`) erzwungen. Eine neue Implementierung gilt genau dann als konform, wenn sie diese Vectors besteht und ein von dieser Referenz gebautes Envelope verifizieren kann. Siehe [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations).

## Die Suite

`gate-keeper` ist eines von 18 Paketen der Produkt-Suite:

```
Layer 0 — Spec                gate-keeper, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

Jeder Layer importiert nur aus den darunterliegenden Layern. Bis auf die reinen Stdlib-Varianten gate-dash und gatectl liegt jedes Paket als Schwester-Repo unter `adam-scott-thomas/gate-*`. Siehe [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite).

## Aus Maelstrom extrahiert

Extrahiert aus [Maelstrom](https://github.com/adam-scott-thomas/maelstrom), einer deterministischen Kognitions-Architektur für governede AI-Autonomie. Maelstrom berechnet das Mode-Signal über eine 22-Node-Pipeline mit Crisis-Klassifikation, Regret-Analyse und Personality-Kalibrierung. Das Gate ist die Durchsetzungsschicht — es läuft eigenständig oder als Teil der vollen Runtime.

## Lizenz

Apache 2.0 — siehe [LICENSE](LICENSE).
