"""
adversarial.py
==============
5. 敵対的・レッドチーム（生成・批判）ストラテジー。

生成役と批判役が交互に発言し、提案の質を高める。

動作フロー:
  1. 生成役が初期提案を生成
  2. 批判役がダメ出し（CRITIC_PROMPT_TEMPLATE を使用）
  3. 生成役が修正提案
  4. 2→3 を max_rounds 回繰り返す
  5. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - generator_index    : 生成役のインデックス（デフォルト: 0）
  - critic_index       : 批判役のインデックス（デフォルト: 1）
  - max_rounds         : 最大往復数（デフォルト: 3）
  - critic_perspective : 批判の観点（省略可、例: "セキュリティ面から"）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..prompt_builder import CRITIC_PROMPT_TEMPLATE
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


class AdversarialStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "adversarial"

    @property
    def description(self) -> str:
        return "敵対的・レッドチーム（生成・批判）: 生成役が提案し、批判役がダメ出し、修正を繰り返して質を高めます。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")
        if len(active) < 2:
            raise ValueError(
                f"テーマ '{session.current_theme}' の敵対的ストラテジーには2人以上のペルソナが必要です"
            )

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        generator_index = min(int(config.get("generator_index", 0)), len(active) - 1)
        critic_index = min(int(config.get("critic_index", 1)), len(active) - 1)
        # generator と critic が同じにならないよう調整
        if critic_index == generator_index:
            critic_index = (generator_index + 1) % len(active)
        max_rounds = max(1, int(config.get("max_rounds", 3)))
        critic_perspective = config.get("critic_perspective", "")

        generator = active[generator_index]
        critic = active[critic_index]

        critic_perspective_section = (
            f"批判の観点: {critic_perspective}\n\n" if critic_perspective else ""
        )

        # ------------------------------------------------------------------
        # Step 1: 生成役が初期提案を生成
        # ------------------------------------------------------------------
        gen_input = build_agent_input(session, generator)
        gen_input.query += "\n\n（あなたは生成役です。議題に対する初期提案を作成してください。）"
        gen_message = ctx.agent_executor(gen_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{generator.name}（生成役）",
            content=gen_message,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        last_generated = gen_message

        # ------------------------------------------------------------------
        # Step 2 & 3: 批判 → 修正 のループ
        # ------------------------------------------------------------------
        for round_idx in range(max_rounds):
            # 批判役がダメ出し
            critic_input = build_agent_input(session, critic)
            critic_input.query += CRITIC_PROMPT_TEMPLATE.format(
                generated_content=last_generated,
                critic_perspective_section=critic_perspective_section,
            )
            critic_message = ctx.agent_executor(critic_input)

            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{critic.name}（批判役 ラウンド{round_idx + 1}）",
                content=critic_message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

            # 生成役が修正提案（最終ラウンド後は修正不要）
            if round_idx < max_rounds - 1:
                revise_input = build_agent_input(session, generator)
                revise_input.query += (
                    f"\n\n（修正ラウンド {round_idx + 1}/{max_rounds}）"
                    "批判役のフィードバックを踏まえて、提案を修正・改善してください。"
                )
                revised_message = ctx.agent_executor(revise_input)

                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name=f"{generator.name}（生成役 修正{round_idx + 1}）",
                    content=revised_message,
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1
                last_generated = revised_message

        return ctx.summarizer(session)
