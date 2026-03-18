"""
sequential.py
=============
1. シーケンシャル（バトンリレー）ストラテジー。

各エージェントが順番にタスクを実行し、結果を次に渡す。
現行の turn_runner.py のロジックをそのまま移植したもの。
"""

import uuid

from ...models import MessageHistory
from ..persona_selector import select_persona
from ..input_builder import build_agent_input
from .base import ThemeStrategy, StrategyContext


class SequentialStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "sequential"

    @property
    def description(self) -> str:
        return "シーケンシャル（バトンリレー）: 各エージェントが順番に発言し、結果を次に渡します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = session.active_personas
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        for _ in range(session.current_turns_per_theme):
            persona = select_persona(active, session)
            agent_input = build_agent_input(session, persona)
            message = ctx.agent_executor(agent_input)

            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=persona.name,
                content=message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

        return ctx.summarizer(session)
