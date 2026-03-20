"""
tournament.py
=============
8. トーナメント / 進化型フロー（並列コンペ）。

同じプロジェクトを複数レーンで独立して実行し、
審査員が全レーンの成果物を比較して最良を選ぶ。

動作フロー:
  1. 全テーマを num_lanes 回、それぞれ独立して実行
     （履歴・要約はレーン間で共有されない）
  2. 審査員が全レーンの成果物を評価し、最良レーンを JSON で返す:
       {"best_lane": N, "reason": "..."}
  3. 最良レーンの要約を最終成果物として採用

設定項目 (flow_config):
  - num_lanes           : 並列レーン数（デフォルト: 2）
  - judge_index         : 審査員のペルソナインデックス（デフォルト: -1 = 最後）
  - evaluation_criteria : 審査基準（省略可）
"""

import logging

from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import TOURNAMENT_JUDGE_PROMPT_TEMPLATE
from ..role_resolver import resolve_role, resolve_stance_prompt, build_flow_role_config
from .base import ProjectFlow, FlowContext

logger = logging.getLogger("bsapp.flows.tournament")


class TournamentFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "tournament"

    @property
    def description(self) -> str:
        return "トーナメント/進化型: 同じプロジェクトを複数回実行し、審査員が最良の成果物を選びます。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        num_lanes = max(1, int(config.get("num_lanes", 2)))
        evaluation_criteria = config.get("evaluation_criteria", "")

        # judge はレーン全体を評価するためグローバル解決
        judge = resolve_role("judge", session.personas,
                             build_flow_role_config(None, config),
                             "judge_index",
                             default_index=int(config.get("judge_index", -1)))
        evaluation_criteria_section = (
            f"評価基準: {evaluation_criteria}\n\n" if evaluation_criteria else ""
        )

        # 初期状態を保存（レーン間でリセットするため）
        initial_history = list(session.history)
        initial_personas = list(session.personas)

        lane_results = []

        # ------------------------------------------------------------------
        # 各レーンを独立して実行
        # ------------------------------------------------------------------
        for lane_idx in range(num_lanes):
            session.current_theme_index = 0
            session.turn_count_in_theme = 0
            session.last_persona_id = None
            session.last_task_id = None
            session.summaries = []
            session.summary_memory = ""
            session.history = list(initial_history)
            session.personas = list(initial_personas)

            lane_summaries = []
            while not session.all_themes_done:
                current_theme = session.current_theme
                summary = ctx.run_one_theme_fn(session)
                lane_summaries.append((current_theme, summary))
                session.advance_theme(summary)

            lane_results.append({
                "lane": lane_idx + 1,
                "summaries": lane_summaries,
            })
            logger.info(
                f"[TournamentFlow] レーン{lane_idx + 1} 完了: {len(lane_summaries)} テーマ"
            )

        # ------------------------------------------------------------------
        # 審査用にクリーンな状態にリセット
        # ------------------------------------------------------------------
        session.current_theme_index = 0
        session.turn_count_in_theme = 0
        session.summaries = []
        session.summary_memory = ""
        session.history = list(initial_history)
        session.personas = list(initial_personas)

        # ------------------------------------------------------------------
        # 審査員が全レーンを比較・評価
        # ------------------------------------------------------------------
        lane_summaries_text = "\n\n".join(
            f"=== レーン{r['lane']} ===\n"
            + "\n\n".join(f"[{theme}]\n{summary}" for theme, summary in r["summaries"])
            for r in lane_results
        )

        judge_input = build_agent_input(session, judge)
        judge_input.query = TOURNAMENT_JUDGE_PROMPT_TEMPLATE.format(
            lane_summaries=lane_summaries_text,
            evaluation_criteria_section=evaluation_criteria_section,
        )
        judge_response = ctx.agent_executor(judge_input)
        data = parse_json_response(judge_response, fallback={})

        best_lane_num = int(data.get("best_lane", 1))
        best_idx = best_lane_num - 1
        if not (0 <= best_idx < len(lane_results)):
            best_idx = 0

        best_lane = lane_results[best_idx]
        logger.info(f"[TournamentFlow] 最良レーン: {best_lane['lane']}")

        # ------------------------------------------------------------------
        # 最良レーンの要約を最終成果物として採用し、審査結果を末尾に記録
        # ------------------------------------------------------------------
        for theme, summary in best_lane["summaries"]:
            session.advance_theme(summary)

        session.summaries.append({
            "theme": "[トーナメント審査]",
            "summary": judge_response,
        })
