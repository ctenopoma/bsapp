"""
dynamic_generation.py
=====================
9. 動的エージェント生成ストラテジー。

メタエージェントが課題に最適なペルソナをその場で生成し、議論を実行する。
生成されたペルソナはセッション終了後に破棄される一時的な存在。

動作フロー:
  1. メタエージェントが一時ペルソナを JSON で生成:
       {"personas": [{"name": "...", "role": "...", "pre_info": "..."}, ...]}
  2. 生成されたペルソナを一時的にセッションの personas に追加
  3. 生成ペルソナ全員がラウンドロビン形式で議論
  4. テーマ処理終了後に一時ペルソナを削除
  5. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - meta_agent_index    : メタエージェント役のインデックス（デフォルト: 0）
  - max_generated       : 同時生成する最大ペルソナ数（デフォルト: 3）
  - generation_guideline: 編成指針（省略可）
  - role_map            : ペルソナIDと役割のマッピング（省略可）
                          例: {"persona_id_1": "meta_agent"}
"""

import uuid

from ...models import MessageHistory, Persona, RagConfig
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..role_resolver import resolve_role
from .base import ThemeStrategy, StrategyContext, get_ordered_personas

# メタエージェント用プロンプト
META_AGENT_PROMPT_TEMPLATE = """\

議題に対して最適な議論メンバーを最大 {max_generated} 人生成してください。
{generation_guideline_section}各メンバーには専門性・立場・視点が異なる役割を与えてください。

以下の JSON 形式のみで回答してください（前後の説明は不要です）:
{{"personas": [
  {{"name": "名前", "role": "役割・専門性", "pre_info": "このペルソナの背景・観点（省略可）"}},
  ...
]}}
"""

# 生成ペルソナへの紹介プロンプト
GENERATED_PERSONA_INTRO = "（このペルソナは今回の議論のために一時的に生成されました）"


class DynamicGenerationStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "dynamic_generation"

    @property
    def description(self) -> str:
        return "動的エージェント生成: メタエージェントが議題に最適なペルソナをその場で生成し、議論を実行します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        # 役割解決: role_map → index → デフォルト
        meta_agent = resolve_role("meta_agent", active, config, "meta_agent_index", default_index=0)
        max_generated = max(1, int(config.get("max_generated", 3)))
        generation_guideline = config.get("generation_guideline", "")

        generation_guideline_section = (
            f"編成指針: {generation_guideline}\n" if generation_guideline else ""
        )

        # ------------------------------------------------------------------
        # Step 1: メタエージェントが一時ペルソナを JSON で生成
        # ------------------------------------------------------------------
        meta_input = build_agent_input(session, meta_agent)
        meta_input.query += META_AGENT_PROMPT_TEMPLATE.format(
            max_generated=max_generated,
            generation_guideline_section=generation_guideline_section,
        )
        meta_response = ctx.agent_executor(meta_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{meta_agent.name}（メタエージェント：編成）",
            content=meta_response,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        # JSON パース
        gen_data = parse_json_response(meta_response, fallback={})
        raw_personas = gen_data.get("personas", [])

        # ------------------------------------------------------------------
        # Step 2: 一時ペルソナを生成してセッションに追加
        # ------------------------------------------------------------------
        temp_persona_ids: list[str] = []
        generated_personas: list[Persona] = []

        for raw in raw_personas[:max_generated]:
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name", "")).strip()
            role = str(raw.get("role", "")).strip()
            if not name or not role:
                continue
            pre_info = str(raw.get("pre_info", "")).strip()
            full_pre_info = "\n".join(filter(None, [pre_info, GENERATED_PERSONA_INTRO]))

            temp_id = f"temp-{uuid.uuid4().hex}"
            persona = Persona(
                id=temp_id,
                name=name,
                role=role,
                pre_info=full_pre_info,
                rag_config=RagConfig(enabled=False),
            )
            generated_personas.append(persona)
            temp_persona_ids.append(temp_id)

        if not generated_personas:
            # 生成失敗 → 既存のアクティブペルソナで継続（追加不要）
            generated_personas = active
        else:
            # セッションに一時ペルソナを追加（生成成功時のみ）
            session.personas.extend(generated_personas)

        try:
            # ------------------------------------------------------------------
            # Step 3: 生成ペルソナ全員がラウンドロビンで議論
            # (session.current_turns_per_theme 回)
            # ------------------------------------------------------------------
            for turn_idx in range(session.current_turns_per_theme):
                persona = generated_personas[turn_idx % len(generated_personas)]
                speaker_input = build_agent_input(session, persona)
                message = ctx.agent_executor(speaker_input)

                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name=f"{persona.name}（生成ペルソナ）",
                    content=message,
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1
                session.last_persona_id = persona.id

            return ctx.summarizer(session)

        finally:
            # ------------------------------------------------------------------
            # Step 4: 一時ペルソナを削除（セッション終了時に破棄）
            # ------------------------------------------------------------------
            temp_id_set = set(temp_persona_ids)
            session.personas = [p for p in session.personas if p.id not in temp_id_set]
