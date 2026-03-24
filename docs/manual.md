# マニュアル機能 ガイド

アプリ内マニュアルの仕組みと更新方法について説明します。

---

## 概要

アプリのサイドバーに **Manual** メニューが追加されており、クリックするとアプリ内マニュアルを参照できます。
マニュアルは **Markdownファイル** として管理されており、ファイルを編集するだけで内容を更新できます。

---

## ファイル構成

```
client/src/manual/
├── 00_overview.md     # アプリ概要
├── 01_setup.md        # New Session の使い方
├── 02_personas.md     # Personas の使い方
├── 03_tasks.md        # Tasks の使い方
├── 04_discussion.md   # Discussion の使い方
├── 05_rag.md          # Data Base (RAG) の使い方
├── 06_patent.md       # Patent Research の使い方
├── 07_settings.md     # Settings の使い方
└── 08_helper.md       # ヘルパー機能の使い方
```

ファイル名の先頭の数字がサイドバー上の表示順序を決定します。

---

## マニュアルページの追加方法

1. `client/src/manual/` に新しいMarkdownファイルを作成する
   - ファイル名は `NN_name.md`（NNは2桁の番号）の命名規則に従う
   - 例：`09_admin.md`

2. `client/src/components/ManualScreen.tsx` の `PAGES` 配列に追記する

```typescript
const PAGES = [
  // ... 既存のページ
  { id: 'admin', file: '../manual/09_admin.md', title: 'Admin' },
];
```

3. アプリをリビルドすると新しいページがサイドバーに表示される

---

## マニュアルの更新方法

対応するMarkdownファイルを編集してアプリをリビルドするだけです。

```bash
cd client
npm run tauri dev  # 開発時
# または
npm run tauri build  # 本番ビルド
```

開発モード中は Hot Reload により変更が即時反映されます。

---

## Markdown 記法

マニュアルページでは **GitHub Flavored Markdown (GFM)** を使用できます。

使用可能な要素：
- 見出し（`#` `##` `###`）
- テーブル
- 箇条書き・番号付きリスト
- コードブロック（バッククォート）
- 太字・イタリック
- インラインコード

---

## ヘルパーの知識ファイル

ヘルパーウィジェット（各ページ右下のチャットアシスタント）が参照する知識は別管理です：

```
host/knowledge/
├── persona.md   # Personasページのヘルパー知識
├── task.md      # Tasksページのヘルパー知識
└── setup.md     # New Sessionページのヘルパー知識
```

これらのファイルを編集することで、ヘルパーのアドバイス内容を更新できます。
サーバー再起動なしに変更が反映されます（ファイルは毎リクエストで読み込まれます）。

---

## 実装の詳細

| ファイル | 役割 |
|---|---|
| `client/src/components/ManualScreen.tsx` | マニュアル画面コンポーネント |
| `client/src/manual/*.md` | マニュアルコンテンツ（Markdown） |
| `client/src/App.tsx` | ルート定義・サイドバー項目 |

マニュアルファイルは Vite の `import.meta.glob` でビルド時に静的インポートされます。
マークダウンのレンダリングには `react-markdown` + `remark-gfm` を使用しています。
