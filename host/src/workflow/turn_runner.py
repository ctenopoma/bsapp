"""
turn_runner.py
===============
1テーマ分のターン実行。ストラテジーパターンで連携方式を切り替える。

★ ThemeConfig.theme_strategy でストラテジーを指定 ★
  - "sequential"        : シーケンシャル（バトンリレー）— デフォルト
  - "parallel"          : 並列独立（ブレスト）
  - "round_robin_debate": ラウンドロビン（順番ディベート）

ThemeConfig.strategy_config で各ストラテジー固有のパラメータを渡す。
"""

from ..session_manager import SessionMemory
from .strategies import get_strategy, StrategyContext


def run_one_theme(session: SessionMemory, agent_executor, summarizer) -> str:
    """現在のテーマをストラテジーに従って実行し、要約テキストを返す。

    Parameters
    ----------
    session : SessionMemory
        現在のセッション状態。
    agent_executor : Callable[[AgentInput], str]
        1ターン分のLLM呼び出しを行う関数。
    summarizer : Callable[[SessionMemory], str]
        要約生成関数。

    Returns
    -------
    str
        テーマ全体の要約テキスト。
    """
    # テーマごとのストラテジー名を取得（未設定なら sequential）
    strategy_name = "sequential"
    if session.current_theme_config and session.current_theme_config.theme_strategy:
        strategy_name = session.current_theme_config.theme_strategy

    strategy = get_strategy(strategy_name)
    # summarize=False のテーマは要約をスキップして空文字を返す
    should_summarize = True
    if session.current_theme_config is not None:
        should_summarize = session.current_theme_config.summarize
    effective_summarizer = summarizer if should_summarize else lambda _: ""
    ctx = StrategyContext(
        session=session,
        agent_executor=agent_executor,
        summarizer=effective_summarizer,
    )
    return strategy.run(ctx)
