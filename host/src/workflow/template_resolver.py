"""
template_resolver.py
=====================
事前情報 (pre_info) 内のテンプレート変数を解決するロジック。

使用可能なテンプレート変数:
  {{theme1_summary}}       - テーマ1の要約結果
  {{theme2_summary}}       - テーマ2の要約結果
  {{theme1_messages}}      - テーマ1の全エージェント発言
  {{theme1_agent:田中}}     - テーマ1の特定エージェント（田中）の発言
  {{themeN_summary}}       - N番目のテーマの要約結果

テーマ番号は1始まり。まだ実行されていないテーマの変数は空文字に置換される。
"""

import re
from typing import List

from ..models import MessageHistory


def resolve_template_variables(
    text: str,
    summaries: List[dict],
    history: List[MessageHistory],
    themes: list,
) -> str:
    """事前情報テキスト内の {{themeN_xxx}} 変数を実際の値に置換する。

    Parameters
    ----------
    text : str
        テンプレート変数を含む事前情報テキスト。
    summaries : list[dict]
        完了済みテーマの要約リスト。各要素は {"theme": str, "summary": str}。
    history : list[MessageHistory]
        全テーマの会話履歴。
    themes : list
        テーマ設定リスト (ThemeConfig)。インデックスとテーマ名の対応付けに使用。

    Returns
    -------
    str
        テンプレート変数が解決された文字列。
    """
    if "{{" not in text:
        return text

    # テーマ名 → 0始まりインデックスのマッピング
    theme_names = [t.theme if hasattr(t, "theme") else str(t) for t in themes]
    # 1始まりインデックス → テーマ名
    index_to_theme = {i + 1: name for i, name in enumerate(theme_names)}
    # テーマ名 → 要約
    summary_map = {s["theme"]: s["summary"] for s in summaries}

    def replacer(match: re.Match) -> str:
        theme_num = int(match.group(1))
        var_type = match.group(2)

        theme_name = index_to_theme.get(theme_num)
        if theme_name is None:
            return ""  # 存在しないテーマ番号

        if var_type == "summary":
            return summary_map.get(theme_name, "")

        if var_type == "messages":
            msgs = [m for m in history if m.theme == theme_name]
            if not msgs:
                return ""
            return "\n".join(f"{m.agent_name}: {m.content}" for m in msgs)

        # {{themeN_agent:エージェント名}} パターン
        agent_match = re.match(r"agent:(.+)", var_type)
        if agent_match:
            agent_name = agent_match.group(1)
            msgs = [
                m for m in history
                if m.theme == theme_name and m.agent_name == agent_name
            ]
            if not msgs:
                return ""
            return "\n".join(f"{m.agent_name}: {m.content}" for m in msgs)

        return ""  # 未知の変数タイプ

    # {{theme数字_変数名}} パターンにマッチ
    result = re.sub(r"\{\{theme(\d+)_([^}]+)\}\}", replacer, text)
    return result
