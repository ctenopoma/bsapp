"""
stage_gate.py
=============
2. ステージゲート型フロー。

各テーマの実行後にゲートキーパーが品質チェックを行い、
不合格なら差し戻して再実行する。合格したテーマのみ次に進む。

動作フロー:
  各テーマに対して:
  1. テーマを実行して要約を得る
  2. ゲートキーパーが要約を評価 (JSON: {"pass": bool, "feedback": str})
  3. 合格 → 次のテーマへ進む
  4. 不合格 → フィードバックを履歴に追加して再実行 (max_revisions 回まで)
  5. 最大回数到達 → 不合格のまま次へ進む

設定項目 (flow_config):
  - gatekeeper_index : ゲートキーパー役のペルソナインデックス（デフォルト: 0）
  - pass_condition   : 通過条件の説明（省略可）
  - max_revisions    : 最大差し戻し回数（デフォルト: 2）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import GATEKEEPER_PROMPT_TEMPLATE
from ..role_resolver import resolve_role, resolve_stance_prompt, build_flow_role_config
from .base import ProjectFlow, FlowContext


class StageGateFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "stage_gate"

    @property
    def description(self) -> str:
        return "ステージゲート型: 各テーマ完了後にゲートキーパーが品質チェックし、不合格なら差し戻します。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        pass_condition = config.get("pass_condition", "")
        max_revisions = max(0, int(config.get("max_revisions", 2)))

        pass_condition_section = (
            f"通過条件: {pass_condition}\n\n" if pass_condition else ""
        )

        while not session.all_themes_done:
            current_theme = session.current_theme

            # テーマごとの flow_role_map で役割解決
            theme_cfg = session.current_theme_config
            frm = build_flow_role_config(
                theme_cfg.flow_role_map if theme_cfg else None, config)
            frm_with_slots = {**frm, **{k: v for k, v in config.items() if k == "slot_prompts"}}

            active = session.active_personas or session.personas
            gatekeeper = resolve_role("gatekeeper", active, frm, "gatekeeper_index",
                                      default_index=int(config.get("gatekeeper_index", 0)))
            gatekeeper_stance = resolve_stance_prompt("gatekeeper", frm_with_slots)

            last_summary = ""

            for revision in range(max_revisions + 1):
                # テーマを実行
                last_summary = ctx.run_one_theme_fn(session)

                # ゲートキーパーが評価
                gate_input = build_agent_input(session, gatekeeper, stance_prompt=gatekeeper_stance)
                gate_input.query = GATEKEEPER_PROMPT_TEMPLATE.format(
                    theme=current_theme,
                    summary=last_summary,
                    pass_condition_section=pass_condition_section,
                )
                gate_response = ctx.agent_executor(gate_input)

                data = parse_json_response(gate_response, fallback={})
                passed = bool(data.get("pass", True))
                feedback = str(data.get("feedback", ""))

                # ゲート結果を履歴に記録
                gate_label = "通過" if passed else f"差し戻し（フィードバック: {feedback}）"
                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=current_theme,
                    agent_name=f"{gatekeeper.name}（ゲートキーパー）",
                    content=f"[ゲート評価: {gate_label}]\n{gate_response}",
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1

                if passed:
                    break

                # 不合格: フィードバックを履歴に追加して再実行準備
                if revision < max_revisions:
                    session.history.append(MessageHistory(
                        id=uuid.uuid4().hex,
                        theme=current_theme,
                        agent_name=f"{gatekeeper.name}（ゲートキーパー：改善指示）",
                        content=f"改善が必要です。{feedback}",
                        turn_order=session.turn_count_in_theme,
                    ))
                    # ターンカウントをリセットして再実行
                    session.turn_count_in_theme = 0
                    session.last_persona_id = None
                    session.last_task_id = None

            session.advance_theme(last_summary)
