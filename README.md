# BSapp: AI 多重ペルソナ ディスカッションアプリ

**BSapp** は、完全にローカルで動作するパーソナライズ可能なAIディスカッションアプリケーションです。
クラウドサービスに依存せず、自分自身のマシン上で高速・セキュアに**複数のAIエージェント**を対話させ、ディスカッションを生成・管理することができます。

このプロジェクトは、バックエンドとフロントエンドを含む**モノレポ（Monorepo）**として構成されています。

- **[`host/`](./host/)**: **FastAPI** と **LangChain** で構築されたバックエンド。複数AIエージェントの会話管理、**Qdrant** を用いた RAG（検索拡張生成）、特許調査ワークフロー、およびローカルLLM（Ollama等）との通信を行います。
- **[`client/`](./client/)**: **Tauri + React + TypeScript** で構築されたデスクトップ向けフロントエンド。軽快でネイティブアプリと同等の操作感を提供します。

---

## 主な特徴

- **完全ローカル動作 (Privacy First)**: 全てのデータはあなたのマシン内に留まり、外部に送信されません。（OpenAI互換APIエンドポイント経由で、Ollama等のローカルLLMをフルサポート）
- **ダイナミック・マルチペルソナ・エンジン**: 様々な性格や役割（ペルソナ）を設定可能。バックエンドの自動モデレーションにより、AIエージェント同士が自律的に連続した議論を行います。
- **RAGによる文脈理解**: ディスカッションの文脈はローカルベクトルデータベース (Qdrant) に保存・検索され、過去のテーマや議論を賢く参照します。
- **会話履歴圧縮**: 長い議論でもトークン上限を超えないよう、古い履歴を自動圧縮（要約）します。直近N件の発言は常に保持されます。
- **特許調査ワークフロー**: CSVファイルから企業ごとの特許情報を読み込み、LLMが各企業のレポートと全体サマリーを自動生成します。
- **セルフホスト型アップデート配布**: バックエンドサーバーがクライアントのインストーラーを配信。起動時に新バージョンが検出されると、アプリ内バナーでダウンロードを案内します。
- **ネイティブ・パフォーマンス**: Tauri（Rust）をベースに構築しており、軽量かつ非常に高速なデスクトップUIを実現しました。
- **LLM設定の秘匿化**: LLM接続情報（IP・ポート・モデル・APIキー）はサーバー側の `.env` のみで管理し、クライアントには公開されません。
- **インアプリマニュアル**: サイドバーの「Manual」からアプリ内マニュアルを参照可能。マークダウンファイル（`client/src/manual/`）を編集するだけで更新できます。
- **AIヘルパー機能**: New Session・Personas・Tasks 各ページに「ヘルパー」ボタンを搭載。入力項目の書き方をAIにチャットで相談し、提案をフォームに直接反映できます。ヘルパーの知識は `host/knowledge/` のMarkdownファイルで管理します。
- **設定の永続化**: ターン数やプロンプトテンプレートなどのアプリ設定は `host/settings.json` に保存され、サーバー再起動後も維持されます。

---

## リポジトリ構成

```text
bsapp/
├── host/                    # FastAPI バックエンドサーバー (Python)
│   ├── src/
│   │   ├── api/             # REST API ルーター
│   │   │   ├── session.py   # セッション管理 API
│   │   │   ├── rag.py       # RAG API
│   │   │   ├── settings.py  # アプリ設定 API
│   │   │   ├── patent.py    # 特許調査 API
│   │   │   └── update.py    # クライアントアップデート配布 API
│   │   ├── workflow/        # エージェント議論ワークフロー
│   │   │   ├── turn_runner.py       # ターン実行
│   │   │   ├── persona_selector.py  # 発言ペルソナ選択
│   │   │   ├── prompt_builder.py    # プロンプト構築
│   │   │   ├── input_builder.py     # エージェント入力組み立て
│   │   │   ├── summarizer.py        # テーマ要約
│   │   │   ├── history_compressor.py # 会話履歴圧縮
│   │   │   └── patent/              # 特許調査サブワークフロー
│   │   │       ├── analyzer.py      # 企業別レポート生成
│   │   │       ├── summarizer.py    # 全体サマリー生成
│   │   │       └── prompt_builder.py
│   │   ├── main.py          # FastAPI アプリ本体・起動エントリ
│   │   ├── models.py        # Pydantic モデル定義
│   │   ├── app_settings.py  # 設定管理シングルトン
│   │   ├── session_manager.py
│   │   ├── agent_runner.py
│   │   └── rag_manager.py
│   ├── client_dist/         # アップデート配布ファイル置き場 (自動生成)
│   │   ├── version.json     # バージョン情報 (開発者が更新)
│   │   └── *.exe / *.AppImage  # インストーラー本体
│   ├── .env                 # LLM接続設定 (秘匿・クライアント非公開)
│   ├── settings.json        # 永続化されたアプリ設定 (自動生成)
│   └── debug_test.py        # ワークフロー単体デバッグスクリプト
└── client/                  # Tauri デスクトップアプリ (Node / Rust)
    ├── src/                 # React フロントエンド (Vite + TypeScript)
    │   ├── components/
    │   │   ├── SetupScreen.tsx         # 新規セッション設定
    │   │   ├── DiscussionScreen.tsx    # ディスカッション実行・表示
    │   │   ├── PersonasScreen.tsx      # ペルソナ管理
    │   │   ├── TasksScreen.tsx         # タスク管理
    │   │   ├── RagScreen.tsx           # RAGデータベース管理
    │   │   ├── PatentResearchScreen.tsx # 特許調査
    │   │   ├── SettingsScreen.tsx      # アプリ設定
    │   │   ├── ManualScreen.tsx        # マニュアル表示
    │   │   └── HelperChatWidget.tsx    # AIヘルパーウィジェット
    │   ├── manual/                      # マニュアルページ（Markdown）
    │   │   ├── 00_overview.md           # アプリ概要
    │   │   ├── 01_setup.md              # New Session の使い方
    │   │   ├── 02_personas.md           # Personas の使い方
    │   │   ├── 03_tasks.md              # Tasks の使い方
    │   │   ├── 04_discussion.md         # Discussion の使い方
    │   │   ├── 05_rag.md                # Data Base (RAG) の使い方
    │   │   ├── 06_patent.md             # Patent Research の使い方
    │   │   ├── 07_settings.md           # Settings の使い方
    │   │   └── 08_helper.md             # ヘルパー機能の使い方
    │   ├── lib/
    │   │   ├── api.ts        # バックエンドAPI呼び出し
    │   │   └── db.ts         # ローカルDB（セッション履歴）
    │   └── types/api.ts      # APIの型定義
    ├── src-tauri/            # Rust バックエンド処理
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

LLM接続情報はクライアントへのAPIレスポンスに含まれません。設定画面からも参照・変更できません。

### アプリ設定 (`host/settings.json`) — Settings 画面から変更可能

| 項目 | 説明 |
|---|---|
| **1テーマあたりのターン数** | セッション開始時のデフォルト値 |
| **デフォルト出力フォーマット** | テーマ・ペルソナで未指定の場合に使用 |
| **エージェント発言プロンプトテンプレート** | LLMへ渡すプロンプトの雛形 |
| **要約プロンプトテンプレート** | テーマ要約生成時のプロンプト雛形 |
| **最大履歴トークン数** | 会話履歴の上限トークン数（0=無制限）。超過分は自動圧縮される |
| **直近保持件数** | 圧縮せずに常に保持する直近の発言数 |
| **特許: 企業名列** | 特許調査CSVの企業名列名（デフォルト: `出願人`） |
| **特許: 内容列** | 特許調査CSVの特許内容列名（デフォルト: `請求項`） |
| **特許: 日付列** | 特許調査CSVの日付列名（デフォルト: `出願日`） |

設定は `host/settings.json` に永続化され、サーバー再起動後も維持されます。

Settings 画面の「接続確認」ボタンでサーバー稼働状態と LLM への疎通確認を行えます。

---

## 特許調査ワークフロー

**Patent Research** 画面から CSVファイルを読み込み、企業ごとの特許動向レポートを自動生成する機能です。

1. CSVファイルをアップロード（企業名・特許内容・日付の各列名はSettings画面で設定）
2. 分析対象の企業を選択
3. 「分析開始」で各企業のレポートを順次生成
4. 「全体サマリー生成」で全企業を横断した総括レポートを出力

システムプロンプトと出力フォーマットは画面上でカスタマイズ可能です。各企業について最新10件の特許が分析対象になります。

---

## クライアントアップデート配布

バックエンドサーバーがクライアントのインストーラーを自己配信する仕組みです。

**配置手順:**

1. `host/client_dist/version.json` を作成・更新する
2. インストーラー（`.exe` / `.AppImage` 等）を `host/client_dist/` に配置する

**`version.json` の形式:**
```json
{
  "version": "1.2.3",
  "release_notes": "変更点の説明",
  "windows": {
    "filename": "client_1.2.3_x64-setup.exe",
    "url": "/api/update/download/client_1.2.3_x64-setup.exe"
  },
  "linux": {
    "filename": "client_1.2.3_amd64.AppImage",
    "url": "/api/update/download/client_1.2.3_amd64.AppImage"
  }
}
```

クライアントは起動時に `/api/update/info` を確認し、新バージョンがあればアプリ内バナーでダウンロードを案内します。

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
