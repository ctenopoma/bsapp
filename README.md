# BSapp: AI 多重ペルソナ ディスカッションアプリ

**BSapp** は、完全にローカルで動作するパーソナライズ可能なAIディスカッションアプリケーションです。
クラウドサービスに依存せず、自分自身のマシン上で高速・セキュアに**複数のAIエージェント**を対話させ、ディスカッションを生成・管理することができます。

このプロジェクトは、バックエンドとフロントエンドを含む**モノレポ（Monorepo）**として構成されています。

- **[`host/`](./host/)**: **FastAPI** と **LangChain** で構築されたバックエンド。複数AIエージェントの会話管理、**Qdrant** を用いた RAG（検索拡張生成）、およびローカルLLM（Ollama等）との通信を行います。
- **[`client/`](./client/)**: **Tauri + React + TypeScript** で構築されたデスクトップ向けフロントエンド。軽快でネイティブアプリと同等の操作感を提供します。

---

## 主な特徴

- **完全ローカル動作 (Privacy First)**: 全てのデータはあなたのマシン内に留まり、外部に送信されません。（`/v1` のOpenAI互換APIエンドポイント経由で、Ollama等のローカルLLMをフルサポート）
- **ダイナミック・マルチペルソナ・エンジン**: 様々な性格や役割（ペルソナ）を設定可能。バックエンドの自動モデレーションにより、AIエージェント同士が自律的に連続した議論を行います。
- **RAGによる文脈理解**: ディスカッションの文脈はローカルベクトルデータベース (Qdrant) に保存・検索され、過去のテーマや議論を賢く参照します。
- **ネイティブ・パフォーマンス**: Tauri（Rust）をベースに構築しており、軽量かつ非常に高速なデスクトップUIを実現しました。
- **LLM設定の秘匿化**: LLM接続情報（IP・ポート・モデル・APIキー）はサーバー側の `.env` のみで管理し、クライアントには公開されません。
- **設定の永続化**: ターン数やプロンプトテンプレートなどのアプリ設定は `host/settings.json` に保存され、サーバー再起動後も維持されます。

---

## リポジトリ構成

```text
bsapp/
├── host/                # FastAPI バックエンドサーバー (Python)
│   ├── src/
│   │   ├── api/         # REST API ルーター (session / rag / settings)
│   │   ├── workflow/    # エージェント議論ワークフロー (モジュール分離)
│   │   ├── main.py      # FastAPI アプリ本体・起動エントリ
│   │   ├── models.py    # Pydantic モデル定義
│   │   ├── app_settings.py  # 設定管理シングルトン
│   │   ├── session_manager.py
│   │   ├── agent_runner.py
│   │   └── rag_manager.py
│   ├── .env             # LLM接続設定 (秘匿・クライアント非公開)
│   ├── settings.json    # 永続化されたアプリ設定 (自動生成)
│   └── debug_test.py    # ワークフロー単体デバッグスクリプト
└── client/              # Tauri デスクトップアプリ (Node / Rust)
    ├── src/             # React フロントエンド (Vite + TypeScript)
    ├── src-tauri/       # Rust バックエンド処理
    └── ...
```

---

## 始め方 / 起動手順

BSappを使用するには、**バックエンド (`host`)** と **フロントエンド (`client`)** の両方を起動する必要があります。

### 1. 必要条件

以下がお使いの環境にインストールされていることを確認してください。

- [uv](https://docs.astral.sh/uv/) (高速なPythonパッケージマネージャ)
- [Node.js](https://nodejs.org/) & npm
- [Rust](https://www.rust-lang.org/tools/install) (Tauriのビルドに必須)
- [Docker](https://www.docker.com/) (Qdrantの起動に推奨)
- ローカルLLM環境: [Ollama](https://ollama.com/) などをインストールし、言語モデル（例: `llama3`）および埋め込みモデル（例: `nomic-embed-text`）を取得しておいてください。

---

### 2. バックエンド (`host`) の起動

**A. Qdrantの起動 (Docker経由)**
```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

**B. `.env` の設定**

`host/.env` を作成し、LLM接続情報を記載します（この情報はクライアントには公開されません）。

```env
LLM_IP=127.0.0.1
LLM_PORT=11434
LLM_MODEL=llama3
LLM_API_KEY=dummy
LLM_TEMPERATURE=0.7
TURNS_PER_THEME=5
```

**C. FastAPIサーバーの起動**
```bash
cd host
uv sync
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

---

### 3. フロントエンド (`client`) の起動

新しく別のターミナルを開き、Tauriアプリを開発モードで起動します。

```bash
cd client
npm install
npm run tauri dev
```

初回実行時はRustコードのコンパイルが走ります。完了するとネイティブのアプリケーションウィンドウが立ち上がります。

接続先のバックエンドURLを変更する場合は `client/.env` を作成してください。

```env
VITE_API_URL=http://127.0.0.1:8080
```

---

## 設定について

### LLM接続設定 (`host/.env`) — サーバー専用

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `LLM_IP` | `127.0.0.1` | LLMサーバーのIPアドレス |
| `LLM_PORT` | `11434` | LLMサーバーのポート番号 |
| `LLM_MODEL` | `llama3` | 使用するモデル名 |
| `LLM_API_KEY` | `dummy` | APIキー（ローカルなら dummy で可） |
| `LLM_TEMPERATURE` | `0.7` | 生成温度 |
| `TURNS_PER_THEME` | `5` | 1テーマあたりのターン数（デフォルト値） |

LLM接続情報はクライアントへのAPIレスポンスに含まれません。設定画面からも参照・変更できません。

### アプリ設定 (`host/settings.json`) — Settings 画面から変更可能

- **1テーマあたりのターン数**: セッション開始時のデフォルト値
- **デフォルト出力フォーマット**: テーマ・ペルソナで未指定の場合に使用
- **エージェント発言プロンプトテンプレート**: LLMへ渡すプロンプトの雛形
- **要約プロンプトテンプレート**: テーマ要約生成時のプロンプト雛形

設定は `host/settings.json` に永続化され、サーバー再起動後も維持されます。`.env` の値はフォールバック（`settings.json` が存在しない場合のデフォルト）として機能します。

Settings 画面の「接続確認」ボタンでサーバー稼働状態と LLM への疎通確認を行えます。

---

## デバッグ

`host/debug_test.py` を使用すると、LLM・Qdrantサーバーなしでワークフロー全体をローカルでデバッグできます。

```bash
cd host
python debug_test.py
```

- `USE_REAL_LLM = False`（デフォルト）: MockLLM でオフライン動作
- `USE_REAL_LLM = True`: `.env` のLLMを使用（`get_llm_config()` 経由）
- VSCode / PyCharm でブレイクポイントを置いてステップ実行可能
- 各テスト関数（`test_persona_selector` 等）を個別に呼び出せる
