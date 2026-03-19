# Company environment DB debug procedure

Windows の会社環境で `start-all.bat` 実行時に、`Waiting for application startup` の直後に落ちる場合の調査手順。

## 使い方

リポジトリのルートで次を実行します。

```bat
debug-company-db.bat
```

実行後、ルートに `debug-company-db-result.txt` が生成されます。

## 何を確認するか

このスクリプトは以下を順番に確認します。

1. `host/.env` の `DATABASE_URL`
2. PostgreSQL サービス一覧
3. 5432番ポートの LISTEN 状態
4. `psql` が存在するか
5. `postgres` ユーザーで DB 一覧を取得できるか
6. `postgres` ユーザーでロール一覧を取得できるか
7. `bsapp` ユーザーで `bsapp` DB に接続できるか
8. backend 単体起動時のログ

## 想定する正常状態

- `host/.env` に `DATABASE_URL=postgresql+asyncpg://bsapp:bsapp@localhost:5432/bsapp?ssl=disable`
- 5432 を PostgreSQL が listen している
- `bsapp` ロールが存在する
- `bsapp` データベースが存在する
- `psql -h localhost -p 5432 -U bsapp -d bsapp` が成功する
- backend 起動時に `PostgreSQL tables ready` が出る

## よくある原因

- PostgreSQL 18 は起動しているが `bsapp` ロール/DB が未作成
- 5432 を別プロセスが使用している
- `host/.env` の `DATABASE_URL` が実環境と不一致
- PostgreSQL の認証設定やローカル接続制限
- 会社PC固有のセキュリティ製品による干渉

## 次に見るべきもの

- `debug-company-db-result.txt`
- PostgreSQL サーバーログ
- backend 起動時の traceback