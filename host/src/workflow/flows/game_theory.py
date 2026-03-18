"""
game_theory.py
==============
5. ゲーム理論 / 対立型フロー（陣営間ディベート）。

提案陣営と批判陣営に分かれ、各テーマについて複数ラウンドの対立的な議論を行う。
最終的に合意形成者が両陣営の主張を整理して合意案を導く。

動作フロー:
  各テーマに対して:
  1. 提案陣営のペルソナが順番に発言
  2. 批判陣営のペルソナが順番に反論・批判
  3. 1〜2 を rounds 回繰り返す
  4. 合意形成者が最終合意案を生成してテーマ要約とする

設定項目 (flow_config):
  - split_index           : 陣営分割インデックス
                            personas[0:split_index] = 提案陣営
                            personas[split_index:]  = 批判陣営
                            （デフォルト: 1）
  - rounds                : ラウンド数（デフォルト: 2）
  - agreement_judge_index : 合意形成者のペルソナインデックス（デフォルト: -1 = 最後）
  - agreement_criteria    : 合意の基準（省略可）
"""

import uuid
import logging

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..prompt_builder import GAME_THEORY_AGREEMENT_PROMPT_TEMPLATE
from .base import ProjectFlow, FlowContext

logger = logging.getLogger("bsapp.flows.game_theory")


class GameTheoryFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "game_theory"

    @property
    def description(self) -> str:
        return "ゲーム理論/対立型: 提案陣営と批判陣営が対立的に議論し、合意形成者が最終案を導きます。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        split_index = max(1, min(int(config.get("split_index", 1)), len(session.personas) - 1))
        rounds = max(1, int(config.get("rounds", 2)))
        raw_judge = int(config.get("agreement_judge_index", -1))
        judge_index = (
            len(session.personas) - 1 if raw_judge < 0
            else min(raw_judge, len(session.personas) - 1)
        )
        agreement_criteria = config.get("agreement_criteria", "")

        proposal_camp = session.personas[:split_index]
        critic_camp = session.personas[split_index:]
        judge = session.personas[judge_index]

        if not proposal_camp:
            proposal_camp = [session.personas[0]]
        if not critic_camp:
            critic_camp = [session.personas[-1]]

        agreement_criteria_section = (
            f"合意の基準: {agreement_criteria}\n\n" if agreement_criteria else ""
        )

        while not session.all_themes_done:
            current_theme = session.current_theme
            debate_start_turn = session.turn_count_in_theme

            # ------------------------------------------------------------------
            # 提案↔批判のラウンドループ
            # ------------------------------------------------------------------
            for round_idx in range(rounds):
                # 提案陣営
                for persona in proposal_camp:
                    agent_input = build_agent_input(session, persona)
                    message = ctx.agent_executor(agent_input)
                    session.history.append(MessageHistory(
                        id=uuid.uuid4().hex,
                        theme=current_theme,
                        agent_name=f"{persona.name}（提案陣営）",
                        content=message,
                        turn_order=session.turn_count_in_theme,
                    ))
                    session.turn_count_in_theme += 1

                # 批判陣営
                for persona in critic_camp:
                    agent_input = build_agent_input(session, persona)
                    message = ctx.agent_executor(agent_input)
                    session.history.append(MessageHistory(
                        id=uuid.uuid4().hex,
                        theme=current_theme,
                        agent_name=f"{persona.name}（批判陣営）",
                        content=message,
                        turn_order=session.turn_count_in_theme,
                    ))
                    session.turn_count_in_theme += 1

            # ------------------------------------------------------------------
            # 合意形成
            # ------------------------------------------------------------------
            debate_msgs = [
                msg for msg in session.history
                if msg.theme == current_theme and msg.turn_order >= debate_start_turn
            ]
            debate_history_text = "\n".join(
                f"{msg.agent_name}: {msg.content}" for msg in debate_msgs
            )

            judge_input = build_agent_input(session, judge)
            judge_input.query = GAME_THEORY_AGREEMENT_PROMPT_TEMPLATE.format(
                theme=current_theme,
                debate_history=debate_history_text,
                agreement_criteria_section=agreement_criteria_section,
            )
            agreement = ctx.agent_executor(judge_input)

            session.advance_theme(agreement)
