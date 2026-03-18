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

  Phase 3:
  - dynamic_routing   : 動的ルーティング（司会者主導）— 司会者が文脈を読んで次の発言者を動的に指名する
  - map_reduce        : 分割統治（Map-Reduce）— プランナーがタスクを分割し、ワーカーが個別処理し、サマライザーが統合する
  - dynamic_generation: 動的エージェント生成 — メタエージェントが議題に最適なペルソナをその場で生成して議論する
"""

from .base import ThemeStrategy, StrategyContext, StrategyResult, get_ordered_personas
from .sequential import SequentialStrategy
from .parallel import ParallelStrategy
from .round_robin_debate import RoundRobinDebateStrategy
from .hierarchical import HierarchicalStrategy
from .adversarial import AdversarialStrategy
from .judge_jury import JudgeJuryStrategy
from .dynamic_routing import DynamicRoutingStrategy
from .map_reduce import MapReduceStrategy
from .dynamic_generation import DynamicGenerationStrategy

# ストラテジー名 → クラスのマッピング
STRATEGY_MAP: dict[str, type[ThemeStrategy]] = {
    "sequential": SequentialStrategy,
    "parallel": ParallelStrategy,
    "round_robin_debate": RoundRobinDebateStrategy,
    "hierarchical": HierarchicalStrategy,
    "adversarial": AdversarialStrategy,
    "judge_jury": JudgeJuryStrategy,
    "dynamic_routing": DynamicRoutingStrategy,
    "map_reduce": MapReduceStrategy,
    "dynamic_generation": DynamicGenerationStrategy,
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
