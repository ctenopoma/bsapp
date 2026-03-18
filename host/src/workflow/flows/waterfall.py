"""
waterfall.py
============
1. ウォーターフォール型フロー（現行ロジック移植）。

テーマを定義された順番に1つずつ実行する。
最もシンプルで予測可能なフロー。

設定項目: なし
"""

from .base import ProjectFlow, FlowContext


class WaterfallFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "waterfall"

    @property
    def description(self) -> str:
        return "ウォーターフォール型: テーマを定義順に1つずつ実行します（デフォルト）。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        while not session.all_themes_done:
            summary = ctx.run_one_theme_fn(session)
            session.advance_theme(summary)
