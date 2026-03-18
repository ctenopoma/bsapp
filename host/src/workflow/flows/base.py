"""
base.py
=======
マクロワークフロー（フロー）の基底クラスとデータ構造。

すべてのフローは ProjectFlow を継承し、run() メソッドを実装する。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from ...session_manager import SessionMemory
from ...models import AgentInput


@dataclass
class FlowContext:
    """フロー実行に必要な依存オブジェクト。"""
    session: SessionMemory
    run_one_theme_fn: Callable[[SessionMemory], str]
    """1テーマ分を実行して要約テキストを返す関数。"""
    agent_executor: Callable[[AgentInput], str]
    """1ターン分のLLM呼び出しを行う関数（ゲートキーパー・判定者・ルーター用）。"""
    summarizer: Callable[[SessionMemory], str]
    """現在のテーマを要約する関数。"""


class ProjectFlow(ABC):
    """テーマ間の進行制御パターン（マクロワークフロー）の基底クラス。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """フローの識別名。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """フローの説明（UI表示用）。"""
        ...

    @abstractmethod
    def run(self, ctx: FlowContext) -> None:
        """全テーマを実行する。

        各テーマの要約は session.advance_theme() で保存する。
        完了後は session.all_themes_done が True になっていること。

        Parameters
        ----------
        ctx : FlowContext
            セッション状態、テーマ実行関数、LLM実行関数、要約関数を含むコンテキスト。
        """
        ...
