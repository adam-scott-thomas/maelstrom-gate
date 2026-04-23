# maelstrom-gate

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Русский** · [Deutsch](README.de.md)

Runtime governance для доступа AI-агентов к инструментам. Фильтрация того, какие инструменты видит ваш агент, на основе сигнала угрозы.

## Проблема

Ваш AI-агент имеет доступ ко всем инструментам постоянно. Во время инцидента он по-прежнему может развернуть код в production, отправить письма клиентам и удалить записи из базы данных. Сказать модели «не делай ничего опасного» — это ограждение. Убрать инструмент из её манифеста — это уже шлюз (gate).

## Решение

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

Модель не может запросить инструмент, которого она не видит.

## Как это работает

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

Значение режима (mode) задаёте вы. Это может быть ручной ползунок, автоматический рисковый скор, система управления инцидентами или целый конвейер governance. Gate не вычисляет угрозу — он обеспечивает её последствия.

## Классы выполнения

Каждому инструменту присваивается ровно один класс выполнения. Класс определяет, когда инструмент исчезает.

| Класс             | Когда подавляется | Используется для                   |
|-------------------|-------------------|------------------------------------|
| `read_only`       | Никогда           | Чтение файлов, API GET, запросы    |
| `advisory`        | Никогда           | Анализ, сводки, скоринг            |
| `external_action` | mode > 0.65       | Почта, webhooks, сообщения в Slack |
| `state_mutation`  | mode > 0.65       | Запись в БД, запись файлов, конфиг |
| `high_impact`     | mode > 0.35       | Деплои, удаления, миграции         |

Нераспознанные классы трактуются как `high_impact`.

## Установка

```bash
pip install maelstrom-gate
```

Python 3.10+. Нулевые зависимости.

## Быстрый старт

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

## Примеры фреймворков

Рабочие примеры для распространённых агентных фреймворков:

- [`examples/basic_usage.py`](examples/basic_usage.py) — автономное использование gate
- [`examples/openai_functions.py`](examples/openai_functions.py) — фильтрация OpenAI function-calling инструментов
- [`examples/langchain_tools.py`](examples/langchain_tools.py) — обёртка LangChain-инструментов gate-фильтрацией
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) — пер-запросная фильтрация инструментов через middleware

## Конверты авторизации (Authorization Envelopes)

Подписанные наборы разрешений, ограничивающие выполнение инструмента. Конверт путешествует вместе с вызовом и сообщает исполнителю, что ему разрешено делать.

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

Параметры конверта автоматически ужесточаются при росте mode. Полная таблица корректировок — в [SPEC.md](SPEC.md), раздел 8.

## Валидация на входе (Ingress Validation)

Проверяйте запросы модели на выполнение инструментов до их запуска. Никогда не доверяйте выбору модели — сверьте его с gate.

```python
from maelstrom_gate import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## Пользовательские пороги

Переопределите пороги подавления по умолчанию для каждого класса выполнения:

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## Спецификация

[SPEC.md](SPEC.md) определяет стандарт Maelstrom Gate в языконезависимой форме. Он охватывает классы выполнения, правила подавления, пороги, схемы конвертов и валидацию на входе. Его можно реализовать на любом языке, не заглядывая в Python.

[ARCHITECTURE.md](ARCHITECTURE.md) описывает пакетный набор из 18 компонентов, канонические правила сериализации конвертов и баги, которые мы поймали, добиваясь побайтно идентичных подписей от Python и Go. Прочитайте этот документ, прежде чем писать новую реализацию.

## JSON-схемы

Формальные определения JSON Schema для совместимости:

- [`schema/tool.schema.json`](schema/tool.schema.json) — манифест инструмента
- [`schema/envelope.schema.json`](schema/envelope.schema.json) — конверт авторизации
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) — результат фильтрации

## Реализации

`maelstrom-gate` — это эталонная реализация на Python. Спецификация языконезависима, и другие реализации уже существуют:

| Реализация        | Язык         | Репозиторий | Статус |
|-------------------|--------------|------|------|
| `maelstrom-gate`  | Python 3.10+ | этот репозиторий | **эталонная** |
| `gate-server-go`  | Go 1.22+     | `adam-scott-thomas/gate-server-go` | соответствует — проходит межъязыковые векторы; конверты, созданные на Python, проверяются в Go |

Межъязыковое соответствие обеспечивается общими тестовыми векторами (`gate-test/vectors/envelope_signing.json`). Любая новая реализация считается соответствующей тогда и только тогда, когда она проходит эти векторы и способна проверить конверт, созданный этой эталонной реализацией. См. [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations).

## Полный набор (The Suite)

`maelstrom-gate` — один из 18 пакетов продуктового набора:

```
Layer 0 — Spec                maelstrom-gate, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

Каждый слой импортирует только из нижележащих слоёв. Все пакеты, кроме вариантов, зависящих только от стандартной библиотеки (gate-dash, gatectl), живут как соседние репозитории под `adam-scott-thomas/gate-*`. См. [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite).

## Извлечён из Maelstrom

Извлечён из [Maelstrom](https://github.com/adam-scott-thomas/maelstrom) — детерминированной когнитивной архитектуры для управляемой автономии AI. Maelstrom вычисляет сигнал mode через конвейер из 22 узлов с классификацией кризиса, анализом сожалений (regret analysis) и калибровкой личности. Gate — это слой принуждения: работает как самостоятельно, так и в составе полного рантайма.

## Лицензия

Apache 2.0 — см. [LICENSE](LICENSE).
