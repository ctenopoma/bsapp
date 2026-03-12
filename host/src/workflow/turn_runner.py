"""
turn_runner.py
===============
1テーマ分のターン実行ループ。

★ ここを書き換えることでディスカッションの進め方を変更できます ★

変更できること:
  - ターン数の動的変更 (条件に応じて早期終了など)
  - ターン間への追加処理 (モデレーターの挿入、外部通知など)
  - 特定ペルソナへの優先発言権付与
  - 発言内容に応じた分岐処理
"""

import uuid

from ..models import MessageHistory
from ..session_manager import SessionMemory
from .persona_selector import select_persona
from .input_builder import build_agent_input


def run_one_theme(session: SessionMemory, agent_executor, summarizer) -> str:
    """現在のテーマを turns_per_theme ターン実行し、要約テキストを返す。

    Parameters
    ----------
    session : SessionMemory
        現在のセッション状態。
    agent_executor : Callable[[AgentInput], str]
        1ターン分のLLM呼び出しを行う関数。
        AgentInput を受け取り、エージェントの発言文字列を返す。
    summarizer : Callable[[SessionMemory], str]
        要約生成関数。SessionMemory を受け取り要約文字列を返す。

    Returns
    -------
    str
        テーマ全体の要約テキスト。
    """
    active = session.active_personas
    if not active:
        raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")

    # ------------------------------------------------------------------
    # ターンループ
    # ------------------------------------------------------------------
    for _ in range(session.turns_per_theme):
        # 1. 発言者を選ぶ
        persona = select_persona(active, session)

        # 2. エージェントへの入力を組み立てる
        agent_input = build_agent_input(session, persona)

        # 3. LLMを呼び出して発言を得る
        message = agent_executor(agent_input)

        # 4. 発言を履歴に追記
        session.history.append(MessageHistory(
            id=uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=persona.name,
            content=message,
            turn_order=session.turn_count_in_theme,
        ))
        session.turn_count_in_theme += 1

        # ------------------------------------------------------------------
        # カスタマイズ例: ターン後フック (コメントアウト解除して使用)
        # ------------------------------------------------------------------
        # ここにターン後の追加処理を入れられます
        # 例: print(f"[Turn {session.turn_count_in_theme}] {persona.name}: {message[:50]}...")

    # ------------------------------------------------------------------
    # 全ターン完了後に要約生成
    # ------------------------------------------------------------------
    return summarizer(session)
