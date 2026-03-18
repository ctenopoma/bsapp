# エージェント議論ワークフロー 開発ガイド

このドキュメントでは、エージェント議論の動作をカスタマイズする方法を説明します。

---

## ディレクトリ構造

```
host/src/
├── agent_runner.py           # メインエントリ (LLM設定・API接続点)
├── session_manager.py        # セッション状態管理
├── models.py                 # データモデル定義
├── rag_manager.py            # RAG (ベクター検索)
└── workflow/                 # ★ 議論ワークフローの各ステップ
    ├── __init__.py
    ├── persona_selector.py   # 発言者の選択ロジック
    ├── prompt_builder.py     # LLMへのプロンプトテンプレート
    ├── input_builder.py      # エージェント入力の組み立て
    ├── history_compressor.py # 会話履歴のトークン圧縮
    ├── summarizer.py         # テーマ要約の生成
    ├── turn_runner.py        # テーマ内ターン実行 (ストラテジーディスパッチャー)
    ├── orchestrator.py       # マクロフロー・ディスパッチャー (テーマ間の進行制御)
    ├── json_utils.py         # JSON構造化出力ユーティリティ
    ├── template_resolver.py  # 事前情報内のテンプレート変数解決
    ├── strategies/           # ★ テーマ内ストラテジー（ミクロワークフロー）
    │   ├── base.py                  # ThemeStrategy 基底クラス
    │   ├── sequential.py            # シーケンシャル（バトンリレー）
    │   ├── parallel.py              # 並列独立（ブレスト）
    │   ├── round_robin_debate.py    # ラウンドロビン（順番ディベート）
    │   ├── hierarchical.py          # 階層型（計画・実行・反省）
    │   ├── adversarial.py           # 敵対的・レッドチーム（生成・批判）
    │   ├── judge_jury.py            # 陪審員・裁判官（Judge & Jury）
    │   ├── dynamic_routing.py       # 動的ルーティング（司会者主導）
    │   ├── map_reduce.py            # 分割統治（Map-Reduce）
    │   └── dynamic_generation.py   # 動的エージェント生成
    └── flows/                # ★ マクロワークフロー（テーマ間の進行制御）
        ├── base.py           # ProjectFlow 基底クラス + FlowContext
        ├── waterfall.py      # ウォーターフォール型（デフォルト）
        ├── v_shape.py        # V字型（実行＆逆順レビュー）
        ├── stage_gate.py     # ステージゲート型（関所付き直列）
        ├── agile_sprint.py   # アジャイル/スプリント型（反復ループ）
        ├── conditional.py    # 条件分岐/ツリー型（If-Then フロー）
        ├── game_theory.py    # ゲーム理論/対立型（陣営間ディベート）
        ├── blackboard.py     # ブラックボード型（共有黒板）
        └── tournament.py     # トーナメント/進化型（並列コンペ）
```

---

## ワークフローの全体像（2層構造）

```
セッション開始
    │
    ▼
[マクロフロー] orchestrator.py が project_flow に基づいてディスパッチ
    │
    │  ウォーターフォール / V字型 / ステージゲート / アジャイル /
    │  条件分岐 / ゲーム理論 / ブラックボード / トーナメント
    │
    ├─────────────────────────────────────────────────────┐
    ▼                                                     │
[テーマループ] flows/*.py がテーマ間の進行を制御            │
    │                                                     │
    ▼                                                     │
[ミクロストラテジー] turn_runner.py が theme_strategy に基づいてディスパッチ
    │
    │  sequential / parallel / round_robin_debate /
    │  hierarchical / adversarial / judge_jury /
    │  dynamic_routing / map_reduce / dynamic_generation
    │
    ├─① persona_selector.py
    │   └─ 次に発言するペルソナを選ぶ
    │
    ├─② input_builder.py
    │   └─ AgentInput を組み立てる
    │       (履歴圧縮・タスク割当・RAGコンテキスト・テンプレート解決)
    │
    ├─③ prompt_builder.py
    │   └─ プロンプトを生成して LLM へ送る
    │
    └─④ 発言を履歴に追記
                                                          │
    ▼                                                     │
⑤ summarizer.py                                          │
    └─ テーマ全体の要約を生成                               │
    │                                                     │
    └───────────── 次のテーマへ（マクロフローが制御） ──────┘

    ▼
最終レポート生成 (全テーマの要約を結合)
```

---

## テーマ内ストラテジー一覧（ミクロワークフロー）

| ストラテジーキー | 名称 | 概要 |
|---|---|---|
| `sequential` | シーケンシャル（デフォルト） | 各エージェントが順番に発言し次へバトンを渡す |
| `parallel` | 並列独立（ブレスト） | 全員が独立して発言し、ファシリテーターが集約 |
| `round_robin_debate` | ラウンドロビン | 全員が発言するループを複数回繰り返す |
| `hierarchical` | 階層型（計画・実行・反省） | マネージャーが計画→ワーカーが実行→評価ループ |
| `adversarial` | 敵対的・レッドチーム | 生成役と批判役が交互にダメ出し・修正を往復 |
| `judge_jury` | 陪審員・裁判官 | ディベーター間で議論し、裁判官が最終判定 |
| `dynamic_routing` | 動的ルーティング | 司会者が文脈を読んで次の発言者をJSON指名 |
| `map_reduce` | 分割統治（Map-Reduce） | プランナーがタスク分割→ワーカーが処理→統合 |
| `dynamic_generation` | 動的エージェント生成 | メタエージェントが最適なペルソナをその場で生成 |

`ThemeConfig.theme_strategy` で指定。設定値は `ThemeConfig.strategy_config` に渡す。

---

## マクロフロー一覧（テーマ間の進行制御）

| フローキー | 名称 | 概要 |
|---|---|---|
| `waterfall` | ウォーターフォール型（デフォルト） | テーマを順番に一度だけ実行 |
| `v_shape` | V字型 | 前半で全テーマ実行、後半は逆順でレビュー |
| `stage_gate` | ステージゲート型 | 各テーマ後にゲートキーパーが品質チェック・差し戻し |
| `agile_sprint` | アジャイル/スプリント型 | 全テーマを1スプリントとして複数回ループ |
| `conditional` | 条件分岐/ツリー型 | テーマ結論によってルーターが次テーマを動的選択 |
| `game_theory` | ゲーム理論/対立型 | 提案陣営と批判陣営が対立議論し合意案を導く |
| `blackboard` | ブラックボード型 | コーディネーターが黒板状態を読み次の担当を動的指名 |
| `tournament` | トーナメント/進化型 | 同一プロジェクトを複数レーンで独立実行し審査員が最良を選出 |

`SessionStartRequest.project_flow` で指定。設定値は `SessionStartRequest.flow_config` に渡す。

---

## 各モジュールのカスタマイズ方法

### 1. ペルソナ選択 — `workflow/persona_selector.py`

**何ができる**: 「次に誰が発言するか」のロジックを変更する

ファイル冒頭の定数を変えるだけで切り替えられる:

```python
# persona_selector.py
PERSONA_SELECTION_STRATEGY = "round_robin"  # ← ここを変更
```

| 値 | 動作 |
|---|---|
| `"random"` | 完全ランダム |
| `"round_robin"` | ターン順に全ペルソナを均等巡回 |
| `"role_first"` | 最初のターンだけ「リーダー」ロールを優先、以降はラウンドロビン |

> **Note:** `session.last_persona_id` に直前のペルソナIDが入っているので、
> 「前回と同じペルソナを避ける」といった実装に利用できる。テーマ切替時に自動リセット。

---

### 2. プロンプトテンプレート — `workflow/prompt_builder.py`

**何ができる**: LLMへの指示文（プロンプト）を変更する

主要な変数:
- `AGENT_PROMPT_TEMPLATE` — エージェントの発言プロンプト
- `SUMMARY_PROMPT_TEMPLATE` — テーマ要約プロンプト
- `DEFAULT_OUTPUT_FORMAT` — 発言の出力フォーマット

各ストラテジー・フロー専用のテンプレートも定義済み:
- `EVALUATION_PROMPT_TEMPLATE` — 階層型の評価
- `CRITIC_PROMPT_TEMPLATE` — 敵対的レッドチームの批判
- `JUDGE_PROMPT_TEMPLATE` — 裁判官の最終判定
- `GATEKEEPER_PROMPT_TEMPLATE` — ステージゲートの品質チェック
- `SPRINT_COMPLETION_PROMPT_TEMPLATE` — スプリント完成判定
- `FLOW_ROUTER_PROMPT_TEMPLATE` — 条件分岐のルーター
- `V_SHAPE_REVIEW_PROMPT_TEMPLATE` — V字型レビュー
- `GAME_THEORY_AGREEMENT_PROMPT_TEMPLATE` — ゲーム理論の合意形成
- `BLACKBOARD_COORDINATOR_PROMPT_TEMPLATE` — ブラックボードのコーディネーター
- `TOURNAMENT_JUDGE_PROMPT_TEMPLATE` — トーナメントの審査員

**カスタマイズ例:**

```python
# 発言フォーマットを変更 (箇条書きスタイル)
DEFAULT_OUTPUT_FORMAT = (
    "**{name}の見解**\n"
    "- 結論: (一言で)\n"
    "- 理由: (2〜3点)\n"
    "- 反論への回答: (あれば)"
)
```

---

### 3. エージェント入力の組み立て — `workflow/input_builder.py`

**何ができる**: エージェントに渡す情報の内容を変更する

タスク割り当て方法はファイル冒頭の定数で切り替えられる:

```python
# input_builder.py
TASK_SELECTION_STRATEGY = "round_robin"  # ← ここを変更
```

| 値 | 動作 |
|---|---|
| `"random"` | 完全ランダム |
| `"round_robin"` | ターン順にタスクを均等巡回 |
| `"role_match"` | ペルソナのロール名を含むタスクを優先、なければランダム |

> **Note:** `session.last_task_id` に直前のタスクIDが入っているので、
> 独自ストラテジーの実装に利用できる。テーマ切替時に自動リセット。

---

### 4. テーマ要約 — `workflow/summarizer.py`

**何ができる**: テーマ終了時の要約生成方法を変更する

要約は `session.history` の中から `msg.theme == session.current_theme` の発言だけを抽出して生成する。

**カスタマイズ例:**

```python
# 特定ペルソナの発言だけを要約に含める
theme_history = [
    msg for msg in session.history
    if msg.theme == session.current_theme and msg.agent_name != "モデレーター"
]
```

> **Note:** 要約プロンプトは Settings 画面の「要約プロンプト」フィールドから UI で編集できる。

---

### 5. ターン実行ループ — `workflow/turn_runner.py`

**何ができる**: ターンの進め方をストラテジーごとに切り替える

`ThemeConfig.theme_strategy` で指定されたストラテジーに処理を委譲するディスパッチャー。
新しいミクロストラテジーを追加する場合:

1. `strategies/my_strategy.py` を作成し `ThemeStrategy` を継承
2. `strategies/__init__.py` の `STRATEGY_MAP` に登録
3. フロントエンドの `THEME_STRATEGIES` に定義を追加

---

### 6. マクロフロー — `workflow/flows/`

**何ができる**: テーマ間の進行制御パターンを切り替える

`SessionStartRequest.project_flow` で指定されたフローに処理を委譲するディスパッチャー（`orchestrator.py`）。
新しいマクロフローを追加する場合:

1. `flows/my_flow.py` を作成し `ProjectFlow` を継承して `run(ctx: FlowContext)` を実装
2. `flows/__init__.py` の `FLOW_MAP` に登録
3. フロントエンドの `PROJECT_FLOWS` に定義を追加

---

## 開発の始め方

### バックエンドの起動

```bash
cd host
pip install -r requirements.txt   # 初回のみ
uvicorn main:app --reload --port 8000
```

### 変更 → 動作確認の流れ

1. `host/src/workflow/` 以下の任意のファイルを編集
2. `uvicorn` が自動リロード (--reload オプション)
3. フロントエンドから新規セッションを開始してテスト

---

## よくあるカスタマイズパターン

| やりたいこと | 編集するファイル |
|---|---|
| 発言者の順番を変えたい | `persona_selector.py` |
| エージェントへの指示文を変えたい | `prompt_builder.py` |
| 発言フォーマットを変えたい | `prompt_builder.py` (DEFAULT_OUTPUT_FORMAT) |
| 参照する会話履歴の件数を変えたい | `input_builder.py` |
| RAGの検索クエリをカスタマイズしたい | `input_builder.py` |
| 要約のスタイルを変えたい | `summarizer.py` |
| テーマ内の進め方を変えたい | `strategies/` に新ストラテジーを追加 |
| テーマ間の進行ルールを変えたい | `flows/` に新フローを追加 |
| LLMモデルや温度を変えたい | Settings 画面 or 環境変数 |
| LLMのエンドポイントを変えたい | 環境変数 `LLM_IP`, `LLM_PORT`, `LLM_MODEL` |

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `LLM_IP` | `127.0.0.1` | Ollama サーバーの IP |
| `LLM_PORT` | `11434` | Ollama サーバーのポート |
| `LLM_MODEL` | `llama3` | 使用するモデル名 |
| `LLM_API_KEY` | `dummy` | APIキー (Ollamaは不要) |
