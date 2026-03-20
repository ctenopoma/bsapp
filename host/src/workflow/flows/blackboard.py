"""
blackboard.py
=============
7. ブラックボード型フロー（共有黒板）。

中央のコーディネーターが現在の黒板状態（共有履歴）を読み、
次に誰がどのテーマについて発言すべきかを動的に決定する。
エージェントが自律的に黒板を更新し続け、
目標達成またはターン上限で終了する。

動作フロー:
  1. コーディネーターが黒板状態を読み、次の担当（ペルソナ + テーマ）を JSON で指示
  2. 指名されたエージェントが発言し、黒板（session.history）を更新
  3. goal_condition が満たされたとコーディネーターが判断するまでループ
  4. 終了後、全テーマの履歴から要約を生成

設定項目 (flow_config):
  - coordinator_index : コーディネーター役のペルソナインデックス（デフォルト: 0）
  - goal_condition    : 終了条件の説明（省略可）
  - max_total_turns   : 最大実行ターン数（デフォルト: テーマ数 × ペルソナ数 × 3）
"""

import uuid
import logging

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import BLACKBOARD_COORDINATOR_PROMPT_TEMPLATE
from ..role_resolver import resolve_role, resolve_stance_prompt, build_flow_role_config
from .base import ProjectFlow, FlowContext

logger = logging.getLogger("bsapp.flows.blackboard")


class BlackboardFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "blackboard"

    @property
    def description(self) -> str:
        return "ブラックボード型: コーディネーターが黒板状態を読み、次の担当エージェントを動的に指名します。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        goal_condition = config.get("goal_condition", "")
        default_max = len(session.themes) * len(session.personas) * 3
        max_total_turns = max(1, int(config.get("max_total_turns", default_max)))

        goal_condition_section = (
            f"目標達成条件: {goal_condition}\n\n" if goal_condition else ""
        )

        theme_list = "\n".join(
            f"{i}. {t.theme}" for i, t in enumerate(session.themes)
        )
        persona_list = "\n".join(
            f"{i}. {p.name}（{p.role}）" for i, p in enumerate(session.personas)
        )

        # ------------------------------------------------------------------
        # メインループ: コーディネーターが次の担当を動的に選択
        # ------------------------------------------------------------------
        for _ in range(max_total_turns):
            recent_messages = session.history[-20:]
            current_state = (
                "\n".join(
                    f"{msg.agent_name}[{msg.theme}]: {msg.content}"
                    for msg in recent_messages
                )
                or "（まだ発言なし）"
            )

            # テーマごとの flow_role_map でコーディネーターを解決
            theme_cfg = session.current_theme_config
            frm = build_flow_role_config(
                theme_cfg.flow_role_map if theme_cfg else None, config)
            active = session.active_personas or session.personas
            coordinator = resolve_role("coordinator", active, frm, "coordinator_index",
                                       default_index=int(config.get("coordinator_index", 0)))
            coordinator_stance = resolve_stance_prompt("coordinator", {**frm, **{k: v for k, v in config.items() if k == "slot_prompts"}})

            coord_input = build_agent_input(session, coordinator, stance_prompt=coordinator_stance)
            coord_input.query = BLACKBOARD_COORDINATOR_PROMPT_TEMPLATE.format(
                theme_list=theme_list,
                persona_list=persona_list,
                current_state=current_state,
                goal_condition_section=goal_condition_section,
            )
            coord_response = ctx.agent_executor(coord_input)

            data = parse_json_response(coord_response, fallback={})
            if data.get("done"):
                logger.info(
                    f"[BlackboardFlow] コーディネーターが終了を指示: {data.get('reason', '')}"
                )
                break

            persona_idx = int(data.get("persona_index", 0))
            theme_idx = int(data.get("theme_index", 0))
            if not (0 <= persona_idx < len(session.personas)):
                persona_idx = 0
            if not (0 <= theme_idx < len(session.themes)):
                theme_idx = 0

            # テーマコンテキストを設定して指名エージェントが発言
            session.current_theme_index = theme_idx
            persona = session.personas[persona_idx]

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

        # ------------------------------------------------------------------
        # 全テーマを要約（summarizer は session.current_theme でフィルタ済み）
        # ------------------------------------------------------------------
        session.summaries = []
        session.summary_memory = ""
        for i in range(len(session.themes)):
            session.current_theme_index = i
            summary = ctx.summarizer(session)
            session.summaries.append({
                "theme": session.themes[i].theme,
                "summary": summary,
            })
            session.summary_memory = "\n\n".join(
                f"[{s['theme']}]\n{s['summary']}" for s in session.summaries
            )

        session.current_theme_index = len(session.themes)
        session.turn_count_in_theme = 0
