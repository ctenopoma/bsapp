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
from ..role_resolver import resolve_role, resolve_stance_prompt, build_flow_role_config
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

        review_focus = config.get("review_focus", "")
        review_focus_section = f"レビューの観点: {review_focus}\n\n" if review_focus else ""

        # ------------------------------------------------------------------
        # 前半: 全テーマをウォーターフォールで実行
        # ------------------------------------------------------------------
        forward_summaries = []
        # テーマインデックスも保存（後半のレビューで flow_role_map を参照するため）
        theme_indices = []
        while not session.all_themes_done:
            current_theme = session.current_theme
            theme_indices.append(session.current_theme_index)
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

            # テーマごとの flow_role_map でレビュアーを解決
            theme_idx = theme_indices[i]
            theme_cfg = session.themes[theme_idx] if theme_idx < len(session.themes) else None
            frm = build_flow_role_config(
                theme_cfg.flow_role_map if theme_cfg else None, config)

            active = session.personas
            if theme_cfg and theme_cfg.persona_ids:
                id_set = set(theme_cfg.persona_ids)
                active = [p for p in session.personas if p.id in id_set] or session.personas

            reviewer = resolve_role("reviewer", active, frm, "reviewer_index",
                                    default_index=int(config.get("reviewer_index", -1)))
            reviewer_stance = resolve_stance_prompt("reviewer", {**frm, **{k: v for k, v in config.items() if k == "slot_prompts"}})

            reviewer_input = build_agent_input(session, reviewer, stance_prompt=reviewer_stance)
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
