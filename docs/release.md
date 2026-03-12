# 公開・リリース手順

## 目次
1. [バージョン管理の方針](#1-バージョン管理の方針)
2. [Host のリリース手順](#2-host-のリリース手順)
3. [Client のビルドと配布手順](#3-client-のビルドと配布手順)
4. [Dockerを使ったビルド (Ubuntu)](#4-dockerを使ったビルド-ubuntu)
5. [アップデート配信の設定](#5-アップデート配信の設定)
6. [初回デプロイ手順](#6-初回デプロイ手順)
7. [トラブルシューティング](#7-トラブルシューティング)

---

## 1. バージョン管理の方針

バージョン番号は [セマンティックバージョニング](https://semver.org/lang/ja/) に従う。

```
X.Y.Z
|  |  +-- Z: バグ修正・軽微な変更
|  +---- Y: 後方互換な機能追加
+------ X: 後方互換性のない変更
```

**バージョン管理ファイル:**

| ファイル | 役割 | 更新タイミング |
|---------|------|--------------|
| `client/src-tauri/tauri.conf.json` | Client の正式バージョン | リリースごと |
| `host/client_dist/version.json` | 配布バージョン情報 | ビルド後 (自動更新) |
| `host/src/main.py` の `version=` | Host API バージョン | 必要に応じて |

---

## 2. Host のリリース手順

### 2.1 設定ファイルを準備する

```bash
cd host

# .env が存在しない場合は作成
cp .env.example .env    # または手動で作成
vi .env
```

`.env` の内容:
```env
LLM_IP=127.0.0.1
LLM_PORT=11434
LLM_MODEL=llama3
LLM_API_KEY=your_api_key
LLM_TEMPERATURE=0.7
```

### 2.2 依存パッケージをインストールして起動する

```bash
cd host
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# 本番起動 (ポート・ワーカー数はサーバー環境に合わせて調整)
uvicorn src.main:app --host 0.0.0.0 --port 8080 --workers 2
```

### 2.3 systemd でサービス化する (本番環境推奨)

```ini
# /etc/systemd/system/bsapp-host.service
[Unit]
Description=BSapp Host Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/bsapp/host
ExecStart=/home/ubuntu/bsapp/host/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable bsapp-host
sudo systemctl start bsapp-host
sudo systemctl status bsapp-host
```

### 2.4 Qdrant を起動する (RAG機能使用時のみ)

```bash
cd /home/ubuntu/bsapp
docker compose up -d
```

---

## 3. Client のビルドと配布手順

### 3.1 バージョンを更新する

`client/src-tauri/tauri.conf.json` の `version` フィールドを更新する:

```json
{
  "version": "1.2.0"
}
```

### 3.2 Windows でビルドする (推奨)

Windows 環境でのネイティブビルドが最も確実。

```powershell
cd client
npm install
npm run tauri build
```

ビルド成果物の場所:
```
client/src-tauri/target/release/bundle/
├── nsis/
│   └── client_1.2.0_x64-setup.exe   ← Windows インストーラー
└── msi/
    └── client_1.2.0_x64_en-US.msi
```

### 3.3 成果物を Host サーバーへコピーする

```bash
# Windows から scp でコピー
scp client/src-tauri/target/release/bundle/nsis/client_1.2.0_x64-setup.exe \
    ubuntu@your-server:/home/ubuntu/bsapp/host/client_dist/

# または rsync
rsync -av client/src-tauri/target/release/bundle/nsis/*.exe \
    ubuntu@your-server:/home/ubuntu/bsapp/host/client_dist/
```

### 3.4 version.json を更新する

`host/client_dist/version.json` を編集する:

```json
{
  "version": "1.2.0",
  "release_notes": "特許調査機能を追加・パフォーマンス改善",
  "windows": {
    "filename": "client_1.2.0_x64-setup.exe",
    "url": "/api/update/download/client_1.2.0_x64-setup.exe"
  },
  "linux": {
    "filename": "client_1.2.0_amd64.AppImage",
    "url": "/api/update/download/client_1.2.0_amd64.AppImage"
  }
}
```

Host サーバーへの反映は即時（再起動不要）。

---

## 4. Dockerを使ったビルド (Ubuntu)

Ubuntu サーバー上で Docker を使って Client をビルドする。

### 4.1 ビルドイメージを作成する (初回・依存パッケージ変更時)

```bash
cd /home/ubuntu/bsapp
docker build -f Dockerfile.client -t bsapp-client-builder .
```

> **注意:** イメージビルドには Rust のコンパイルが含まれるため、
> 初回は 20〜30分かかることがあります。

### 4.2 Linux 向けにビルドする

```bash
./build-client.sh linux
```

成果物:
```
client/src-tauri/target/release/bundle/
├── deb/   client_X.Y.Z_amd64.deb
└── appimage/  client_X.Y.Z_amd64.AppImage
```

### 4.3 Windows 向けにビルドする (クロスコンパイル)

```bash
./build-client.sh windows
```

> **制限事項:**
> - MinGW (GNU toolchain) を使ったクロスコンパイルのため、
>   Windows MSVC ネイティブビルドとは動作が異なる場合があります。
> - WebView2 の動作確認は Windows 環境で行うことを推奨します。
> - 本番リリース用インストーラーは Windows でのネイティブビルドを推奨します。

### 4.4 ビルド後の自動処理

`build-client.sh` は以下を自動で行う:
1. Docker コンテナ内でビルド実行
2. 成果物を `host/client_dist/` へコピー
3. `version.json` の `version` フィールドを `tauri.conf.json` の値で自動更新

---

## 5. アップデート配信の設定

### 5.1 アップデート配信の仕組み

```
Client 起動
  -> GET /api/update/info?current=現在バージョン
  <- { has_update: true, latest_version, download_url }
  -> バナー表示 -> ユーザーがダウンロードボタンをクリック
  -> ブラウザで GET /api/update/download/filename を開く
  -> インストーラーをダウンロード -> ユーザーが手動でインストール
```

### 5.2 ファイルの配置場所

```
host/client_dist/
├── version.json                     # バージョン情報 (必須)
├── client_1.2.0_x64-setup.exe       # Windows インストーラー
└── client_1.2.0_amd64.AppImage      # Linux AppImage
```

### 5.3 古いバージョンのファイルを削除する

ディスク節約のため、不要になったインストーラーファイルは手動で削除する:

```bash
# 例: 1.0.0 と 1.1.0 のファイルを削除
rm host/client_dist/client_1.0.0_x64-setup.exe
rm host/client_dist/client_1.1.0_x64-setup.exe
```

---

## 6. 初回デプロイ手順

Ubuntu サーバーへの初回セットアップ全体の流れ。

### ステップ 1: サーバー準備

```bash
# Ubuntu 22.04 推奨
sudo apt update && sudo apt upgrade -y

# Docker インストール
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Git
sudo apt install -y git
```

### ステップ 2: リポジトリのクローン

```bash
cd /home/ubuntu
git clone <repository-url> bsapp
cd bsapp
```

### ステップ 3: Host の設定と起動

```bash
cd host

# 仮想環境と依存パッケージ
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env   # なければ手動作成
vi .env                # LLM接続情報を入力

# 動作確認
uvicorn src.main:app --host 0.0.0.0 --port 8080
# http://your-server:8080/docs でSwagger UIが開けばOK

# systemd サービス化 (セクション2.3参照)
```

### ステップ 4: Qdrant の起動 (RAG使用時)

```bash
cd /home/ubuntu/bsapp
docker compose up -d
# http://your-server:6333/dashboard で確認
```

### ステップ 5: client_dist の準備

```bash
mkdir -p host/client_dist

# 初期 version.json を作成 (バージョンはビルド後に更新)
cat > host/client_dist/version.json << 'EOF'
{
  "version": "0.1.0",
  "release_notes": "初回リリース",
  "windows": {
    "filename": "client_0.1.0_x64-setup.exe",
    "url": "/api/update/download/client_0.1.0_x64-setup.exe"
  }
}
EOF
```

### ステップ 6: Client のビルドと初回配布

Windows でビルドしてサーバーへコピー (セクション3.2〜3.3 参照)。

### ステップ 7: ファイアウォール設定

```bash
# Client からの HTTP アクセスを許可
sudo ufw allow 8080/tcp
sudo ufw allow 6333/tcp   # Qdrant (必要な場合)
sudo ufw enable
```

---

## 7. トラブルシューティング

### Host が起動しない

```bash
# ログ確認
journalctl -u bsapp-host -n 50

# .env のパスを確認 (host/ ディレクトリから起動すること)
cd /home/ubuntu/bsapp/host
uvicorn src.main:app --host 0.0.0.0 --port 8080
```

### Client がホストに接続できない

- `VITE_API_URL` または `client/src/lib/api.ts` の `BASE_URL` を確認する
- ファイアウォールで 8080 番ポートが開いているか確認する
- Settings 画面の「接続確認」ボタンで診断する

### アップデートバナーが表示されない

- `host/client_dist/version.json` が存在するか確認する
- `version.json` の `version` が `tauri.conf.json` の値より大きいか確認する
- `/api/update/info?current=0.0.0` に直接アクセスして動作確認する

### Docker ビルドが失敗する

```bash
# ビルドログを詳細表示
docker build --no-cache -f Dockerfile.client -t bsapp-client-builder . 2>&1 | tee build.log

# コンテナ内に入って手動で確認
docker run --rm -it \
  -v $(pwd)/client:/build/client \
  bsapp-client-builder bash
```

### クロスコンパイルで Windows バイナリが動かない

MinGW クロスコンパイルで生成された `.exe` が Windows で動作しない場合、
Windows 環境でのネイティブビルドに切り替える (セクション3.2参照)。
