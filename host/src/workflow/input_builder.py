"""
input_builder.py
=================
エージェント1ターン分の入力 (AgentInput) を組み立てるロジック。

★ ここを書き換えることで各エージェントへ渡す情報を変更できます ★

変更できること:
  - 渡す履歴の件数・圧縮設定 (AppSettings の max_history_tokens / recent_history_count)
  - タスク割り当て方法 (ランダム → 役割ベース など)
  - RAG取得クエリのカスタマイズ
  - output_format の動的変更
"""

import random

from ..models import Persona, AgentInput
from ..session_manager import SessionMemory
from ..rag_manager import rag_manager
from ..app_settings import get_settings
from .history_compressor import compress_history


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

    # セッション共通の事前情報とペルソナ固有の事前情報を結合
    pre_info = "\n\n".join(filter(None, [session.pre_info, persona.pre_info]))

    # ------------------------------------------------------------------
    # 会話履歴の取得と圧縮
    # max_history_tokens を超える場合、recent_history_count 件より前を要約圧縮する
    # ------------------------------------------------------------------
    settings = get_settings()
    history = compress_history(
        history=session.history,
        recent_count=settings.recent_history_count,
        max_tokens=settings.max_history_tokens,
    )

    return AgentInput(
        persona=persona,
        task=task_description,
        query=query,
        history=history,
        rag_context=rag_context,
        pre_info=pre_info,
        previous_summaries=session.summary_memory,
        output_format=(
            output_format
            or (session.current_theme_config.output_format if session.current_theme_config else "")
            or settings.default_output_format.format(name=persona.name)
        ),
    )
