"""
flows パッケージ
===============
マクロワークフロー（テーマ間の進行制御）を定義。

利用可能なフロー:
  - waterfall   : ウォーターフォール型 — テーマを順番に実行（デフォルト）
  - stage_gate  : ステージゲート型 — テーマ間にゲートキーパー判定を挟む
  - agile_sprint: アジャイル/スプリント型 — テーマ群を1スプリントとして複数回ループ
  - conditional : 条件分岐/ツリー型 — テーマの結論によって次のテーマが分岐
"""

from .base import ProjectFlow, FlowContext
from .waterfall import WaterfallFlow
from .stage_gate import StageGateFlow
from .agile_sprint import AgileSprintFlow
from .conditional import ConditionalFlow

FLOW_MAP: dict[str, type[ProjectFlow]] = {
    "waterfall": WaterfallFlow,
    "stage_gate": StageGateFlow,
    "agile_sprint": AgileSprintFlow,
    "conditional": ConditionalFlow,
}


def get_flow(name: str) -> ProjectFlow:
    """フロー名からインスタンスを生成して返す。未知の名前は waterfall にフォールバック。"""
    cls = FLOW_MAP.get(name, WaterfallFlow)
    return cls()


__all__ = [
    "ProjectFlow",
    "FlowContext",
    "FLOW_MAP",
    "get_flow",
]
