# API リファレンス

**Base URL:** `http://<host>:8080`
**形式:** JSON
**文字コード:** UTF-8
**インタラクティブUI:** `http://<host>:8080/docs` (Swagger UI)

---

## 目次

- [共通仕様](#共通仕様)
- [セッション API](#セッション-api--apiSession)
  - [POST /api/session/start](#post-apisessionstart)
  - [POST /api/session/{id}/turn/start](#post-apisessionidturnstart)
  - [GET /api/session/{id}/turn/status/{job_id}](#get-apisessionidturnstatusjob_id)
  - [POST /api/session/{id}/summarize/start](#post-apisessionidsummarizestart)
  - [GET /api/session/{id}/summarize/status/{job_id}](#get-apisessionidsummarizestatusjob_id)
  - [POST /api/session/{id}/full/start](#post-apisessionidfullstart)
  - [GET /api/session/{id}/full/status/{job_id}](#get-apisessionidfullstatusjob_id)
  - [POST /api/session/{id}/end](#post-apisessionidend)
- [設定 API](#設定-api--apisettings)
  - [GET /api/settings/](#get-apisettings)
  - [PUT /api/settings/](#put-apisettings)
  - [GET /api/settings/health](#get-apisettingshealth)
- [特許調査 API](#特許調査-api--apipatent)
  - [POST /api/patent/analyze](#post-apipatentanalyze)
  - [POST /api/patent/summary](#post-apipatentsummary)
- [アップデート API](#アップデート-api--apiupdate)
  - [GET /api/update/info](#get-apiupdateinfo)
  - [GET /api/update/download/{filename}](#get-apiupdatedownloadfilename)
- [RAG API](#rag-api--apirag)
  - [POST /api/rag/init](#post-apiraginit)
  - [POST /api/rag/add](#post-apiragadd)
  - [GET /api/rag/status/{job_id}](#get-apiragstatusjob_id)
- [データ型定義](#データ型定義)
- [エラーレスポンス](#エラーレスポンス)

---

## 共通仕様

### リクエストヘッダー

```
Content-Type: application/json
```

### ジョブポーリングパターン

非同期処理（ターン実行・要約生成）は以下のパターンで扱う。

```
1. POST /{resource}/start  -> { "job_id": "job-xxx" }
2. GET  /{resource}/status/{job_id} を3秒おきにポーリング
3. status が "processing" の間はポーリングを継続
4. status が "completed" or "error" になったら処理完了
```

### ステータス値

| 値 | 意味 |
|----|------|
| `"processing"` | バックグラウンド処理中 |
| `"completed"` | 処理完了・結果あり |
| `"error"` | エラー発生・`error_msg` を参照 |

---

## セッション API `/api/session`

議論セッションのライフサイクルを管理する。セッション状態はサーバーのインメモリに保持され、`/end` で破棄される。

---

### POST /api/session/start

セッションを開始する。ペルソナ・テーマ・タスク・過去履歴を渡してインメモリに状態を作成する。

**リクエストボディ: `SessionStartRequest`**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `themes` | `ThemeConfig[]` | ✅ | 議論するテーマのリスト（順番に処理される） |
| `personas` | `Persona[]` | ✅ | 議論に参加するエージェントのリスト |
| `tasks` | `TaskModel[]` | ✅ | エージェントに割り当てるタスクのリスト |
| `history` | `MessageHistory[]` | - | 過去の会話履歴（再開時に渡す） |
| `turns_per_theme` | int | - | 1テーマあたりの発言ターン数（デフォルト: 5） |
| `common_theme` | string | - | 全テーマ共通の上位テーマ |
| `pre_info` | string | - | 全エージェント共通の事前情報（資料等） |

**ThemeConfig**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `theme` | string | ✅ | テーマのテキスト |
| `persona_ids` | string[] | - | このテーマで発言するペルソナIDのリスト。空配列=全員 |
| `output_format` | string | - | このテーマでの出力フォーマット指定。空=デフォルト |

**Persona**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id` | string | ✅ | ペルソナを一意に識別するID |
| `name` | string | ✅ | エージェント名（発言者として表示される） |
| `role` | string | ✅ | 役割・立場（プロンプトに組み込まれる） |
| `pre_info` | string | - | このペルソナ固有の事前情報 |
| `rag_config` | `RagConfig` | - | RAG設定 |

**RagConfig**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `enabled` | boolean | RAGを有効にするか |
| `tag` | string | 使用するQdrantコレクションのタグ名 |

**TaskModel**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id` | string | ✅ | タスクID |
| `description` | string | ✅ | タスクの説明（各ターンでランダムに割り当てられる） |

**レスポンス: `SessionStartResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `session_id` | string | 以降のAPI呼び出しで使用するセッションID |

**例:**

```bash
curl -X POST http://localhost:8080/api/session/start \
  -H "Content-Type: application/json" \
  -d '{
    "themes": [
      {
        "theme": "AIが社会に与える影響",
        "persona_ids": [],
        "output_format": ""
      }
    ],
    "personas": [
      {
        "id": "p1",
        "name": "楽観主義者",
        "role": "AIの可能性を信じる研究者",
        "pre_info": "",
        "rag_config": { "enabled": false }
      },
      {
        "id": "p2",
        "name": "懐疑論者",
        "role": "AIのリスクを重視する倫理学者",
        "pre_info": ""
      }
    ],
    "tasks": [
      { "id": "t1", "description": "AIが雇用に与える影響を分析する" }
    ],
    "history": [],
    "turns_per_theme": 5,
    "common_theme": "2030年の技術と社会",
    "pre_info": "本議論は研究目的です。"
  }'
```

```json
{ "session_id": "sess-a1b2c3d4e5f6..." }
```

---

### POST /api/session/{id}/turn/start

1ターン分の発言生成をバックグラウンドで開始する。

**パスパラメーター**

| 名前 | 型 | 説明 |
|------|-----|------|
| `id` | string | セッションID |

**レスポンス: `TurnStartResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `job_id` | string | ステータスポーリングに使うジョブID |

**エラー**

| コード | 説明 |
|--------|------|
| 404 | セッションが存在しない |

```bash
curl -X POST http://localhost:8080/api/session/sess-xxx/turn/start
```

```json
{ "job_id": "job-turn-7f8a9b..." }
```

---

### GET /api/session/{id}/turn/status/{job_id}

ターン実行の状態を取得する。`status` が `"processing"` の間は3秒おきにポーリングする。

**パスパラメーター**

| 名前 | 型 | 説明 |
|------|-----|------|
| `id` | string | セッションID |
| `job_id` | string | ジョブID |

**レスポンス: `TurnStatusResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status` | `"processing"` \| `"completed"` \| `"error"` | 処理状態 |
| `agent_name` | string \| null | 発言したエージェント名 (`completed` 時) |
| `message` | string \| null | エージェントの発言内容 (`completed` 時) |
| `theme` | string \| null | 現在のテーマ |
| `is_theme_end` | boolean \| null | このターンでテーマが終了したか |
| `all_themes_done` | boolean \| null | 全テーマが完了したか |
| `error_msg` | string \| null | エラーメッセージ (`error` 時) |

**完了時レスポンス例:**

```json
{
  "status": "completed",
  "agent_name": "楽観主義者",
  "message": "AIは新たな産業を生み出し、雇用の形を変えると考えます。",
  "theme": "AIが社会に与える影響",
  "is_theme_end": false,
  "all_themes_done": false,
  "error_msg": null
}
```

**テーマ終了時 (`is_theme_end: true`):**
テーマが完了した最後のターンで返る。次に `/summarize/start` を呼ぶ。

**全テーマ完了時 (`all_themes_done: true`):**
全テーマのターンが終わった。`/end` でセッションを終了する。

---

### POST /api/session/{id}/summarize/start

現在のテーマの会話履歴をLLMで要約する処理をバックグラウンドで開始する。
`/turn/status` の `is_theme_end: true` を受け取った後に呼ぶ。

**レスポンス: `SummarizeStartResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `job_id` | string | ジョブID |

---

### GET /api/session/{id}/summarize/status/{job_id}

要約生成の状態を取得する。

**レスポンス: `SummarizeStatusResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status` | `"processing"` \| `"completed"` \| `"error"` | 処理状態 |
| `summary_text` | string \| null | 生成された要約テキスト (`completed` 時) |
| `all_themes_done` | boolean \| null | 全テーマが完了したか |
| `error_msg` | string \| null | エラーメッセージ (`error` 時) |

**完了時レスポンス例:**

```json
{
  "status": "completed",
  "summary_text": "楽観主義者はAIによる雇用創出を主張。懐疑論者はホワイトカラー職消滅のリスクを指摘...",
  "all_themes_done": false,
  "error_msg": null
}
```

---

### POST /api/session/{id}/full/start

全テーマを一括でバックグラウンド実行する（ターン→要約→テーマ進行を自動で繰り返す）。
個別ポーリングが不要な場合に使用する。

**レスポンス: `TurnStartResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `job_id` | string | ジョブID |

---

### GET /api/session/{id}/full/status/{job_id}

全テーマ一括実行の状態を取得する。

**レスポンス: `FullSessionStatusResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status` | `"processing"` \| `"completed"` \| `"error"` | 処理状態 |
| `result` | `FullSessionResult` \| null | 全完了時の結果 |
| `error_msg` | string \| null | エラーメッセージ (`error` 時) |

**FullSessionResult**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `theme_summaries` | `ThemeSummary[]` | テーマごとの要約リスト |
| `final_report` | string | 全要約を結合したレポート文字列 |

**ThemeSummary**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `theme` | string | テーマ名 |
| `summary` | string | そのテーマの要約テキスト |

---

### POST /api/session/{id}/end

セッションを終了し、インメモリ状態を破棄する。

**レスポンス: `SessionEndResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status` | `"success"` | 常に `"success"` |

**エラー**

| コード | 説明 |
|--------|------|
| 404 | セッションが存在しない |

---

## 設定 API `/api/settings`

ホストサーバーの公開設定を取得・更新する。LLM接続情報（IP・ポート・モデル等）は `.env` で管理されるためこのAPIには含まれない。

---

### GET /api/settings/

現在の `AppSettings` を返す。

**レスポンス: `AppSettings`**

| フィールド | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| `turns_per_theme` | int | 5 | 1テーマあたりの発言ターン数 |
| `default_output_format` | string | (テンプレート) | エージェント発言の出力フォーマット |
| `agent_prompt_template` | string | (テンプレート) | エージェントへのシステムプロンプトテンプレート |
| `summary_prompt_template` | string | (テンプレート) | テーマ要約プロンプトテンプレート |
| `max_history_tokens` | int | 50000 | 会話履歴の最大トークン数（0=無制限） |
| `recent_history_count` | int | 5 | 圧縮しない直近の会話数 |
| `patent_company_column` | string | `"出願人"` | 特許CSV の企業名列名 |
| `patent_content_column` | string | `"請求項"` | 特許CSV の内容列名 |
| `patent_date_column` | string | `"出願日"` | 特許CSV の日付列名 |

**プロンプトテンプレートで使用できる変数:**

`agent_prompt_template` 内で使用できる変数:

| 変数 | 内容 |
|------|------|
| `{role}` | ペルソナの役割 |
| `{name}` | ペルソナの名前 |
| `{task}` | 割り当てタスク |
| `{query}` | 今回のテーマ（共通テーマ + テーマを結合したもの） |
| `{pre_info_section}` | 事前情報（セッション共通 + ペルソナ固有を結合） |
| `{rag_section}` | RAG検索結果 |
| `{history}` | 会話履歴（圧縮処理済み） |
| `{previous_summaries}` | 過去テーマの要約一覧 |
| `{output_format}` | 出力フォーマット指定 |

`summary_prompt_template` 内で使用できる変数:

| 変数 | 内容 |
|------|------|
| `{theme}` | 現在のテーマ |
| `{history}` | 会話履歴テキスト |
| `{output_format}` | 出力フォーマット指定 |

---

### PUT /api/settings/

`AppSettings` を上書きして `settings.json` に永続化する。
指定しないフィールドは現在値のまま（全フィールドを送る必要がある）。

**リクエストボディ:** `AppSettings`（上記と同じスキーマ）

**レスポンス:** 保存後の `AppSettings`

---

### GET /api/settings/health

サーバー自身の稼働確認と、LLMへの疎通確認を行う。

**レスポンス: `HealthResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `server` | `"ok"` | サーバーが稼働していれば常に `"ok"` |
| `llm` | `"ok"` \| `"error"` | LLMへの疎通結果 |
| `llm_error` | string \| null | LLM接続エラーの詳細 |

**LLM疎通確認の仕組み:**
`http://{LLM_IP}:{LLM_PORT}/v1/models` に GET リクエストを送信（タイムアウト5秒）。

```json
{
  "server": "ok",
  "llm": "ok",
  "llm_error": null
}
```

---

## 特許調査 API `/api/patent`

企業ごとの特許リストをLLMで分析し、レポートを生成する。
クライアント側でCSVのパースと最新10件への絞り込みを行った上でこのAPIを呼ぶ。

---

### POST /api/patent/analyze

1企業分の特許リストを分析してレポートを返す（同期処理）。

**リクエストボディ: `PatentAnalyzeRequest`**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `company` | string | ✅ | 企業名 |
| `patents` | `PatentItem[]` | ✅ | 特許リスト（クライアント側で最新10件に絞り込み済み） |
| `system_prompt` | string | ✅ | 分析用システムプロンプト。空文字でデフォルトを使用 |
| `output_format` | string | ✅ | 出力フォーマット指定。空文字でデフォルトを使用 |

**PatentItem**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `content` | string | 特許のタイトル・概要等のテキスト |
| `date` | string | 出願日等の日付文字列（表示目的） |

**レスポンス: `PatentAnalyzeResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `company` | string | リクエストの企業名をそのまま返す |
| `report` | string | LLMが生成した分析レポート（Markdown） |

**例:**

```bash
curl -X POST http://localhost:8080/api/patent/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "company": "サンプル技術株式会社",
    "patents": [
      { "content": "深層学習を用いた画像認識システム", "date": "2024-03-15" },
      { "content": "自然言語処理による文書分類装置", "date": "2024-02-10" }
    ],
    "system_prompt": "",
    "output_format": ""
  }'
```

```json
{
  "company": "サンプル技術株式会社",
  "report": "## サンプル技術株式会社 分析レポート\n\n### 主な技術領域\n- 深層学習・画像認識\n..."
}
```

---

### POST /api/patent/summary

全企業のレポートを読んで総括レポートを生成する（同期処理）。
全企業の `/analyze` が完了した後に呼ぶ。

**リクエストボディ: `PatentSummaryRequest`**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `company_reports` | `PatentAnalyzeResponse[]` | ✅ | 全企業の分析レポートリスト |
| `system_prompt` | string | ✅ | 総括用システムプロンプト。空文字でデフォルトを使用 |

**レスポンス: `PatentSummaryResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `summary` | string | LLMが生成した総括レポート（Markdown） |

---

## アップデート API `/api/update`

クライアントのバージョン確認とインストーラー配布を行う。
`host/client_dist/version.json` の内容を返す。ファイルが存在しない場合は `has_update: false` を返す。

---

### GET /api/update/info

最新バージョン情報とダウンロードURLを返す。

**クエリパラメーター**

| 名前 | 型 | デフォルト | 説明 |
|------|-----|-----------|------|
| `current` | string | `"0.0.0"` | クライアントの現在バージョン |
| `platform` | string | `"windows"` | プラットフォーム: `"windows"` or `"linux"` |

**バージョン比較ロジック:**
`latest_version > current` の場合のみ `has_update: true` を返す。
比較はセマンティックバージョニング（`X.Y.Z`）の数値比較による。

**レスポンス: `UpdateInfoResponse`**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `latest_version` | string | `version.json` に記載の最新バージョン |
| `current_version` | string | リクエストで渡した `current` の値をそのまま返す |
| `has_update` | boolean | アップデートが利用可能かどうか |
| `release_notes` | string | リリースノート |
| `download_url` | string | インストーラーの相対パス（例: `/api/update/download/client_1.2.0_x64-setup.exe`） |
| `filename` | string | インストーラーのファイル名 |

**例:**

```bash
curl "http://localhost:8080/api/update/info?current=0.1.0&platform=windows"
```

```json
{
  "latest_version": "1.2.0",
  "current_version": "0.1.0",
  "has_update": true,
  "release_notes": "特許調査機能を追加・パフォーマンス改善",
  "download_url": "/api/update/download/client_1.2.0_x64-setup.exe",
  "filename": "client_1.2.0_x64-setup.exe"
}
```

**アップデートなしの場合:**

```json
{
  "latest_version": "1.2.0",
  "current_version": "1.2.0",
  "has_update": false,
  "release_notes": "",
  "download_url": "",
  "filename": ""
}
```

---

### GET /api/update/download/{filename}

`host/client_dist/` ディレクトリ内のファイルをダウンロードする。

**パスパラメーター**

| 名前 | 型 | 説明 |
|------|-----|------|
| `filename` | string | ダウンロードするファイル名 |

**セキュリティ:**
ファイル名に `/`、`\`、`..` を含む場合は 400 エラーを返す（パストラバーサル防止）。

**レスポンス:** バイナリファイル (`application/octet-stream`)

**エラー**

| コード | 説明 |
|--------|------|
| 400 | ファイル名にパス区切り文字が含まれている |
| 404 | ファイルが存在しない |

---

## RAG API `/api/rag`

Qdrant ベクトルDBへのデータ登録を管理する。
タグ（コレクション名）単位で知識ベースを分離できる。

> **現在の実装:** モック実装のため、Qdrant への実際の書き込みは行われない。

---

### POST /api/rag/init

指定タグのコレクションを初期化する（既存データを全削除して再作成）。

**リクエストボディ**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `tag` | string | ✅ | 初期化するコレクションのタグ名 |

**レスポンス**

```json
{ "status": "success" }
```

---

### POST /api/rag/add

テキストをチャンキング・エンベディングしてQdrantに追加する（非同期処理）。

**リクエストボディ**

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `tag` | string | ✅ | 追加先コレクションのタグ名 |
| `text` | string | ✅ | ベクトル化するテキスト |

**レスポンス**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `job_id` | string | ステータスポーリング用のジョブID |

---

### GET /api/rag/status/{job_id}

RAGデータ追加ジョブの状態を取得する。

**レスポンス**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `status` | `"processing"` \| `"completed"` \| `"error"` | 処理状態 |
| `error_msg` | string \| null | エラーメッセージ |

---

## データ型定義

### MessageHistory

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | string | 発言を一意に識別するID（UUIDなど） |
| `theme` | string | この発言が属するテーマ |
| `agent_name` | string | 発言したエージェント名 |
| `content` | string | 発言内容 |
| `turn_order` | int | テーマ内での発言順（0始まり） |

> **Note:** `agent_name` が `"[会話要約]"` の場合、それは会話履歴圧縮によって生成された要約エントリを表す。

---

## エラーレスポンス

### 標準エラー形式

```json
{ "detail": "エラーメッセージ" }
```

### 主なHTTPエラーコード

| コード | 説明 |
|--------|------|
| 400 | リクエストが不正（パラメーター不足・不正な値） |
| 404 | 対象リソースが見つからない（セッション・ジョブ・ファイル） |
| 422 | リクエストボディのバリデーションエラー（Pydantic） |
| 500 | サーバー内部エラー |

### 422 バリデーションエラーの例

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "themes"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### ジョブエラーの例

`/turn/status` や `/summarize/status` で `status: "error"` が返る場合:

```json
{
  "status": "error",
  "agent_name": null,
  "message": null,
  "theme": null,
  "is_theme_end": null,
  "all_themes_done": null,
  "error_msg": "LLM connection refused: http://127.0.0.1:11434"
}
```
