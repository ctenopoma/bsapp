"""
input_builder.py
=================
エージェント1ターン分の入力 (AgentInput) を組み立てるロジック。

★ ここを書き換えることで各エージェントへ渡す情報を変更できます ★

変更できること:
  - 渡す履歴の件数 (history[-5:] の数を変更)
  - タスク割り当て方法 (ランダム → 役割ベース など)
  - RAG取得クエリのカスタマイズ
  - output_format の動的変更
"""

import random

from ..models import Persona, AgentInput
from ..session_manager import SessionMemory
from ..rag_manager import rag_manager
from ..app_settings import get_settings


def build_agent_input(
    session: SessionMemory,
    persona: Persona,
    output_format: str = "",
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

    Returns
    -------
    AgentInput
        LLM呼び出しに渡す入力データ。
    """
    # ------------------------------------------------------------------
    # タスク割り当て (デフォルト: ランダム選択)
    # ------------------------------------------------------------------
    task_description = ""
    if session.tasks:
        assigned_task = random.choice(session.tasks)
        task_description = assigned_task.description

    # ------------------------------------------------------------------
    # RAG取得 (ペルソナの rag_config に基づく)
    # ------------------------------------------------------------------
    rag_context = ""
    if persona.rag_config and persona.rag_config.enabled and persona.rag_config.tag:
        rag_context = rag_manager.search_context(
            tag=persona.rag_config.tag,
            query=session.current_theme,
        )

    # ------------------------------------------------------------------
    # AgentInput 組み立て
    # ------------------------------------------------------------------
    query = (
        f"{session.common_theme}\n\n{session.current_theme}"
        if session.common_theme
        else session.current_theme
    )

    # セッション共通の事前情報とペルソナ固有の事前情報を結合
    pre_info = "\n\n".join(filter(None, [session.pre_info, persona.pre_info]))

    return AgentInput(
        persona=persona,
        task=task_description,
        query=query,
        history=session.history[-5:],   # ← 渡す履歴件数をここで調整
        rag_context=rag_context,
        pre_info=pre_info,
        previous_summaries=session.summary_memory,
        output_format=(
            output_format
            or (session.current_theme_config.output_format if session.current_theme_config else "")
            or get_settings().default_output_format.format(name=persona.name)
        ),
    )
