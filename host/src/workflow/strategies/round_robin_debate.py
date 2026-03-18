"""
round_robin_debate.py
=====================
3. ラウンドロビン（順番ディベート）ストラテジー。

指定順序で全員が発言するループを複数回回し、議論を深掘りする。
全員が全履歴を共有する。

動作フロー:
  1. ラウンド1: 全ペルソナが順番に発言
  2. ラウンド2: 前ラウンドの発言を踏まえて全員が再度発言
  3. ...max_loops 回繰り返す
  4. 要約を生成

設定項目 (ThemeConfig.strategy_config):
  - max_loops: 最大ループ数（デフォルト: 2）
"""

import uuid

from ...models import MessageHistory
from ..persona_selector import select_persona
from ..input_builder import build_agent_input
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


class RoundRobinDebateStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "round_robin_debate"

    @property
    def description(self) -> str:
        return "ラウンドロビン（順番ディベート）: 全員が順番に発言するループを複数回回し、議論を深掘りします。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        # ストラテジー設定を取得
        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        max_loops = config.get("max_loops", 2)

        # ------------------------------------------------------------------
        # ラウンドロビン・ループ
        # ------------------------------------------------------------------
        for loop_idx in range(max_loops):
            for persona_idx, persona in enumerate(active):
                agent_input = build_agent_input(session, persona)

                # ラウンド番号をクエリに追加して文脈を明確にする
                if max_loops > 1:
                    agent_input.query += (
                        f"\n\n（ラウンド {loop_idx + 1}/{max_loops}）"
                    )
                    if loop_idx > 0:
                        agent_input.query += (
                            "\n前ラウンドの議論を踏まえて、あなたの見解を深めてください。"
                            "他の参加者の意見に賛同・反論・補足するなど、議論を発展させてください。"
                        )

                message = ctx.agent_executor(agent_input)

                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name=persona.name,
                    content=message,
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1
                session.last_persona_id = persona.id

        # ------------------------------------------------------------------
        # 要約生成
        # ------------------------------------------------------------------
        return ctx.summarizer(session)
