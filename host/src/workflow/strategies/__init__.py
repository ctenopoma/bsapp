"""
strategies パッケージ
====================
テーマ内のエージェント連携パターン（ミクロワークフロー）を定義。

利用可能なストラテジー:
  Phase 1:
  - sequential        : シーケンシャル（バトンリレー）— 順番にターンを実行
  - parallel          : 並列独立（ブレスト）— 全員が独立して発言し、ファシリテーターが集約
  - round_robin_debate: ラウンドロビン（順番ディベート）— 全員が発言するループを複数回回す

  Phase 2:
  - hierarchical      : 階層型（計画・実行・反省）— マネージャーが計画し、ワーカーが実行し、評価・修正を繰り返す
  - adversarial       : 敵対的・レッドチーム（生成・批判）— 生成役と批判役が交互に発言し提案を改善する
  - judge_jury        : 陪審員・裁判官（Judge & Jury）— ディベーター間で議論し、裁判官が最終判定を下す
"""

from .base import ThemeStrategy, StrategyContext, StrategyResult, get_ordered_personas
from .sequential import SequentialStrategy
from .parallel import ParallelStrategy
from .round_robin_debate import RoundRobinDebateStrategy
from .hierarchical import HierarchicalStrategy
from .adversarial import AdversarialStrategy
from .judge_jury import JudgeJuryStrategy

# ストラテジー名 → クラスのマッピング
STRATEGY_MAP: dict[str, type[ThemeStrategy]] = {
    "sequential": SequentialStrategy,
    "parallel": ParallelStrategy,
    "round_robin_debate": RoundRobinDebateStrategy,
    "hierarchical": HierarchicalStrategy,
    "adversarial": AdversarialStrategy,
    "judge_jury": JudgeJuryStrategy,
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
    "get_ordered_personas",
    "STRATEGY_MAP",
    "get_strategy",
]
