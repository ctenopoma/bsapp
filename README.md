# BSapp: AI 多重ペルソナ ディスカッションアプリ 💬🤖

**BSapp** は、完全にローカルで動作するパーソナライズ可能なAIディスカッションアプリケーションです。  
クラウドサービスに依存せず、自分自身のマシン上で高速・セキュアに**複数のAIエージェント**を対話させ、ディスカッションを生成・管理することができます。

このプロジェクトは、バックエンドとフロントエンドを含む**モノレポ（Monorepo）**として構成されています。

- **[`host/`](./host/)**: **FastAPI** と **LangChain** で構築されたバックエンド。複数AIエージェントの会話管理、**Qdrant** を用いた RAG（検索拡張生成）、およびローカルLLM（Ollama等）との通信を行います。
- **[`client/`](./client/)**: **Tauri + React + TypeScript** で構築されたデスクトップ向けフロントエンド。軽快でネイティブアプリと同等の操作感を提供します。

---

## 🌟 主な特徴

- ✨ **完全ローカル動作 (Privacy First)**: 全てのデータはあなたのマシン内に留まり、外部に送信されません。（`/v1` のOpenAI互換APIエンドポイント経由で、Ollama等のローカルLLMをフルサポート）
- 🎭 **ダイナミック・マルチペルソナ・エンジン**: 様々な性格や役割（ペルソナ）を設定可能。バックエンドの自動モデレーションにより、AIエージェント同士が自律的に連続した議論を行います。
- 🧠 **RAGによる文脈理解**: ディスカッションの文脈はローカルベクトルデータベース (Qdrant) に保存・検索され、過去のテーマや議論を賢く参照します。
- ⚡ **ネイティブ・パフォーマンス**: Tauri（Rust）をベースに構築しており、軽量かつ非常に高速なデスクトップUIを実現しました。

---

## 📁 リポジトリ構成

```text
bsapp/
├── host/        # FastAPI バックエンドサーバー (Python)
│   ├── src/     # AIエージェントロジック、REST API、RAG管理
│   ├── .env     # LLMやDBの接続設定ファイル
│   └── README.md
└── client/      # Tauri デスクトップアプリ (Node / Rust)
    ├── src/     # React フロントエンド (Vite)
    ├── src-tauri/# Rust バックエンド処理
    └── README.md
```

---

## 🚀 始め方 / 起動手順

BSappを使用するには、**バックエンド (`host`)** と **フロントエンド (`client`)** の両方を起動する必要があります。

### 1. 必要条件 (Prerequisites)

以下がお使いの環境にインストールされていることを確認してください。

- [uv](https://docs.astral.sh/uv/) (高速なPythonパッケージマネージャ)
- [Node.js](https://nodejs.org/) & [npm](https://www.npmjs.com/) (または pnpm/yarn)
- [Rust](https://www.rust-lang.org/tools/install) (Tauriのビルドに必須)
- [Docker](https://www.docker.com/) (Qdrantの起動に推奨)
- ローカルLLM環境: [Ollama](https://ollama.com/) などをインストールし、言語モデル（例: `llama3`）および埋め込みモデル（例: `nomic-embed-text`）を取得しておいてください。

---

### 2. バックエンド (`host`) の起動

バックエンドは、QdrantベクトルデータベースとローカルLLMと連携して動作します。

**A. Qdrantの起動 (Docker経由)**
```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant
```

**B. FastAPIサーバーの起動**
```bash
cd host
# 依存パッケージの同期・インストール
uv sync
# サーバーの起動
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```
> 💡 LLMのIP・ポート、モデル名などの詳しい構成方法（`.env` の設定）については、[**`host/README.md`**](./host/README.md) をご覧ください。

---

### 3. フロントエンド (`client`) の起動

新しく別のターミナルウィンドウを開き、`client` ディレクトリへ移動して、Tauriアプリを開発モードで起動します。

```bash
cd client
npm install
npm run tauri dev
```

初回実行時はRustコードのコンパイルが走ります。完了するとネイティブのアプリケーションウィンドウが立ち上がり、すぐに使い始めることができます。

---

## 📝 設定について

推論エンジンや埋め込みモデルの詳しい設定変更、各LLM・Rerank APIの個別ポート・IP変更などはすべて `host/.env` で管理されています。
初期設定では、Ollamaが `http://127.0.0.1:11434` 、Qdrantが `http://localhost:6333` で動作している前提となっています。
