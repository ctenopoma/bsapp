"""
conditional.py
==============
4. 条件分岐/ツリー型フロー。

各テーマの実行後にルーターが結果を読み、次に実行すべきテーマを動的に選択する。
前のテーマの結論によってワークフローが分岐し、ツリー状に進行する。

動作フロー:
  1. 現在のテーマを実行して要約を得る
  2. ルーターが要約を読み、次のテーマインデックスをJSONで出力:
       {"next_theme_index": N, "reason": "..."}  または  {"end": true, "reason": "..."}
  3. 指定されたテーマを次に実行 (ループ可)
  4. end シグナルまたは max_total_themes 到達で終了

設定項目 (flow_config):
  - router_index    : ルーター役のペルソナインデックス（デフォルト: 0）
  - routing_rules   : 分岐条件ルールの説明（省略可）
  - max_total_themes: 最大実行テーマ総数（デフォルト: テーマ数 × 3）
"""

import uuid
import logging

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from ..prompt_builder import FLOW_ROUTER_PROMPT_TEMPLATE
from .base import ProjectFlow, FlowContext

logger = logging.getLogger("bsapp.flows.conditional")


class ConditionalFlow(ProjectFlow):

    @property
    def name(self) -> str:
        return "conditional"

    @property
    def description(self) -> str:
        return "条件分岐/ツリー型: テーマの結論によって次のテーマが動的に分岐します。"

    def run(self, ctx: FlowContext) -> None:
        session = ctx.session
        config = session.flow_config

        router_index = min(int(config.get("router_index", 0)), len(session.personas) - 1)
        routing_rules = config.get("routing_rules", "")
        default_max = len(session.themes) * 3
        max_total = max(len(session.themes), int(config.get("max_total_themes", default_max)))

        router = session.personas[router_index]
        routing_rules_section = (
            f"分岐ルール: {routing_rules}\n\n" if routing_rules else ""
        )

        # テーマ一覧（ルーターへのプロンプト用）
        theme_list = "\n".join(
            f"{i}. {t.theme}" for i, t in enumerate(session.themes)
        )

        executed_count = 0

        while executed_count < max_total:
            current_theme = session.current_theme
            current_index = session.current_theme_index

            # テーマを実行
            summary = ctx.run_one_theme_fn(session)
            session.advance_theme(summary)
            executed_count += 1

            # ------------------------------------------------------------------
            # ルーターが次のテーマを選択
            # ------------------------------------------------------------------
            router_input = build_agent_input(session, router)
            router_input.query = FLOW_ROUTER_PROMPT_TEMPLATE.format(
                theme_list=theme_list,
                current_theme=current_theme,
                summary=summary,
                routing_rules_section=routing_rules_section,
            )
            router_response = ctx.agent_executor(router_input)

            data = parse_json_response(router_response, fallback={})

            # ルーター判定を履歴に記録
            session.summaries.append({
                "theme": f"[ルーター判定: {current_theme}の後]",
                "summary": router_response,
            })

            # 終了シグナルの検出
            if data.get("end"):
                logger.info(f"[ConditionalFlow] ルーターが終了を指示: {data.get('reason', '')}")
                # current_theme_index を末尾に強制して all_themes_done = True にする
                session.current_theme_index = len(session.themes)
                break

            # 次のテーマインデックスを解決
            next_idx = data.get("next_theme_index")
            if next_idx is None or not isinstance(next_idx, int):
                # パース失敗 → そのまま順番通りに進む（advance_theme 後の状態）
                logger.warning(f"[ConditionalFlow] ルーターのJSON解析失敗、順番通りに進みます")
            else:
                next_idx = int(next_idx)
                if 0 <= next_idx < len(session.themes):
                    session.current_theme_index = next_idx
                    session.turn_count_in_theme = 0
                    session.last_persona_id = None
                    session.last_task_id = None
                    logger.info(f"[ConditionalFlow] 次のテーマ: {session.themes[next_idx].theme}")
                else:
                    # 範囲外 → 終了
                    logger.info(f"[ConditionalFlow] 範囲外インデックス {next_idx}、終了します")
                    session.current_theme_index = len(session.themes)
                    break

            # 全テーマ完了チェック
            if session.all_themes_done:
                break
