"""
hierarchical.py
===============
4. 階層型（計画・実行・反省）ストラテジー。

マネージャーが計画を立て、ワーカーが実行し、マネージャーが評価するサイクルを回す。
評価が合格するまで、または最大修正ループ数に達するまで繰り返す。

動作フロー:
  1. マネージャーが「計画・指示」を発言
  2. ワーカー全員（マネージャー以外）が順番に「実行」
  3. マネージャーが全ワーカーの発言を評価（JSON: pass/complete/feedback）
     → complete=true: プロセス完了 → 早期終了
     → pass=true: 合格 → 終了
     → pass=false: フィードバックを履歴に追加し 2 に戻る
  4. リトライ上限到達時は強制終了
  5. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - manager_index      : マネージャー役のインデックス（デフォルト: 0）
  - max_revision_loops : 最大修正ループ数（デフォルト: 3）
  - pass_condition     : 合格判定の追加指示（省略可）
  - role_map           : ペルソナIDと役割のマッピング（省略可）
                         例: {"persona_id_1": "manager", "persona_id_2": "worker", ...}
  - max_retry_per_phase: リトライ上限（デフォルト: 3）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..prompt_builder import EVALUATION_PROMPT_TEMPLATE
from ..role_resolver import resolve_role, resolve_role_group, resolve_stance_prompt
from ..termination import TerminationChecker
from .base import ThemeStrategy, StrategyContext, get_ordered_personas


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

        # 役割解決: role_map → index → デフォルト
        manager = resolve_role("manager", active, config, "manager_index", default_index=0)
        workers = resolve_role_group("worker", active, config, exclude_ids={manager.id})

        max_revision_loops = max(1, int(config.get("max_revision_loops", 3)))
        pass_condition = config.get("pass_condition", "")

        # スタンスプロンプト解決
        manager_stance = resolve_stance_prompt("manager", config)
        worker_stance = resolve_stance_prompt("worker", config)

        # 終了制御
        checker = TerminationChecker(config)

        # ------------------------------------------------------------------
        # Step 1: マネージャーが計画・指示を発言
        # ------------------------------------------------------------------
        plan_input = build_agent_input(session, manager, stance_prompt=manager_stance)
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
                worker_input = build_agent_input(session, worker, stance_prompt=worker_stance)
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
            eval_input = build_agent_input(session, manager, stance_prompt=manager_stance)
            eval_input.query += EVALUATION_PROMPT_TEMPLATE.format(
                worker_opinions=worker_opinions,
                pass_condition_section=pass_condition_section,
            )
            eval_response = ctx.agent_executor(eval_input)

            # JSON評価結果をパース（標準スキーマ）
            eval_result = checker.parse_evaluation(eval_response)
            passed = eval_result.get("pass", True)
            complete = checker.is_complete(eval_result)
            feedback = eval_result.get("feedback", "")

            eval_label = "合格" if passed else f"不合格（フィードバック: {feedback}）"
            session.history.append(MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{manager.name}（マネージャー：評価）",
                content=f"[評価: {eval_label}]\n{eval_response}",
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

            # 完了判定
            if complete or passed:
                break

            # 不合格 → リトライ上限チェック
            checker.increment_retry()
            if checker.should_force_proceed():
                session.history.append(MessageHistory(
                    id=uuid.uuid4().hex,
                    theme=session.current_theme,
                    agent_name="システム",
                    content=f"リトライ上限（{checker.max_retry}回）に達したため、現状の成果で打ち切ります。",
                    turn_order=session.turn_count_in_theme,
                ))
                session.turn_count_in_theme += 1
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
