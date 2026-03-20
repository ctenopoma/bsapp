"""
input_builder.py
=================
エージェント1ターン分の入力 (AgentInput) を組み立てるロジック。

★ TASK_SELECTION_STRATEGY を変更するだけでタスク割り当て方法を切り替えられます ★

対応ストラテジー:
  - TaskStrategy.RANDOM      : ランダム選択 (デフォルト)
  - TaskStrategy.ROUND_ROBIN : ターン順にタスクを均等に巡回
  - TaskStrategy.ROLE_MATCH  : ペルソナのロール名に一致するタスクを優先、なければランダム

新しいストラテジーを追加する手順:
  1. TaskStrategy に新しい値を追加
  2. 対応する _assign_xxx 関数を実装
  3. _TASK_STRATEGY_MAP に登録

変更できること (その他):
  - 渡す履歴の件数・圧縮設定 (AppSettings の max_history_tokens / recent_history_count)
  - RAG取得クエリのカスタマイズ
  - output_format の動的変更
"""

import random
from enum import Enum
from typing import Callable, List, Optional

# ------------------------------------------------------------------
# ★ ここを変更してストラテジーを切り替える ★
# ------------------------------------------------------------------
TASK_SELECTION_STRATEGY = "round_robin"
# ------------------------------------------------------------------

from ..models import Persona, AgentInput, TaskModel
from ..session_manager import SessionMemory
from ..rag_manager import rag_manager
from ..app_settings import get_settings, get_max_history_tokens_limit
from .history_compressor import compress_history
from .template_resolver import resolve_template_variables


# ------------------------------------------------------------------
# タスク選択ストラテジー
# ------------------------------------------------------------------

class TaskStrategy(str, Enum):
    RANDOM      = "random"
    ROUND_ROBIN = "round_robin"
    ROLE_MATCH  = "role_match"


def _assign_random(tasks: List[TaskModel], persona: Persona, session: SessionMemory) -> TaskModel:
    """完全ランダム選択。"""
    return random.choice(tasks)


def _assign_round_robin(tasks: List[TaskModel], persona: Persona, session: SessionMemory) -> TaskModel:
    """ターン順にタスクを均等に巡回する。テーマが変わると先頭に戻る。"""
    idx = session.turn_count_in_theme % len(tasks)
    return tasks[idx]


def _assign_role_match(tasks: List[TaskModel], persona: Persona, session: SessionMemory) -> TaskModel:
    """ペルソナのロール名を含むタスクを優先して割り当てる。

    一致するタスクが複数ある場合はその中からランダムに選ぶ。
    一致するタスクがない場合はランダムにフォールバックする。
    """
    matched = [t for t in tasks if persona.role in t.description]
    return random.choice(matched) if matched else random.choice(tasks)


# ストラテジーマップ (新しいストラテジーはここに追加)
_TASK_STRATEGY_MAP: dict[str, Callable[[List[TaskModel], Persona, SessionMemory], TaskModel]] = {
    TaskStrategy.RANDOM:      _assign_random,
    TaskStrategy.ROUND_ROBIN: _assign_round_robin,
    TaskStrategy.ROLE_MATCH:  _assign_role_match,
}


def _select_task(tasks: List[TaskModel], persona: Persona, session: SessionMemory) -> TaskModel:
    theme_cfg = session.current_theme_config
    assignment = (theme_cfg.task_assignment if theme_cfg and theme_cfg.task_assignment else "")

    # fixed モード: ペルソナ→タスク固定マッピング
    if assignment == "fixed" and theme_cfg and theme_cfg.persona_task_map:
        fixed_task_id = theme_cfg.persona_task_map.get(persona.id)
        if fixed_task_id:
            match = next((t for t in tasks if t.id == fixed_task_id), None)
            if match:
                session.last_task_id = match.id
                return match
        # マッピングになければランダムフォールバック
        chosen = random.choice(tasks)
        session.last_task_id = chosen.id
        return chosen

    # テーマ指定 or グローバル設定のストラテジー
    strategy_name = assignment if assignment else TASK_SELECTION_STRATEGY
    strategy_fn = _TASK_STRATEGY_MAP.get(strategy_name, _assign_random)
    chosen = strategy_fn(tasks, persona, session)
    session.last_task_id = chosen.id
    return chosen


# ------------------------------------------------------------------

def build_agent_input(
    session: SessionMemory,
    persona: Persona,
    output_format: str = "",
    stance_prompt: str = "",
) -> AgentInput:
    """セッション状態とペルソナからエージェントへの入力を構築する。

    Parameters
    ----------
    session : SessionMemory
        現在のセッション状態。
    persona : Persona
        今回発言するペルソナ。
    output_format : str, optional
        出力フォーマット文字列。空の場合は DEFAULT_OUTPUT_FORMAT を使用。
    stance_prompt : str, optional
        ストラテジの役割に応じたスタンスプロンプト。空の場合は省略される。

    Returns
    -------
    AgentInput
        LLM呼び出しに渡す入力データ。
    """
    # ------------------------------------------------------------------
    # タスク割り当て (TASK_SELECTION_STRATEGY に従って選択)
    # ------------------------------------------------------------------
    task_description = ""
    if session.tasks:
        assigned_task = _select_task(session.tasks, persona, session)
        task_description = assigned_task.description

    # ------------------------------------------------------------------
    # RAG取得 (ペルソナの rag_config に基づく)
    # rag_type に応じて異なる実装を呼び分ける。
    # ホストに存在しない種別が指定されていた場合はスキップ (不一致は実行時に無視)。
    # ------------------------------------------------------------------
    rag_context = ""
    if persona.rag_config and persona.rag_config.enabled and persona.rag_config.tag:
        rag_type = persona.rag_config.rag_type or "qdrant"
        if rag_type == "qdrant":
            rag_context = rag_manager.search_context(
                tag=persona.rag_config.tag,
                query=session.current_theme,
            )
        # 将来的に他のRAG種別を追加する場合はここに elif を追加:
        # elif rag_type == "other_rag":
        #     rag_context = other_rag_search(...)
        # 不明な種別は無視してRAGをスキップ

    # ------------------------------------------------------------------
    # AgentInput 組み立て
    # ------------------------------------------------------------------
    query = (
        f"{session.common_theme}\n\n{session.current_theme}"
        if session.common_theme
        else session.current_theme
    )

    # セッション共通の事前情報 + テーマ固有の事前情報 + ペルソナ固有の事前情報を結合
    theme_pre_info = (
        session.current_theme_config.pre_info
        if session.current_theme_config
        else ""
    )
    pre_info = "\n\n".join(filter(None, [session.pre_info, theme_pre_info, persona.pre_info]))

    # テンプレート変数 ({{themeN_summary}} 等) を解決
    pre_info = resolve_template_variables(
        text=pre_info,
        summaries=session.summaries,
        history=session.history,
        themes=session.themes,
    )

    # ------------------------------------------------------------------
    # 会話履歴の取得と圧縮
    # max_history_tokens を超える場合、recent_history_count 件より前を要約圧縮する
    # モデルの真の上限 (MAX_HISTORY_TOKENS_LIMIT) を超えないようキャップもかける
    # ------------------------------------------------------------------
    settings = get_settings()
    limit = get_max_history_tokens_limit()
    effective_max = settings.max_history_tokens
    if limit > 0:
        if effective_max <= 0:
            # クライアントが無制限設定した場合もハードリミットでキャップ
            effective_max = limit
        else:
            effective_max = min(effective_max, limit)
    history, history_compressed = compress_history(
        history=session.history,
        recent_count=settings.recent_history_count,
        max_tokens=effective_max,
    )

    return AgentInput(
        persona=persona,
        task=task_description,
        query=query,
        history=history,
        rag_context=rag_context,
        pre_info=pre_info,
        previous_summaries=session.summary_memory,
        stance_prompt=stance_prompt,
        history_compressed=history_compressed,
        output_format=(
            output_format
            or (session.current_theme_config.output_format if session.current_theme_config else "")
            or settings.default_output_format.format(name=persona.name)
        ),
    )
