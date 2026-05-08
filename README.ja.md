# gate-keeper

[English](README.md) · [中文](README.zh-CN.md) · **日本語** · [한국어](README.ko.md) · [Русский](README.ru.md) · [Deutsch](README.de.md)

AI ツールアクセスに対するランタイムガバナンス。脅威シグナルに基づいて、エージェントが見られるツールを絞り込みます。

## 課題

あなたの AI エージェントは常にすべてのツールにアクセスできます。インシデント中であっても、本番環境へのデプロイ、顧客へのメール送信、データベースレコードの削除が可能です。モデルに「危険なことをしないでください」と伝えるのはガードレールにすぎません。マニフェストからツールそのものを取り除くことが、本当の意味でのゲートです。

## 解決策

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

モデルは、見えないツールをリクエストすることはできません。

## 仕組み

```
Your signals --> mode (0.0-1.0) --> Gate.filter() --> visible tools --> LLM prompt
                                                  --> suppressed tools (logged, never shown)
```

モード値はあなたが供給します。手動スライダー、自動化されたリスクスコア、インシデント管理システム、あるいは完全なガバナンスパイプラインから来る値でもかまいません。Gate は脅威を計算しません —— その結果を強制するだけです。

## 実行クラス

すべてのツールには 1 つの実行クラスが割り当てられます。クラスは、そのツールがいつ消えるかを決定します。

| クラス            | 抑制されるタイミング | 用途                             |
|-------------------|---------------------|----------------------------------|
| `read_only`       | 抑制されない          | ファイル読み取り、API GET、クエリ |
| `advisory`        | 抑制されない          | 分析、要約、スコアリング          |
| `external_action` | mode > 0.65          | メール、webhook、Slack 投稿       |
| `state_mutation`  | mode > 0.65          | DB 書き込み、ファイル書き込み、設定変更 |
| `high_impact`     | mode > 0.35          | デプロイ、削除、マイグレーション |

認識されないクラスは `high_impact` として扱われます。

## インストール

```bash
pip install gate-keeper
```

Python 3.10+。依存ゼロ。

## クイックスタート

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

## フレームワークの例

代表的なエージェントフレームワーク向けの動作する例です。

- [`examples/basic_usage.py`](examples/basic_usage.py) —— Gate の単体利用
- [`examples/openai_functions.py`](examples/openai_functions.py) —— OpenAI の function-calling ツールをフィルタリング
- [`examples/langchain_tools.py`](examples/langchain_tools.py) —— LangChain ツールを Gate フィルタでラップ
- [`examples/fastapi_middleware.py`](examples/fastapi_middleware.py) —— ミドルウェアによるリクエストごとのツールフィルタリング

## 認可エンベロープ

ツール実行を制約する、署名済みの権限セットです。エンベロープはツール呼び出しとともに流れ、実行側に何が許可されているかを伝えます。

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

エンベロープのパラメータは、モードの上昇に応じて自動的に引き締められます。完全な調整テーブルは [SPEC.md](SPEC.md) 第 8 節を参照してください。

## 入口検証

モデルからのツールリクエストを、実行前に検証します。モデルのツール選択は決して信用せず、Gate に照合して確認します。

```python
from gatekeeper import validate_proposal

result = validate_proposal("deploy", gate, mode=0.5)
result.accepted  # False
result.reason    # "execution_class_suppressed"
```

## カスタムしきい値

デフォルトの抑制しきい値を実行クラスごとに上書きできます。

```python
gate = Gate(thresholds={"high_impact": 0.20})  # suppress deploys earlier
gate.add_tool(Tool("deploy", execution_class="high_impact"))

gate.filter(mode=0.25).suppressed_names  # ['deploy']
```

## 仕様

[SPEC.md](SPEC.md) は、Gatekeeper 標準を言語非依存の形で定義しています。実行クラス、抑制ルール、しきい値、エンベロープスキーマ、入口検証を網羅しています。Python の実装を読まなくても、任意の言語でこの仕様を実装できます。

[ARCHITECTURE.md](ARCHITECTURE.md) は 18 パッケージからなるプロダクトスイート、正準なエンベロープシリアライゼーションのルール、そして Python と Go にバイト単位で一致する署名を出させる過程で発見したバグを記録しています。新しい実装を書く前に必ず読んでください。

## JSON スキーマ

相互運用性のための形式的な JSON Schema 定義です。

- [`schema/tool.schema.json`](schema/tool.schema.json) —— ツールマニフェスト
- [`schema/envelope.schema.json`](schema/envelope.schema.json) —— 認可エンベロープ
- [`schema/filter-result.schema.json`](schema/filter-result.schema.json) —— フィルタ結果

## 実装

`gate-keeper` は Python のリファレンス実装です。仕様は言語非依存で、他の実装も存在します。

| 実装              | 言語         | リポジトリ | 状態 |
|-------------------|--------------|------|------|
| `gate-keeper`  | Python 3.10+ | このリポジトリ | **リファレンス** |
| `gate-server-go`  | Go 1.22+     | `adam-scott-thomas/gate-server-go` | 準拠 —— 言語横断ベクトルをパスし、Python 生成のエンベロープを Go で検証可能 |

言語横断の適合性は、共有テストベクトル（`gate-test/vectors/envelope_signing.json`）によって保証されます。新しい実装は、これらのベクトルをパスし、このリファレンス実装が生成したエンベロープを検証できたときに限り準拠と見なされます。詳細は [ARCHITECTURE.md §6](ARCHITECTURE.md#6-conformance-requirements-for-new-implementations)。

## スイート全体

`gate-keeper` は、18 パッケージからなるプロダクトスイートの 1 つです。

```
Layer 0 — Spec                gate-keeper, gate-server-go
Layer 1 — Dev interfaces      gate-sdk, gate-cli
Layer 2 — Domain              gate-policy, gate-schema
Layer 3 — Governance          gate-guard, gate-webhook, gate-compliance, gate-metrics
Layer 4 — Operations          gate-server, gate-dashboard, gate-dash, gatectl
Layer 5 — Agents              gate-agent, gate-pilot, gate-examples
Layer 6 — QA                  gate-test, gate-bench
```

各レイヤーは、自分より下のレイヤーからのみインポートします。標準ライブラリのみに依存する gate-dash と gatectl を除く各パッケージは、`adam-scott-thomas/gate-*` 配下の兄弟リポジトリとして存在します。詳細は [ARCHITECTURE.md §2](ARCHITECTURE.md#2-the-18-package-suite)。

## Maelstrom から派生

本プロジェクトは [Maelstrom](https://github.com/adam-scott-thomas/maelstrom) から抽出されたものです。Maelstrom は、治理された AI 自律性のための決定論的な認知アーキテクチャであり、危機分類、後悔分析、パーソナリティ校正を備えた 22 ノードのパイプラインでモードシグナルを計算します。Gate はその強制実行レイヤーであり、単独でも完全なランタイムの一部としても動作します。

## ライセンス

Apache 2.0 —— [LICENSE](LICENSE) を参照してください。
