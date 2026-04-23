# maelstrom-gate

[English](README.md) · **中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

面向 AI 工具访问的运行时治理。根据威胁信号过滤代理可见的工具。

## 问题

你的 AI 代理始终能访问全部工具。即便在事故期间，它仍然可以部署到生产环境、向客户发送邮件，并删除数据库记录。告诉模型“不要做危险的事情”只是一道护栏。把工具从它的清单中移除，才是一道闸门。

## 解决方案

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

模型无法请求它看不到的工具。

## 工作原理

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

模式值由你提供。它可以是一个手动滑块、一个自动化的风险评分、一套事件管理系统，或者一条完整的治理流水线。Gate 本身不计算威胁 —— 它只负责执行其后果。

## 执行类别

每个工具都有一个执行类别。类别决定了工具何时消失。

| 类别              | 何时抑制         | 适用于                         |
|-------------------|-----------------|--------------------------------|
| `read_only`       | 永不            | 读文件、API GET、查询          |
| `advisory`        | 永不            | 分析、摘要、评分               |
| `external_action` | mode > 0.65     | 邮件、webhook、Slack 发帖      |
| `state_mutation`  | mode > 0.65     | 数据库写入、文件写入、配置变更 |
| `high_impact`     | mode > 0.35     | 部署、删除、迁移               |

未识别的类别按 `high_impact` 处理。

## 安装

```bash
pip install maelstrom-gate
```

Python 3.10+。零依赖。

## 快速开始

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

## 框架示例

常见代理框架的可运行示例：

- [`examples/basic_usage.py`](examples/basic_usage.py) —— 独立使用 Gate
- [`examples/openai_functions.py`](examples/openai_functions.py) —— 过滤 OpenAI function-calling 工具
- [`examples/langchain_tools.py`](examples/langchain_tools.py) —— 用 Gate 过滤包装 LangChain 工具
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) —— 通过中间件实现按请求的工具过滤

## 授权信封

经过签名的权限集合，用于约束工具执行。信封随工具调用一起传递，告诉执行方它被允许做什么。

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

随着 mode 上升，信封参数会自动收紧。完整的调整表见 [SPEC.md](SPEC.md) 第 8 节。

## 入口校验

在执行之前，对来自模型的工具请求进行校验。永远不要信任模型的工具选择 —— 用 Gate 去验证它。

```python
from maelstrom_gate import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## 自定义阈值

按执行类别覆盖默认的抑制阈值：

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## 规范

[SPEC.md](SPEC.md) 以语言无关的方式定义了 Maelstrom Gate 标准。它涵盖执行类别、抑制规则、阈值、信封模式以及入口校验。无需阅读 Python 代码，你就可以在任意语言中实现它。

[ARCHITECTURE.md](ARCHITECTURE.md) 记录了 18 个包组成的产品套件、权威的信封序列化规则，以及我们在让 Python 与 Go 产生字节一致签名时抓到的 bug。编写新实现前请先阅读。

## JSON 模式

用于互操作的正式 JSON Schema 定义：

- [`schema/tool.schema.json`](schema/tool.schema.json) —— 工具清单
- [`schema/envelope.schema.json`](schema/envelope.schema.json) —— 授权信封
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) —— 过滤结果

## 实现

`maelstrom-gate` 是 Python 参考实现。本规范是语言无关的，已有其他实现：

| 实现              | 语言         | 仓库 | 状态 |
|-------------------|--------------|------|------|
| `maelstrom-gate`  | Python 3.10+ | 本仓库 | **参考实现** |
| `gate-server-go`  | Go 1.22+     | `adam-scott-thomas/gate-server-go` | 合规 —— 通过跨语言向量；Python 构建的信封可在 Go 中校验 |

跨语言一致性通过共享测试向量（`gate-test/vectors/envelope_signing.json`）强制保障。任何新实现当且仅当通过这些向量并能校验由本参考实现构建的信封时，才算合规。详见 [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations)。

## 整个套件

`maelstrom-gate` 是 18 个包组成的产品套件中的一员：

```
Layer 0 — Spec                maelstrom-gate, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

每一层仅从其下方的层导入。除了仅依赖标准库的变体 gate-dash、gatectl 之外，每个包都作为一个同级仓库存放在 `adam-scott-thomas/gate-*` 下。详见 [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite)。

## 源自 Maelstrom

本项目从 [Maelstrom](https://github.com/adam-scott-thomas/maelstrom) 中提取，它是一个面向受治理 AI 自主性的确定性认知架构。Maelstrom 通过一条 22 节点的流水线计算模式信号，包含危机分类、悔恨分析与人格校准。Gate 是它的强制执行层 —— 既可独立运行，也可作为完整运行时的一部分使用。

## 许可证

Apache 2.0 —— 详见 [LICENSE](LICENSE)。
