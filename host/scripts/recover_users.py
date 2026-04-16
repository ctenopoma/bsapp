"""
ユーザー復旧スクリプト (データ付き対話版)
==========================================
windows_username が未設定のユーザーについて、そのユーザーが持つ
  - セッション履歴 (sessions.title, sessions.created_at)
  - ペルソナ (personas.name)
  - タスク (tasks.description)
  - セッションプリセット (session_presets.name)
  - ペルソナプリセット (persona_presets.name)
  - タスクプリセット (task_presets.name)
  - 特許セッション (patent_sessions.title)
  - 最終ログイン日時・IPアドレス

を一覧表示し、誰のデータか判断できるよう支援する。
確認後、Windows ユーザー名を割り当てて復旧する。

使い方:
  cd host
  python scripts/recover_users.py [--dry-run]

オプション:
  --dry-run   DBを変更せずに一覧表示のみ行う

前提:
  host/.env が設定済みで DB に接続できること。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from src.database import AsyncSessionLocal
from src.db_models import (
    User, Persona, Task, Session, SessionPreset,
    PersonaPreset, TaskPreset, PatentSession,
)

DIVIDER = "=" * 72
THIN    = "-" * 72


def _fmt_dt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "不明"


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


async def load_orphan_users(db) -> list[User]:
    result = await db.execute(
        select(User)
        .where(User.windows_username == None)  # noqa: E711
        .options(
            selectinload(User.sessions),
            selectinload(User.personas),
            selectinload(User.tasks),
            selectinload(User.session_presets),
            selectinload(User.persona_presets),
            selectinload(User.task_presets),
            selectinload(User.patent_sessions),
        )
        .order_by(User.last_login_at.desc())
    )
    return result.scalars().all()


def print_user_detail(idx: int, u: User) -> None:
    """1ユーザー分の詳細を端末に出力する。"""
    print(f"\n{DIVIDER}")
    print(f"  [{idx}] email       : {u.email}")
    print(f"       display_name : {u.display_name or '(未設定)'}")
    print(f"       最終ログイン  : {_fmt_dt(u.last_login_at)}")
    print(f"       最終IP       : {u.last_known_ip or '不明'}")
    print(f"       作成日       : {_fmt_dt(u.created_at)}")
    print(f"       is_admin     : {u.is_admin}  |  is_approved: {u.is_approved}")
    print(THIN)

    # セッション履歴（最新10件）
    sessions_sorted = sorted(u.sessions, key=lambda s: s.created_at, reverse=True)
    if sessions_sorted:
        print(f"  ■ セッション履歴 ({len(sessions_sorted)} 件, 最新10件表示)")
        for s in sessions_sorted[:10]:
            print(f"      {_fmt_dt(s.created_at)}  {_trunc(s.title, 52)}")
    else:
        print("  ■ セッション履歴: なし")

    # ペルソナ
    if u.personas:
        names = ", ".join(_trunc(p.name, 20) for p in u.personas)
        print(f"  ■ ペルソナ ({len(u.personas)} 件): {names}")
    else:
        print("  ■ ペルソナ: なし")

    # タスク
    if u.tasks:
        descs = " / ".join(_trunc(t.description, 25) for t in u.tasks[:5])
        print(f"  ■ タスク ({len(u.tasks)} 件): {descs}")
    else:
        print("  ■ タスク: なし")

    # セッションプリセット
    if u.session_presets:
        names = ", ".join(_trunc(p.name, 20) for p in u.session_presets)
        print(f"  ■ セッションプリセット ({len(u.session_presets)} 件): {names}")

    # ペルソナプリセット
    if u.persona_presets:
        names = ", ".join(_trunc(p.name, 20) for p in u.persona_presets)
        print(f"  ■ ペルソナプリセット ({len(u.persona_presets)} 件): {names}")

    # タスクプリセット
    if u.task_presets:
        names = ", ".join(_trunc(p.name, 20) for p in u.task_presets)
        print(f"  ■ タスクプリセット ({len(u.task_presets)} 件): {names}")

    # 特許セッション
    if u.patent_sessions:
        names = ", ".join(_trunc(p.title, 25) for p in u.patent_sessions[:5])
        print(f"  ■ 特許セッション ({len(u.patent_sessions)} 件): {names}")

    # 完全に空のユーザー
    total_data = (len(u.sessions) + len(u.personas) + len(u.tasks) +
                  len(u.session_presets) + len(u.persona_presets) +
                  len(u.task_presets) + len(u.patent_sessions))
    if total_data == 0:
        print("  ※ データなし（削除候補）")


async def main(dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        orphans = await load_orphan_users(db)

        if not orphans:
            print("windows_username が未設定のユーザーはいません。復旧不要です。")
            return

        print(f"\n{DIVIDER}")
        print(f"  windows_username 未設定ユーザー: {len(orphans)} 件")
        print(f"{DIVIDER}")

        # 全ユーザーの詳細を表示
        for i, u in enumerate(orphans):
            print_user_detail(i, u)

        print(f"\n{DIVIDER}")

        if dry_run:
            print("[dry-run] DB は変更されません。")
            return

        print("\n各ユーザーに Windows ユーザー名を割り当てます。")
        print("  - スキップ   : Enter のみ")
        print("  - 削除       : 'd' を入力 (データなしユーザー向け)")
        print(f"{THIN}\n")

        updated = 0
        deleted = 0

        for i, u in enumerate(orphans):
            # データ量サマリを再表示
            total_data = (len(u.sessions) + len(u.personas) + len(u.tasks) +
                          len(u.session_presets) + len(u.persona_presets) +
                          len(u.task_presets) + len(u.patent_sessions))
            data_hint = f"{total_data} 件のデータ" if total_data > 0 else "データなし"
            prompt = f"[{i}] {u.email} ({data_hint}) > Windows ユーザー名: "

            try:
                win_name = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n中断しました。")
                break

            # スキップ
            if not win_name:
                print("  → スキップ\n")
                continue

            # 削除
            if win_name.lower() == "d":
                if total_data > 0:
                    confirm = input(
                        f"  [警告] {total_data} 件のデータが削除されます。本当に削除しますか？ [y/N]: "
                    ).strip().lower()
                    if confirm != "y":
                        print("  → スキップ\n")
                        continue
                await db.delete(u)
                await db.commit()
                deleted += 1
                print(f"  → 削除: {u.email}\n")
                continue

            # 既存ユーザーとの重複チェック
            existing_result = await db.execute(
                select(User).where(User.windows_username == win_name)
            )
            existing_user = existing_result.scalar_one_or_none()

            if existing_user and existing_user.id != u.id:
                print(
                    f"  [警告] '{win_name}' は既に {existing_user.email} に紐づいています。\n"
                    f"  データを既存ユーザー ({existing_user.email}) にマージして\n"
                    f"  このレコード ({u.email}) を削除しますか？ [y/N]: ",
                    end=""
                )
                ans = input().strip().lower()
                if ans != "y":
                    print("  → スキップ\n")
                    continue

                # マージ: 各テーブルの user_id を既存ユーザーに付け替え
                from sqlalchemy import update as sql_update
                tables_fk = [
                    ("sessions", "user_id"),
                    ("personas", "user_id"),
                    ("tasks", "user_id"),
                    ("session_presets", "user_id"),
                    ("persona_presets", "user_id"),
                    ("task_presets", "user_id"),
                    ("patent_sessions", "user_id"),
                    ("patent_presets", "user_id"),
                    ("patent_csvs", "user_id"),
                ]
                from sqlalchemy import text
                for table, col in tables_fk:
                    await db.execute(
                        text(f"UPDATE {table} SET {col} = :new_id WHERE {col} = :old_id"),
                        {"new_id": existing_user.id, "old_id": u.id},
                    )
                await db.delete(u)
                await db.commit()
                updated += 1
                print(
                    f"  → マージ完了: {u.email} のデータを {existing_user.email} に統合し削除\n"
                )
                continue

            # 通常の更新
            old_email = u.email
            new_email = f"{win_name}@dev.local"
            u.email = new_email
            u.windows_username = win_name
            u.display_name = win_name
            await db.commit()
            await db.refresh(u)
            updated += 1
            print(f"  → 更新: {old_email} → {new_email}\n")

        print(f"\n{DIVIDER}")
        print(f"完了: 更新 {updated} 件 / 削除 {deleted} 件")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run))
