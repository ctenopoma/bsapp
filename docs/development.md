# 開発ガイド

## 目次
1. [プロジェクト構成](#1-プロジェクト構成)
2. [開発環境のセットアップ](#2-開発環境のセットアップ)
3. [Host (FastAPI) の開発フロー](#3-host-fastapi-の開発フロー)
4. [Client (Tauri/React) の開発フロー](#4-client-taurireact-の開発フロー)
5. [ワークフローの拡張方法](#5-ワークフローの拡張方法)
6. [デバッグ手順](#6-デバッグ手順)

---

## 1. プロジェクト構成

```
bsapp/
├── host/                        # FastAPI バックエンド
│   ├── src/
│   │   ├── main.py              # FastAPI エントリポイント
│   │   ├── models.py            # Pydantic データモデル
│   │   ├── app_settings.py      # 設定管理 (settings.json / .env)
│   │   ├── session_manager.py   # セッション状態管理 (インメモリ)
│   │   ├── agent_runner.py      # LLM呼び出し
│   │   ├── rag_manager.py       # Qdrant RAG管理
│   │   ├── api/
│   │   │   ├── session.py       # 議論セッション API
│   │   │   ├── settings.py      # 設定 API
│   │   │   ├── patent.py        # 特許調査 API
│   │   │   ├── update.py        # クライアント配布 API
│   │   │   └── rag.py           # RAG API
│   │   └── workflow/
│   │       ├── turn_runner.py       # 1テーマ実行ループ ★カスタマイズ
│   │       ├── persona_selector.py  # 発言者選択 ★カスタマイズ
│   │       ├── input_builder.py     # エージェント入力構築 ★カスタマイズ
│   │       ├── history_compressor.py # 会話履歴圧縮 ★カスタマイズ
│   │       ├── summarizer.py        # テーマ要約 ★カスタマイズ
│   │       ├── prompt_builder.py    # デフォルトプロンプト ★カスタマイズ
│   │       └── patent/
│   │           ├── analyzer.py      # 企業別特許分析 ★カスタマイズ
│   │           ├── summarizer.py    # 総括レポート生成 ★カスタマイズ
│   │           └── prompt_builder.py # 特許用プロンプト ★カスタマイズ
│   ├── client_dist/             # 配布用クライアントファイル置き場
│   │   ├── version.json         # 最新バージョン情報 (開発者が更新)
│   │   └── *.exe / *.AppImage   # ビルド済みインストーラー
│   ├── settings.json            # 実行時設定 (API経由で保存)
│   ├── .env                     # LLM接続情報 (Gitignore対象)
│   ├── requirements.txt
│   └── debug_test.py            # 議論ワークフロー デバッグスクリプト
│   └── debug_report.py          # 特許調査ワークフロー デバッグスクリプト
│
├── client/                      # Tauri デスクトップアプリ
│   ├── src/
│   │   ├── App.tsx              # ルーティング + 起動時アップデートチェック
│   │   ├── types/api.ts         # TypeScript 型定義
│   │   ├── lib/
│   │   │   ├── api.ts           # FastAPI クライアント
│   │   │   └── db.ts            # SQLite CRUD
│   │   └── components/
│   │       ├── SetupScreen.tsx      # 新規セッション設定
│   │       ├── DiscussionScreen.tsx # 議論進行・表示
│   │       ├── PersonasScreen.tsx   # ペルソナ管理
│   │       ├── TasksScreen.tsx      # タスク管理
│   │       ├── RagScreen.tsx        # RAG知識ベース管理
│   │       ├── PatentResearchScreen.tsx # 特許調査
│   │       └── SettingsScreen.tsx   # アプリ設定
│   └── src-tauri/
│       ├── tauri.conf.json      # Tauri設定・バージョン管理
│       └── Cargo.toml
│
├── docs/                        # このドキュメント群
├── Dockerfile.client            # クライアントビルド用Docker環境
├── build-client.sh              # ビルドスクリプト
└── docker-compose.yml           # Qdrant用
```

---

## 2. 開発環境のセットアップ

### 前提条件

| ツール | 推奨バージョン | 用途 |
|--------|--------------|------|
| Python | 3.11 以上 | Host 開発 |
| Node.js | 20 LTS | Client 開発 |
| Rust | stable | Tauri ビルド |
| Docker | 最新 | Qdrant (RAG使用時) |

### Host セットアップ

```bash
cd host

# 仮想環境作成・有効化
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 依存パッケージインストール
pip install -r requirements.txt

# .env を作成 (テンプレート)
cat > .env << 'EOF'
LLM_IP=127.0.0.1
LLM_PORT=11434
LLM_MODEL=llama3
LLM_API_KEY=dummy
LLM_TEMPERATURE=0.7
EOF

# 開発サーバー起動
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

> **Note:** `settings.json` はサーバー起動時に自動生成されます。

### Client セットアップ

```bash
cd client

# 依存パッケージインストール
npm install

# Tauri 開発モード起動 (Hot Reload あり)
npm run tauri dev
```

> Tauri 開発モードは `http://localhost:1420` で Vite dev server を起動し、
> Webview 内でロードします。

### Qdrant (RAG機能使用時のみ)

```bash
# リポジトリルートで
docker compose up -d
# → http://localhost:6333 で起動
```

---

## 3. Host (FastAPI) の開発フロー

### API エンドポイントの追加

1. `src/models.py` にリクエスト・レスポンスの Pydantic モデルを追加
2. `src/api/` に新しいルーターファイルを作成
3. `src/main.py` にルーターを登録

```python
# src/main.py への追加例
from src.api import my_new_feature
app.include_router(my_new_feature.router, prefix="/api/my_feature", tags=["MyFeature"])
```

### 設定項目の追加

`src/models.py` の `AppSettings` クラスにフィールドを追加し、
`client/src/types/api.ts` の `AppSettings` インターフェースにも対応フィールドを追加します。

```python
# src/models.py
class AppSettings(BaseModel):
    my_new_setting: str = "default_value"  # ← 追加
```

```typescript
// client/src/types/api.ts
export interface AppSettings {
  my_new_setting: string;  // ← 追加
}
```

Settings画面にUIを追加すれば、`/api/settings/` 経由で自動的に `settings.json` に保存されます。

### 設定値の読み取り (Host内)

```python
from ..app_settings import get_settings

settings = get_settings()
value = settings.my_new_setting
```

### ワークフローの設定優先順位

```
.env (LLM接続情報のみ)
  ↓ 起動時に読み込み
settings.json (AppSettings)
  ↓ API経由で更新可能
デフォルト値 (prompt_builder.py / models.py)
```

---

## 4. Client (Tauri/React) の開発フロー

### 画面の追加

1. `client/src/components/` に新しいコンポーネントを作成
2. `client/src/App.tsx` にルートとナビゲーション項目を追加

```tsx
// App.tsx への追加例
import MyNewScreen from './components/MyNewScreen';

// navItems に追加
{ path: "/my_screen", label: "My Screen", icon: <IconName size={20} /> }

// Routes に追加
<Route path="/my_screen" element={<MyNewScreen />} />
```

### API 呼び出しの追加

```typescript
// client/src/lib/api.ts に追加
export function apiMyEndpoint(req: MyRequest): Promise<MyResponse> {
  return request('/api/my_feature/endpoint', { method: 'POST', body: JSON.stringify(req) });
}
```

### DB テーブルの追加

`client/src/lib/db.ts` の `initDb()` 関数内に `CREATE TABLE IF NOT EXISTS` を追加します。
テーブル追加は自動的にマイグレーションされます（既存テーブルはそのまま）。

```typescript
// db.ts の initDb() 内
await db.execute(`
  CREATE TABLE IF NOT EXISTS my_table (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )
`);
```

### BASE_URL の変更

`client/src/lib/api.ts` の `BASE_URL` は環境変数 `VITE_API_URL` で上書きできます。

```bash
# .env.local (client/ 直下に作成)
VITE_API_URL=http://192.168.1.100:8080
```

---

## 5. ワークフローの拡張方法

`★カスタマイズ` とコメントされたファイルを編集することで、AIの挙動を変更できます。

### 発言者の選択ロジックを変える

`workflow/persona_selector.py` の `PERSONA_SELECTION_STRATEGY` 定数を変更します。

```python
PERSONA_SELECTION_STRATEGY = "round_robin"  # "random" / "round_robin" / "role_first"
```

新しいストラテジーを追加する場合は `_STRATEGY_MAP` に関数を登録します。
詳細は `AGENT_WORKFLOW.md` を参照してください。

### エージェントへ渡す情報を変える

`workflow/input_builder.py` の `TASK_SELECTION_STRATEGY` 定数でタスク割り当て方法を変更できます。

```python
TASK_SELECTION_STRATEGY = "role_match"  # "random" / "round_robin" / "role_match"
```

会話履歴の渡し方・RAG検索クエリなど他の変更は `build_agent_input()` を直接編集します。

### 会話履歴の圧縮設定

`workflow/history_compressor.py` で、トークン超過時の圧縮挙動を変更できます。
圧縮の上限・直近保持件数は Settings 画面 (→ `AppSettings`) から設定できます。

| 設定 | デフォルト | 説明 |
|------|-----------|------|
| `max_history_tokens` | 50000 | これを超えると古い履歴を圧縮 (0=無制限) |
| `recent_history_count` | 5 | 圧縮せず保持する直近の会話数 |

### RAG種別を追加する

新しい RAG バックエンドをペルソナに割り当て可能な「種別」として追加できます。

#### ステップ 1: 種別を Settings に登録する

`host/settings.json` を直接編集します。

```json
{
  "available_rag_types": [
    { "id": "qdrant", "name": "Qdrant (ベクトル検索)", "description": "Qdrantを使ったベクトル類似検索" },
    { "id": "my_rag",  "name": "My RAG",               "description": "独自RAGバックエンド" }
  ]
}
```

> **注意:** `id` はシステム内部で使用されます。一度ペルソナに割り当てた後に変更すると、
> そのペルソナの RAG 設定が実行時に無視されます（エラーにはなりません）。

#### ステップ 2: Host に処理を実装する

`host/src/workflow/input_builder.py` の RAG 分岐に `elif` を追加します。

```python
# input_builder.py の RAG取得セクション

if rag_type == "qdrant":
    rag_context = rag_manager.search_context(
        tag=persona.rag_config.tag,
        query=session.current_theme,
    )
elif rag_type == "my_rag":
    # 独自 RAG の検索ロジックをここに実装
    rag_context = my_rag_search(tag=persona.rag_config.tag, query=session.current_theme)
```

それ以外の変更は不要です。Client 側は Settings に登録された種別を
自動的にドロップダウンに表示します。

#### 実行時の種別不一致について

ペルソナに設定された `rag_type` が Host の `available_rag_types` に存在しない場合、
または `input_builder.py` に対応する処理がない場合、RAG はスキップされます
（rag_context が空になるだけで、ディスカッションは継続します）。

### 特許調査ワークフローを変える

`workflow/patent/analyzer.py` と `workflow/patent/summarizer.py` を編集します。
プロンプトは `workflow/patent/prompt_builder.py` で管理されています。

---

## 6. デバッグ手順

### Host ワークフローのデバッグ

```bash
cd host
python debug_test.py       # 議論ワークフロー
python debug_report.py     # 特許調査ワークフロー
```

各ファイルの `USE_REAL_LLM = False` でモックLLMを使い、
LLMサーバーなしでブレイクポイントを使ったステップ実行が可能です。

```python
# LLMを使う場合は True に変更
USE_REAL_LLM = True
```

### API の動作確認

Host 起動後、Swagger UI でインタラクティブにテストできます:
```
http://localhost:8080/docs
```

### Client のデバッグ

```bash
cd client
npm run tauri dev   # DevTools が使える (右クリック → 検証)
```
