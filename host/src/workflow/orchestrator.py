"""
orchestrator.py
===============
マクロフロー・ディスパッチャー。

session.project_flow に基づいて適切な ProjectFlow を選択し、
全テーマの実行を委譲する。

agent_runner.py の run_full_session_background() からここに委譲することで、
テーマ間の進行制御ロジックを agent_runner から分離している。
"""

from ..session_manager import SessionMemory
from .flows import get_flow, FlowContext
from .turn_runner import run_one_theme


def run_full_session(
    session: SessionMemory,
    agent_executor,
    summarizer,
) -> None:
    """全テーマを session.project_flow に従って実行する。

    Parameters
    ----------
    session : SessionMemory
        現在のセッション状態。
    agent_executor : Callable[[AgentInput], str]
        1ターン分のLLM呼び出しを行う関数。
    summarizer : Callable[[SessionMemory], str]
        テーマ要約関数。
    """
    flow_name = session.project_flow or "waterfall"
    flow = get_flow(flow_name)

    def run_one_theme_fn(s: SessionMemory) -> str:
        return run_one_theme(
            session=s,
            agent_executor=agent_executor,
            summarizer=summarizer,
        )

    ctx = FlowContext(
        session=session,
        run_one_theme_fn=run_one_theme_fn,
        agent_executor=agent_executor,
        summarizer=summarizer,
    )

    flow.run(ctx)
