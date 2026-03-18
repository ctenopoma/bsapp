"""
map_reduce.py
=============
8. 分割統治（Map-Reduce）ストラテジー。

プランナーが議題をサブタスクに分割し、ワーカーが個別に処理し、
サマライザーが全結果を統合する。

動作フロー:
  1. プランナーがサブタスクを JSON で生成:
       {"subtasks": ["サブタスク1", "サブタスク2", ...]}
  2. 各ワーカーがサブタスクを独立して実行
     （ワーカー数 < サブタスク数の場合はラウンドロビンで割り当て）
  3. サマライザーが全結果を統合する発言を生成
  4. 要約生成

設定項目 (ThemeConfig.strategy_config):
  - planner_index    : プランナー役のインデックス（デフォルト: 0）
  - summarizer_index : サマライザー役のインデックス（デフォルト: -1 = 最後のペルソナ）
  - max_subtasks     : 最大サブタスク数（デフォルト: 5）
"""

import uuid

from ...models import MessageHistory
from ..input_builder import build_agent_input
from ..json_utils import parse_json_response
from .base import ThemeStrategy, StrategyContext, get_ordered_personas

# プランナー用プロンプト
PLANNER_PROMPT_TEMPLATE = """\

議題を最大 {max_subtasks} 個のサブタスクに分割してください。
各サブタスクは独立して処理できる具体的な問いや作業にしてください。

以下の JSON 形式のみで回答してください（前後の説明は不要です）:
{{"subtasks": ["サブタスク1", "サブタスク2", ...]}}
"""

# サマライザー用プロンプト
SUMMARIZER_PROMPT_TEMPLATE = """\

--- 各ワーカーの処理結果 ---
{worker_results}
---

上記の各サブタスクの結果を統合し、議題全体への包括的な回答をまとめてください。
重複を除去し、矛盾があれば整理して、一貫性のある最終成果物を作成してください。
"""


class MapReduceStrategy(ThemeStrategy):

    @property
    def name(self) -> str:
        return "map_reduce"

    @property
    def description(self) -> str:
        return "分割統治（Map-Reduce）: プランナーがタスクを分割し、ワーカーが個別処理し、サマライザーが統合します。"

    def run(self, ctx: StrategyContext) -> str:
        session = ctx.session
        active = get_ordered_personas(session, session.active_personas)
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

        config = {}
        if session.current_theme_config and session.current_theme_config.strategy_config:
            config = session.current_theme_config.strategy_config

        planner_index = min(int(config.get("planner_index", 0)), len(active) - 1)
        raw_summarizer = int(config.get("summarizer_index", -1))
        summarizer_index = len(active) - 1 if raw_summarizer < 0 else min(raw_summarizer, len(active) - 1)
        # planner と summarizer が同じ場合は summarizer を隣にずらす
        if summarizer_index == planner_index and len(active) > 1:
            summarizer_index = (planner_index + 1) % len(active)
        max_subtasks = max(1, int(config.get("max_subtasks", 5)))

        planner = active[planner_index]
        summarizer = active[summarizer_index]
        workers = [p for i, p in enumerate(active) if i not in (planner_index, summarizer_index)]
        # ワーカーが 0 人の場合はプランナー以外全員
        if not workers:
            workers = [p for p in active if p.id != planner.id]
        if not workers:
            workers = active  # 全員でフォールバック

        # ------------------------------------------------------------------
        # Step 1: プランナーがサブタスクを JSON で生成
        # ------------------------------------------------------------------
        plan_input = build_agent_input(session, planner)
        plan_input.query += PLANNER_PROMPT_TEMPLATE.format(max_subtasks=max_subtasks)
        plan_response = ctx.agent_executor(plan_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{planner.name}（プランナー）",
            content=plan_response,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        # サブタスク取得（パース失敗時は議題全体をそのまま1サブタスクとして扱う）
        plan_data = parse_json_response(plan_response, fallback={})
        subtasks: list[str] = plan_data.get("subtasks", [])
        if not subtasks or not isinstance(subtasks, list):
            subtasks = [session.current_theme]
        subtasks = [str(t) for t in subtasks[:max_subtasks]]

        # ------------------------------------------------------------------
        # Step 2: 各ワーカーがサブタスクを処理（ラウンドロビン割り当て）
        # ------------------------------------------------------------------
        worker_results: list[tuple[str, str, str]] = []  # (subtask, worker_name, result)

        for task_idx, subtask in enumerate(subtasks):
            worker = workers[task_idx % len(workers)]
            worker_input = build_agent_input(session, worker)
            worker_input.query += f"\n\n【担当サブタスク】\n{subtask}"
            result = ctx.agent_executor(worker_input)

            msg = MessageHistory(
                id=uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=f"{worker.name}（ワーカー: サブタスク{task_idx + 1}）",
                content=result,
                turn_order=session.turn_count_in_theme,
            )
            session.history.append(msg)
            session.turn_count_in_theme += 1
            worker_results.append((subtask, worker.name, result))

        # ------------------------------------------------------------------
        # Step 3: サマライザーが全結果を統合
        # ------------------------------------------------------------------
        worker_results_text = "\n\n".join(
            f"【サブタスク {i + 1}: {subtask}】\n担当: {worker_name}\n{result}"
            for i, (subtask, worker_name, result) in enumerate(worker_results)
        )
        summarizer_input = build_agent_input(session, summarizer)
        summarizer_input.query += SUMMARIZER_PROMPT_TEMPLATE.format(
            worker_results=worker_results_text,
        )
        summary_message = ctx.agent_executor(summarizer_input)

        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=f"{summarizer.name}（サマライザー）",
            content=summary_message,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        return ctx.summarizer(session)
