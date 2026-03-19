"""
parallel.py
===========
2. 並列独立（ブレスト）ストラテジー。

各エージェントが独立してタスクを実行し、最後にファシリテーター役が全員の意見を集約する。

動作フロー:
  1. 全ペルソナが独立して発言（会話履歴を共有せず、テーマに対する独自の見解を出す）
  2. ファシリテーター（最初のペルソナ or 指定ペルソナ）が全発言を参照して集約発言を生成
  3. 要約を生成

設定項目 (ThemeConfig.strategy_config):
  - facilitator_index: ファシリテーター役のペルソナインデックス（デフォルト: 0 = 先頭）
"""

import uuid
from typing import List

from ...models import MessageHistory
from ..input_builder import build_agent_input
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


# ファシリテーター用の集約プロンプトテンプレート
FACILITATOR_PROMPT_SUFFIX = """

--- 以下は各メンバーの独立した意見です ---
{member_opinions}
---

上記の意見を踏まえて、ファシリテーターとして以下を行ってください:
1. 各意見の共通点と相違点を整理
2. 最も重要なポイントを抽出
3. グループとしての統合的な見解をまとめる
"""


class ParallelStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "parallel"

    @property
    def description(self) -> str:
        return "並列独立（ブレスト）: 各エージェントが独立して意見を出し、ファシリテーターが集約します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        # ストラテジー設定を取得
        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        facilitator_index = int(config.get("facilitator_index", 0))
        facilitator_index = min(facilitator_index, len(active) - 1)

        # ------------------------------------------------------------------
        # Phase 1: 全ペルソナが独立して発言
        # 履歴を共有せずに、テーマに対する独自の見解を出す
        # ------------------------------------------------------------------
        independent_messages: List[MessageHistory] = []

        for persona in active:
            agent_input = build_agent_input(session, persona)
            # 独立発言: 他メンバーの発言履歴は含めない（現在のテーマの履歴のみ除外）
            agent_input.history = [
                msg for msg in agent_input.history
                if msg.theme != session.current_theme
            ]
            message = ctx.agent_executor(agent_input)

            msg_history = MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=persona.name,
                content=message,
                turn_order=session.turn_count_in_theme,
            )
            independent_messages.append(msg_history)
            session.history.append(msg_history)
            session.turn_count_in_theme += 1

        # ------------------------------------------------------------------
        # Phase 2: ファシリテーターが集約
        # ------------------------------------------------------------------
        facilitator = active[facilitator_index]
        member_opinions = "\n\n".join(
            f"【{msg.agent_name}】\n{msg.content}"
            for msg in independent_messages
        )

        facilitator_input = build_agent_input(session, facilitator)
        # ファシリテーターのクエリに集約指示を追加
        facilitator_input.query += FACILITATOR_PROMPT_SUFFIX.format(
            member_opinions=member_opinions
        )

        facilitator_message = ctx.agent_executor(facilitator_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{facilitator.name}（ファシリテーター）",
            content=facilitator_message,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        # ------------------------------------------------------------------
        # 要約生成
        # ------------------------------------------------------------------
        return ctx.summarizer(session)
