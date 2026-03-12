# エージェント議論ワークフロー 開発ガイド

このドキュメントでは、エージェント議論の動作をカスタマイズする方法を説明します。

---

## ディレクトリ構造

```
host/src/
├── agent_runner.py          # メインエントリ (LLM設定・API接続点)
├── session_manager.py       # セッション状態管理
├── models.py                # データモデル定義
├── rag_manager.py           # RAG (ベクター検索)
└── workflow/                # ★ 議論ワークフローの各ステップ
    ├── __init__.py
    ├── persona_selector.py  # 1. 発言者の選択ロジック
    ├── prompt_builder.py    # 2. LLMへのプロンプトテンプレート
    ├── input_builder.py     # 3. エージェント入力の組み立て
    ├── summarizer.py        # 4. テーマ要約の生成
    └── turn_runner.py       # 5. ターン実行ループ
```

---

## ワークフローの全体像

```
セッション開始
    │
    ▼
[テーマループ] ─────────────────────────────────────┐
    │                                               │
    ▼                                               │
[ターンループ] (turns_per_theme 回)                  │
    │                                               │
    ├─① persona_selector.py                        │
    │   └─ 次に発言するペルソナを選ぶ               │
    │                                               │
    ├─② input_builder.py                           │
    │   └─ AgentInput を組み立てる                  │
    │       (履歴・タスク・RAGコンテキスト)         │
    │                                               │
    ├─③ prompt_builder.py                          │
    │   └─ プロンプトを生成して LLM へ送る          │
    │                                               │
    └─④ 発言を履歴に追記                           │
                                                    │
    ▼                                               │
⑤ summarizer.py                                    │
    └─ テーマ全体の要約を生成                        │
    │                                               │
    └───────────────────────── 次のテーマへ ────────┘

    ▼
最終レポート生成 (全テーマの要約を結合)
```

---

## 各モジュールのカスタマイズ方法

### 1. ペルソナ選択 — `workflow/persona_selector.py`

**何ができる**: 「次に誰が発言するか」のロジックを変更する

```python
def select_persona(personas, session) -> Persona:
    # デフォルト: ランダム選択
    return random.choice(personas)
```

**カスタマイズ例:**

```python
# ラウンドロビン (順番に全員が発言)
def select_persona(personas, session) -> Persona:
    idx = session.turn_count_in_theme % len(personas)
    return personas[idx]
```

```python
# 最初のターンはリーダーが発言
def select_persona(personas, session) -> Persona:
    if session.turn_count_in_theme == 0:
        leaders = [p for p in personas if "リーダー" in p.role]
        if leaders:
            return leaders[0]
    return random.choice(personas)
```

---

### 2. プロンプトテンプレート — `workflow/prompt_builder.py`

**何ができる**: LLMへの指示文（プロンプト）を変更する

変数:
- `AGENT_PROMPT_TEMPLATE` — エージェントの発言プロンプト
- `SUMMARY_PROMPT_TEMPLATE` — テーマ要約プロンプト
- `DEFAULT_OUTPUT_FORMAT` — 発言の出力フォーマット

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

```python
# プロンプトに「反論を意識して発言する」指示を追加
AGENT_PROMPT_TEMPLATE = """\
あなたは {role} です。
名前: {name} / タスク: {task}

議題: {query}
{rag_section}

直近の発言:
{history}

★ 他のメンバーの意見に対して積極的に反論・補足しながら発言してください。
{output_format}
"""
```

---

### 3. エージェント入力の組み立て — `workflow/input_builder.py`

**何ができる**: エージェントに渡す情報の内容を変更する

```python
def build_agent_input(session, persona, output_format="") -> AgentInput:
    ...
    history=session.history[-5:],  # ← 参照する履歴件数
    ...
```

**カスタマイズ例:**

```python
# 履歴をより多く参照 (直近10件)
history=session.history[-10:]

# 現在のテーマの発言のみを履歴として渡す
history=[m for m in session.history if m.theme == session.current_theme][-5:]

# タスクを役割に応じて固定割り当て
task_description = next(
    (t.description for t in session.tasks if persona.role in t.description),
    session.tasks[0].description if session.tasks else ""
)
```

---

### 4. テーマ要約 — `workflow/summarizer.py`

**何ができる**: テーマ終了時の要約生成方法を変更する

```python
def summarize_theme(session, llm) -> str:
    # theme_history に含まれる発言をもとにLLMが要約
    ...
```

**カスタマイズ例:**

```python
# 特定ペルソナの発言だけを要約に含める
theme_history = [
    msg for msg in session.history
    if msg.theme == session.current_theme and msg.agent_name != "モデレーター"
]
```

```python
# SUMMARY_PROMPT_TEMPLATE を変えて箇条書きの要約にする
SUMMARY_PROMPT_TEMPLATE = """\
テーマ「{theme}」の議論を以下の形式でまとめてください:

## 合意点
## 対立点
## 今後の論点

ディスカッション履歴:
{history}
"""
```

---

### 5. ターン実行ループ — `workflow/turn_runner.py`

**何ができる**: ターンの進め方・繰り返し方法を変更する

```python
def run_one_theme(session, agent_executor, summarizer) -> str:
    for _ in range(session.turns_per_theme):
        persona = select_persona(active, session)
        agent_input = build_agent_input(session, persona)
        message = agent_executor(agent_input)
        # 履歴追記...
    return summarizer(session)
```

**カスタマイズ例:**

```python
# 発言後にモデレーターのコメントを挿入
for _ in range(session.turns_per_theme):
    persona = select_persona(active, session)
    agent_input = build_agent_input(session, persona)
    message = agent_executor(agent_input)
    # 発言を履歴追記 ...

    # モデレーターが要約・整理コメントを追加 (3ターンごと)
    if session.turn_count_in_theme % 3 == 0:
        mod_input = build_moderator_input(session)
        mod_message = agent_executor(mod_input)
        # モデレーターの発言も履歴追記 ...
```

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

### 素早く単体テストする

```python
# host/ ディレクトリで実行
python -c "
from src.workflow.persona_selector import select_persona
from src.models import Persona, RagConfig

# ダミーデータで動作確認
personas = [
    Persona(id='a', name='Alice', role='楽観主義者', rag_config=RagConfig()),
    Persona(id='b', name='Bob',   role='批評家',     rag_config=RagConfig()),
]

class FakeSession:
    turn_count_in_theme = 0

result = select_persona(personas, FakeSession())
print(result.name)
"
```

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
| テーマ間でモデレーターを挟みたい | `turn_runner.py` |
| LLMモデルや温度を変えたい | `agent_runner.py` (GLOBAL_LLM) |
| LLMのエンドポイントを変えたい | 環境変数 `LLM_IP`, `LLM_PORT`, `LLM_MODEL` |

---

## 環境変数

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `LLM_IP` | `127.0.0.1` | Ollama サーバーの IP |
| `LLM_PORT` | `11434` | Ollama サーバーのポート |
| `LLM_MODEL` | `llama3` | 使用するモデル名 |
| `LLM_API_KEY` | `dummy` | APIキー (Ollamaは不要) |
