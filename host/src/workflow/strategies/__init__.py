"""
strategies パッケージ
====================
テーマ内のエージェント連携パターン（ミクロワークフロー）を定義。

利用可能なストラテジー:
  - sequential   : シーケンシャル（バトンリレー）— 順番にターンを実行
  - parallel     : 並列独立（ブレスト）— 全員が独立して発言し、ファシリテーターが集約
  - round_robin  : ラウンドロビン（順番ディベート）— 全員が発言するループを複数回回す
"""

from .base import ThemeStrategy, StrategyContext, StrategyResult
from .sequential import SequentialStrategy
from .parallel import ParallelStrategy
from .round_robin_debate import RoundRobinDebateStrategy

# ストラテジー名 → クラスのマッピング
STRATEGY_MAP: dict[str, type[ThemeStrategy]] = {
    "sequential": SequentialStrategy,
    "parallel": ParallelStrategy,
    "round_robin_debate": RoundRobinDebateStrategy,
}


def get_strategy(name: str) -> ThemeStrategy:
    """ストラテジー名からインスタンスを生成して返す。"""
    cls = STRATEGY_MAP.get(name)
    if cls is None:
        raise ValueError(
            f"未知のテーマストラテジー: '{name}'. "
            f"有効な値: {list(STRATEGY_MAP.keys())}"
        )
    return cls()


__all__ = [
    "ThemeStrategy",
    "StrategyContext",
    "StrategyResult",
    "STRATEGY_MAP",
    "get_strategy",
]
