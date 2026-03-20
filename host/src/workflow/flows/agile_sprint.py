"""
agile_sprint.py
===============
3. アジャイル/スプリント型フロー。

テーマ群を1スプリントとして、複数回ループする。
スプリント終了後に完成判定者が仕上がりを評価し、
合格なら早期終了、不合格なら次のスプリントへ進む。

動作フロー:
  スプリント1回 = 全テーマを順番に実行
  1. 全テーマを実行（ウォーターフォール）
  2. 完成判定者が全スプリント結果を評価 (JSON: {"done": bool, "reason": str})
  3. 完成 or 最終スプリント → 終了
  4. 未完成 → 次のスプリントへ（全テーマを再実行、履歴は引き継ぎ）

設定項目 (flow_config):
  - sprint_count            : スプリント回数（デフォルト: 2）
  - completion_judge_index  : 完成判定者のペルソナインデックス（デフォルト: -1 = 最後）
  - completion_criteria     : 完成判定の基準（省略可）
"""

from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import SPRINT_COMPLETION_PROMPT_TEMPLATE
from ..role_resolver import resolve_role, resolve_stance_prompt, build_flow_role_config
from .base import ProjectFlow, FlowContext


class AgileSprintFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "agile_sprint"

    @property
    def description(self) -> str:
        return "アジャイル/スプリント型: 全テーマをスプリントとして複数回繰り返し、完成度を高めます。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        sprint_count = max(1, int(config.get("sprint_count", 2)))
        completion_criteria = config.get("completion_criteria", "")

        # completion_judge はスプリント全体を評価するためグローバル解決
        judge = resolve_role("completion_judge", session.personas,
                             build_flow_role_config(None, config),
                             "completion_judge_index",
                             default_index=int(config.get("completion_judge_index", -1)))
        completion_criteria_section = (
            f"完成基準: {completion_criteria}\n\n" if completion_criteria else ""
        )

        for sprint_idx in range(sprint_count):
            # ------------------------------------------------------------------
            # スプリント実行: 全テーマをウォーターフォールで処理
            # ------------------------------------------------------------------
            # 最初のスプリント以外はテーマインデックスをリセット
            if sprint_idx > 0:
                session.current_theme_index = 0
                session.turn_count_in_theme = 0
                session.last_persona_id = None
                session.last_task_id = None

            while not session.all_themes_done:
                summary = ctx.run_one_theme_fn(session)
                session.advance_theme(summary)

            # 最終スプリントは判定不要
            if sprint_idx >= sprint_count - 1:
                break

            # ------------------------------------------------------------------
            # スプリント完成判定
            # ------------------------------------------------------------------
            sprint_summaries = "\n\n".join(
                f"[スプリント{sprint_idx + 1} - {s['theme']}]\n{s['summary']}"
                for s in session.summaries
            )

            judge_input = build_agent_input(session, judge)
            judge_input.query = SPRINT_COMPLETION_PROMPT_TEMPLATE.format(
                sprint_summaries=sprint_summaries,
                completion_criteria_section=completion_criteria_section,
            )
            judge_response = ctx.agent_executor(judge_input)

            data = parse_json_response(judge_response, fallback={})
            done = bool(data.get("done", False))
            reason = str(data.get("reason", ""))

            # 判定結果を要約に記録
            session.summaries.append({
                "theme": f"[スプリント{sprint_idx + 1}完成判定]",
                "summary": f"判定: {'完成' if done else '継続'}\n理由: {reason}\n\n{judge_response}",
            })

            if done:
                break
