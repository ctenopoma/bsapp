"""
judge_jury.py
=============
6. 陪審員・裁判官（Judge & Jury）ストラテジー。

ディベーター間で議論し、最後に裁判官が全履歴を読んで最終判定を下す。

動作フロー:
  1. ディベーター（裁判官以外）が debate_turns 回ラウンドロビンで議論
  2. 裁判官が全ディベート履歴を読み、最終判定を発言
  3. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - judge_index          : 裁判官役のインデックス（デフォルト: -1 = 最後のペルソナ）
  - debate_turns         : ディベートの総ターン数（デフォルト: 6）
  - evaluation_criteria  : 評価基準・観点（省略可）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..prompt_builder import JUDGE_PROMPT_TEMPLATE
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


class JudgeJuryStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "judge_jury"

    @property
    def description(self) -> str:
        return "陪審員・裁判官（Judge & Jury）: ディベーター間で議論し、裁判官が最終判定を下します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")
        if len(active) < 2:
            raise ValueError(
                f"テーマ '{session.current_theme}' の Judge & Jury ストラテジーには2人以上のペルソナが必要です"
            )

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        raw_judge_index = int(config.get("judge_index", -1))
        if raw_judge_index < 0:
            judge_index = len(active) - 1
        else:
            judge_index = min(raw_judge_index, len(active) - 1)
        debate_turns = max(1, int(config.get("debate_turns", 6)))
        evaluation_criteria = config.get("evaluation_criteria", "")

        judge = active[judge_index]
        debaters = [p for i, p in enumerate(active) if i != judge_index]

        evaluation_criteria_section = (
            f"評価基準: {evaluation_criteria}\n\n" if evaluation_criteria else ""
        )

        # ------------------------------------------------------------------
        # Step 1: ディベーターがラウンドロビンで議論
        # ------------------------------------------------------------------
        debate_messages: list[MessageHistory] = []

        for turn_idx in range(debate_turns):
            debater = debaters[turn_idx % len(debaters)]
            debater_input = build_agent_input(session, debater)
            if turn_idx > 0:
                debater_input.query += "\n\n前の発言を踏まえて、あなたの立場から反論・補足・主張をしてください。"

            message = ctx.agent_executor(debater_input)
            msg = MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{debater.name}（ディベーター）",
                content=message,
                turn_order=session.turn_count_in_theme,
            )
            debate_messages.append(msg)
            session.history.append(msg)
            session.turn_count_in_theme += 1

        # ------------------------------------------------------------------
        # Step 2: 裁判官が全履歴を読んで最終判定
        # ------------------------------------------------------------------
        debate_history = "\n\n".join(
            f"【{m.agent_name}】\n{m.content}" for m in debate_messages
        )

        judge_input = build_agent_input(session, judge)
        judge_input.query += JUDGE_PROMPT_TEMPLATE.format(
            debate_history=debate_history,
            evaluation_criteria_section=evaluation_criteria_section,
        )

        verdict = ctx.agent_executor(judge_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{judge.name}（裁判官：最終判定）",
            content=verdict,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        return ctx.summarizer(session)
