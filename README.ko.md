# gate-keeper

[English](README.md) · [中文](README.zh-CN.md) · [日本語](README.ja.md) · **한국어** · [Русский](README.ru.md) · [Deutsch](README.de.md)

AI 도구 접근에 대한 런타임 거버넌스. 위협 시그널을 기반으로 에이전트가 볼 수 있는 도구를 필터링합니다.

## 문제

여러분의 AI 에이전트는 항상 모든 도구에 접근할 수 있습니다. 사고(incident) 상황에서도 프로덕션에 배포하고, 고객에게 이메일을 보내고, 데이터베이스 레코드를 삭제할 수 있습니다. 모델에게 "위험한 일을 하지 말라"고 말하는 것은 가드레일일 뿐입니다. 모델의 매니페스트에서 도구 자체를 제거해야 비로소 게이트가 됩니다.

## 해결책

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

모델은 보이지 않는 도구를 요청할 수 없습니다.

## 동작 방식

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

모드 값은 여러분이 제공합니다. 수동 슬라이더, 자동화된 리스크 점수, 인시던트 관리 시스템, 또는 완전한 거버넌스 파이프라인에서 올 수 있습니다. Gate는 위협을 계산하지 않습니다 —— 그 결과만 집행합니다.

## 실행 클래스

모든 도구는 하나의 실행 클래스를 가집니다. 클래스는 도구가 언제 사라지는지를 결정합니다.

| 클래스            | 억제 조건        | 용도                             |
|-------------------|-----------------|----------------------------------|
| `read_only`       | 억제되지 않음     | 파일 읽기, API GET, 쿼리          |
| `advisory`        | 억제되지 않음     | 분석, 요약, 점수화                |
| `external_action` | mode > 0.65      | 이메일, webhook, Slack 게시      |
| `state_mutation`  | mode > 0.65      | DB 쓰기, 파일 쓰기, 설정 변경    |
| `high_impact`     | mode > 0.35      | 배포, 삭제, 마이그레이션         |

인식되지 않는 클래스는 `high_impact`로 취급합니다.

## 설치

```bash
pip install gate-keeper
```

Python 3.10+. 의존성 없음.

## 빠른 시작

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

## 프레임워크 예제

대표적인 에이전트 프레임워크를 위한 동작 예제입니다.

- [`examples/basic_usage.py`](examples/basic_usage.py) —— Gate 단독 사용
- [`examples/openai_functions.py`](examples/openai_functions.py) —— OpenAI function-calling 도구 필터링
- [`examples/langchain_tools.py`](examples/langchain_tools.py) —— LangChain 도구를 Gate 필터로 래핑
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) —— 미들웨어를 통한 요청별 도구 필터링

## 인가 봉투 (Authorization Envelope)

도구 실행을 제약하는 서명된 권한 집합입니다. 봉투는 도구 호출과 함께 전달되며, 실행자에게 무엇이 허용되는지 알려 줍니다.

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

모드가 상승하면 봉투 파라미터는 자동으로 더 엄격해집니다. 전체 조정 표는 [SPEC.md](SPEC.md) 섹션 8을 참조하십시오.

## 입구 검증 (Ingress Validation)

모델로부터 오는 도구 요청을 실행 전에 검증합니다. 모델의 도구 선택을 절대 신뢰하지 말고 —— Gate에 대조하여 확인하십시오.

```python
from gatekeeper import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## 사용자 정의 임계값

실행 클래스별로 기본 억제 임계값을 재정의합니다.

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## 명세

[SPEC.md](SPEC.md)는 Gatekeeper 표준을 언어 독립적으로 정의합니다. 실행 클래스, 억제 규칙, 임계값, 봉투 스키마, 입구 검증을 모두 포함합니다. Python 코드를 읽지 않고도 어떤 언어로든 구현할 수 있습니다.

[ARCHITECTURE.md](ARCHITECTURE.md)는 18개 패키지로 구성된 제품 스위트, 표준 봉투 직렬화 규칙, 그리고 Python과 Go가 바이트 단위로 일치하는 서명을 만들도록 하면서 발견한 버그들을 문서화합니다. 새 구현을 작성하기 전에 반드시 읽으십시오.

## JSON 스키마

상호 운용성을 위한 형식적 JSON Schema 정의입니다.

- [`schema/tool.schema.json`](schema/tool.schema.json) —— 도구 매니페스트
- [`schema/envelope.schema.json`](schema/envelope.schema.json) —— 인가 봉투
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) —— 필터 결과

## 구현체

`gate-keeper`는 Python 참조 구현입니다. 명세는 언어 독립적이며, 다른 구현도 존재합니다.

| 구현체            | 언어         | 저장소 | 상태 |
|-------------------|--------------|------|------|
| `gate-keeper`  | Python 3.10+ | 이 저장소 | **참조 구현** |
| `gate-server-go`  | Go 1.22+     | `adam-scott-thomas/gate-server-go` | 준수 —— 언어 간 벡터 통과, Python이 만든 봉투를 Go에서 검증 가능 |

언어 간 준수성은 공유 테스트 벡터(`gate-test/vectors/envelope_signing.json`)를 통해 강제됩니다. 새 구현은 해당 벡터를 통과하고 본 참조 구현이 만든 봉투를 검증할 수 있을 때에만 준수로 간주됩니다. 자세한 내용은 [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations) 참조.

## 전체 스위트

`gate-keeper`는 18개 패키지로 구성된 제품 스위트의 한 패키지입니다.

```
Layer 0 — Spec                gate-keeper, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

각 레이어는 자신보다 아래 레이어에서만 import 합니다. 표준 라이브러리만 사용하는 변형인 gate-dash, gatectl을 제외한 모든 패키지는 `adam-scott-thomas/gate-*` 아래의 형제 저장소로 존재합니다. 자세한 내용은 [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite) 참조.

## Maelstrom에서 추출

이 프로젝트는 [Maelstrom](https://github.com/adam-scott-thomas/maelstrom)에서 추출되었습니다. Maelstrom은 거버넌스 기반 AI 자율성을 위한 결정론적 인지 아키텍처로, 위기 분류, 후회 분석, 퍼스낼리티 보정을 포함한 22 노드 파이프라인으로 모드 시그널을 계산합니다. Gate는 그 집행 레이어이며 —— 단독으로도, 또는 완전한 런타임의 일부로도 동작합니다.

## 라이선스

Apache 2.0 —— [LICENSE](LICENSE) 참조.
