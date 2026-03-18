"""
hierarchical.py
===============
4. 階層型（計画・実行・反省）ストラテジー。

マネージャーが計画を立て、ワーカーが実行し、マネージャーが評価するサイクルを回す。
評価が合格するまで、または最大修正ループ数に達するまで繰り返す。

動作フロー:
  1. マネージャーが「計画・指示」を発言
  2. ワーカー全員（マネージャー以外）が順番に「実行」
  3. マネージャーが全ワーカーの発言を評価
     → 合格: 終了
     → 不合格: フィードバックを履歴に追加し 2 に戻る（最大 max_revision_loops 回）
  4. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - manager_index      : マネージャー役のインデックス（デフォルト: 0）
  - max_revision_loops : 最大修正ループ数（デフォルト: 3）
  - pass_condition     : 合格判定の追加指示（省略可）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import EVALUATION_PROMPT_TEMPLATE
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


def _parse_evaluation(text: str) -> tuple[bool, str]:
    """LLM応答からJSON評価結果をパースする。

    パース失敗時は (True, "") を返してループを止める。
    """
    data = parse_json_response(text, fallback={})
    return bool(data.get("pass", True)), str(data.get("feedback", ""))


class HierarchicalStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "hierarchical"

    @property
    def description(self) -> str:
        return "階層型（計画・実行・反省）: マネージャーが計画を立て、ワーカーが実行し、評価・修正を繰り返します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        manager_index = min(int(config.get("manager_index", 0)), len(active) - 1)
        max_revision_loops = max(1, int(config.get("max_revision_loops", 3)))
        pass_condition = config.get("pass_condition", "")

        manager = active[manager_index]
        workers = [p for p in active if p.id != manager.id]

        # ------------------------------------------------------------------
        # Step 1: マネージャーが計画・指示を発言
        # ------------------------------------------------------------------
        plan_input = build_agent_input(session, manager)
        plan_input.query += "\n\n（あなたはマネージャーです。まずワーカーへの計画・指示を述べてください。）"
        plan_message = ctx.agent_executor(plan_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{manager.name}（マネージャー：計画）",
            content=plan_message,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        # ------------------------------------------------------------------
        # Step 2 & 3: ワーカー実行 → マネージャー評価 のループ
        # ------------------------------------------------------------------
        for loop_idx in range(max_revision_loops):
            round_label = f"（修正ラウンド {loop_idx + 1}/{max_revision_loops}）" if loop_idx > 0 else ""

            # ワーカー全員が順番に発言
            worker_messages: list[MessageHistory] = []
            for worker in workers if workers else active:
                worker_input = build_agent_input(session, worker)
                if loop_idx > 0:
                    worker_input.query += f"\n\n{round_label}マネージャーのフィードバックを踏まえて発言を修正してください。"
                msg_text = ctx.agent_executor(worker_input)

                msg = MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name=f"{worker.name}（ワーカー）",
                    content=msg_text,
                    turn_order=session.turn_count_in_theme,
                )
                worker_messages.append(msg)
                session.history.append(msg)
                session.turn_count_in_theme += 1

            # マネージャーが評価（JSON出力を要求）
            worker_opinions = "\n\n".join(
                f"【{m.agent_name}】\n{m.content}" for m in worker_messages
            )
            pass_condition_section = (
                f"\n合格条件: {pass_condition}" if pass_condition else ""
            )
            eval_input = build_agent_input(session, manager)
            eval_input.query += EVALUATION_PROMPT_TEMPLATE.format(
                worker_opinions=worker_opinions,
                pass_condition_section=pass_condition_section,
            )
            eval_response = ctx.agent_executor(eval_input)

            passed, feedback = _parse_evaluation(eval_response)

            eval_label = "合格" if passed else f"不合格（フィードバック: {feedback}）"
            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{manager.name}（マネージャー：評価）",
                content=f"[評価: {eval_label}]\n{eval_response}",
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

            if passed:
                break

            # 不合格の場合、フィードバックを履歴に追加してループ継続
            if loop_idx < max_revision_loops - 1:
                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name=f"{manager.name}（マネージャー：フィードバック）",
                    content=f"修正指示: {feedback}",
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1

        return ctx.summarizer(session)
