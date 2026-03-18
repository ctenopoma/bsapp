"""
dynamic_routing.py
==================
7. 動的ルーティング（司会者主導）ストラテジー。

司会者（ルーター）が直前の文脈から「次に誰が発言すべきか」をJSON形式で指名する。
議論の流れに応じて発言者が動的に決まる高度な連携パターン。

動作フロー:
  1. ルーターが次の発言者を JSON で指名:
       {"next_speaker": "ペルソナ名", "reason": "指名理由"}
     または終了シグナル:
       {"end": true, "reason": "終了理由"}
  2. 指名されたペルソナが発言
  3. 1→2 を max_turns 回、または終了シグナルが出るまで繰り返す
  4. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - router_index  : 司会者のインデックス（デフォルト: 0）
  - max_turns     : 最大ターン数（デフォルト: 10）
  - end_condition : 終了条件の説明（省略可）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from .base import ThemeStrategy, StrategyContext, get_ordered_personas

# ルーター用のシステムプロンプトサフィックス
ROUTER_PROMPT_TEMPLATE = """\

--- 参加者一覧 ---
{participant_list}
---

{end_condition_section}あなたは司会者として、現在の議論の流れを踏まえて次の発言者を指名してください。
議論を深めるために最も適切な参加者を選んでください。

以下の JSON 形式のみで回答してください（前後の説明は不要です）:
発言者を指名する場合:
{{"next_speaker": "参加者名（上記リストの名前と完全一致）", "reason": "指名理由（日本語）"}}

議論を終了する場合:
{{"end": true, "reason": "終了理由（日本語）"}}
"""


class DynamicRoutingStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "dynamic_routing"

    @property
    def description(self) -> str:
        return "動的ルーティング（司会者主導）: 司会者が文脈を読んで次の発言者を動的に指名します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")
        if len(active) < 2:
            raise ValueError(
                f"テーマ '{session.current_theme}' の動的ルーティングには2人以上のペルソナが必要です"
            )

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        router_index = min(int(config.get("router_index", 0)), len(active) - 1)
        max_turns = max(1, int(config.get("max_turns", 10)))
        end_condition = config.get("end_condition", "")

        router = active[router_index]
        speakers = [p for p in active if p.id != router.id]

        # 参加者リスト（ルーターへのプロンプト用）
        participant_list = "\n".join(f"- {p.name}（{p.role}）" for p in speakers)
        end_condition_section = (
            f"終了条件: {end_condition}\n\n" if end_condition else ""
        )

        # 参加者名 → ペルソナ の辞書（JSONの next_speaker を解決するため）
        name_to_persona = {p.name: p for p in speakers}

        for turn_idx in range(max_turns):
            # ------------------------------------------------------------------
            # ルーターが次の発言者を JSON で指名
            # ------------------------------------------------------------------
            router_input = build_agent_input(session, router)
            router_input.query += ROUTER_PROMPT_TEMPLATE.format(
                participant_list=participant_list,
                end_condition_section=end_condition_section,
            )
            routing_response = ctx.agent_executor(router_input)

            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{router.name}（司会者：指名）",
                content=routing_response,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

            # JSON パース
            routing = parse_json_response(routing_response, fallback={})

            # 終了シグナルの検出
            if routing.get("end"):
                break

            # 次の発言者を解決
            next_speaker_name = str(routing.get("next_speaker", "")).strip()
            next_persona = name_to_persona.get(next_speaker_name)

            if next_persona is None:
                # パース失敗 or 名前不一致 → 最後の発言者以外からラウンドロビン
                candidates = [p for p in speakers if p.id != session.last_persona_id] or speakers
                next_persona = candidates[turn_idx % len(candidates)]

            # ------------------------------------------------------------------
            # 指名されたペルソナが発言
            # ------------------------------------------------------------------
            speaker_input = build_agent_input(session, next_persona)
            speaker_message = ctx.agent_executor(speaker_input)

            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=next_persona.name,
                content=speaker_message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1
            session.last_persona_id = next_persona.id

        return ctx.summarizer(session)
