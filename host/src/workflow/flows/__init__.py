"""
flows パッケージ
===============
マクロワークフロー（テーマ間の進行制御）を定義。

利用可能なフロー:
  - waterfall   : ウォーターフォール型 — テーマを順番に実行（デフォルト）
  - v_shape     : V字型 — 全テーマ実行後に逆順でレビュー
  - stage_gate  : ステージゲート型 — テーマ間にゲートキーパー判定を挟む
  - agile_sprint: アジャイル/スプリント型 — テーマ群を1スプリントとして複数回ループ
  - conditional : 条件分岐/ツリー型 — テーマの結論によって次のテーマが分岐
  - game_theory : ゲーム理論/対立型 — 提案陣営と批判陣営が対立議論し合意案を導く
  - blackboard  : ブラックボード型 — コーディネーターが動的に担当エージェントを指名
  - tournament  : トーナメント/進化型 — 同一プロジェクトを複数回実行し最良を選出
"""

from .base import ProjectFlow, FlowContext
from .waterfall import WaterfallFlow
from .v_shape import VShapeFlow
from .stage_gate import StageGateFlow
from .agile_sprint import AgileSprintFlow
from .conditional import ConditionalFlow
from .game_theory import GameTheoryFlow
from .blackboard import BlackboardFlow
from .tournament import TournamentFlow

FLOW_MAP: dict[str, type[ProjectFlow]] = {
    "waterfall": WaterfallFlow,
    "v_shape": VShapeFlow,
    "stage_gate": StageGateFlow,
    "agile_sprint": AgileSprintFlow,
    "conditional": ConditionalFlow,
    "game_theory": GameTheoryFlow,
    "blackboard": BlackboardFlow,
    "tournament": TournamentFlow,
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
