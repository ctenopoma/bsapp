"""
helper_knowledge.py
===================
ペルソナ・タスク・セットアップ入力支援ヘルパーのナレッジ管理。

host/knowledge/ ディレクトリ配下の Markdown ファイルを読み込み、
context (persona / task / setup) ごとのシステムプロンプトと参考情報を返す。
"""

import logging
from pathlib import Path
from typing import Literal

logger = logging.getLogger("bsapp.helper")

ContextType = Literal["persona", "task", "setup"]

# host/knowledge/ ディレクトリ (host/ 直下)
KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "knowledge"

# context → ファイル名のマッピング
_KNOWLEDGE_FILES: dict[str, str] = {
    "persona": "persona.md",
    "task": "task.md",
    "setup": "setup.md",
}


def _read_knowledge(context: ContextType) -> str:
    """knowledge/ 配下のファイルを読み込む。無ければ空文字を返す。"""
    fname = _KNOWLEDGE_FILES.get(context)
    if not fname:
        return ""
    path = KNOWLEDGE_DIR / fname
    if not path.exists():
        logger.warning(f"Knowledge file not found: {path}")
        return ""
    return path.read_text(encoding="utf-8").strip()


def get_system_prompt(context: ContextType) -> str:
    """context に応じたシステムプロンプトを組み立てて返す。"""

    knowledge = _read_knowledge(context)

    # ---- context ごとのラベルとフィールド定義 ----
    if context == "persona":
        context_label = "ペルソナ"
        fields_description = (
            "フィールド:\n"
            '- name (名前): ペルソナの名前。人物像が伝わる名前。\n'
            '- role (ロール): ペルソナの役割・専門性・性格の説明。\n'
            '- pre_info (事前情報): このペルソナだけに与える背景知識や資料。\n'
        )
    elif context == "task":
        context_label = "タスク"
        fields_description = (
            "フィールド:\n"
            '- description (説明): タスクの内容。エージェントに何をさせたいかの指示。\n'
        )
    else:  # setup
        context_label = "セッション設定"
        fields_description = (
            "フィールド:\n"
            '- common_theme (共通テーマ): 全テーマに共通する上位テーマ。議論全体の方向性を決める。\n'
            '- pre_info (事前情報): 全エージェントに共有する背景情報。ドキュメントや前提条件など。\n'
            '- theme (テーマ): 個別の議論テーマ。具体的な議題・問い。\n'
        )

    # ---- システムプロンプト構築 ----
    parts = [
        f"あなたは{context_label}の入力を手伝うアシスタントです。",
        f"ユーザーが{context_label}をどう書けばいいか分からない時に、質問に答えたり、具体的な入力例を提案します。",
        "",
        fields_description,
        "## 回答ルール",
        "- ユーザーの質問に日本語で簡潔に答える。",
        "- 具体的な提案がある場合は、回答テキストの中で自然に説明する。",
        '- 提案値がある場合は、回答テキストとは別に JSON の suggestions 配列で返す。',
        '  suggestions の各要素: {"field": "フィールド名", "value": "提案値", "label": "表示ラベル"}',
        "- 一般的な質問（説明を求められた等）で具体的な値の提案が不要な場合は suggestions を省略する。",
        "- ユーザーの current_input が渡された場合は、その内容を踏まえてフィードバックする。",
        "",
    ]

    if knowledge:
        parts.append("## 参考知識")
        parts.append(knowledge)
        parts.append("")

    parts.append(
        '回答は必ず以下のJSON形式で返してください:\n'
        '{"answer": "回答テキスト", "suggestions": [{"field": "...", "value": "...", "label": "..."}]}\n'
        "suggestions が不要なら省略するか空配列にしてください。"
    )

    return "\n".join(parts)
