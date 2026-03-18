"""
v_shape.py
==========
2. V字型フロー（実行＆逆順レビュー）。

前半でテーマを順番に実行し、後半は逆順で各テーマの成果物を
後続テーマの結果と照らし合わせながらレビューする。

動作フロー:
  前半: テーマを 1→2→...→N の順に実行（ウォーターフォール）
  後半: テーマを N-2→...→1→0 の逆順でレビュー
    - レビュアーが元テーマの結果 + 後続テーマの結果を参照してフィードバックを生成
    - レビュー結果は要約として session.summaries に追記される

設定項目 (flow_config):
  - reviewer_index : レビュアー役のペルソナインデックス（デフォルト: -1 = 最後）
  - review_focus   : レビューで重点的に確認する観点（省略可）
"""

from ..input_builder import build_agent_input
from ..prompt_builder import V_SHAPE_REVIEW_PROMPT_TEMPLATE
from .base import ProjectFlow, FlowContext


class VShapeFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "v_shape"

    @property
    def description(self) -> str:
        return "V字型: 全テーマを順番に実行した後、逆順でレビューして品質を担保します。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        raw_reviewer = int(config.get("reviewer_index", -1))
        reviewer_index = (
            len(session.personas) - 1 if raw_reviewer < 0
            else min(raw_reviewer, len(session.personas) - 1)
        )
        review_focus = config.get("review_focus", "")

        reviewer = session.personas[reviewer_index]
        review_focus_section = f"レビューの観点: {review_focus}\n\n" if review_focus else ""

        # ------------------------------------------------------------------
        # 前半: 全テーマをウォーターフォールで実行
        # ------------------------------------------------------------------
        forward_summaries = []
        while not session.all_themes_done:
            current_theme = session.current_theme
            summary = ctx.run_one_theme_fn(session)
            forward_summaries.append((current_theme, summary))
            session.advance_theme(summary)

        # ------------------------------------------------------------------
        # 後半: 逆順でレビュー（最後のテーマはスキップ）
        # ------------------------------------------------------------------
        for i in range(len(forward_summaries) - 2, -1, -1):
            theme, original_summary = forward_summaries[i]
            downstream_summaries = "\n\n".join(
                f"[{t}]\n{s}" for t, s in forward_summaries[i + 1:]
            )

            reviewer_input = build_agent_input(session, reviewer)
            reviewer_input.query = V_SHAPE_REVIEW_PROMPT_TEMPLATE.format(
                theme=theme,
                original_summary=original_summary,
                downstream_summaries=downstream_summaries,
                review_focus_section=review_focus_section,
            )
            review_response = ctx.agent_executor(reviewer_input)

            session.summaries.append({
                "theme": f"[V字レビュー: {theme}]",
                "summary": review_response,
            })
