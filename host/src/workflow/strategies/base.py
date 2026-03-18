"""
base.py
=======
テーマストラテジーの基底クラスとデータ構造。

すべてのストラテジーは ThemeStrategy を継承し、run() メソッドを実装する。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from ...models import MessageHistory, AgentInput, Persona
from ...session_manager import SessionMemory


def get_ordered_personas(session: SessionMemory, personas: List[Persona]) -> List[Persona]:
    """persona_order が設定されている場合、その順序でペルソナリストを並び替えて返す。

    - persona_order が空の場合はそのまま返す
    - persona_order に含まれないペルソナはスキップ
    - persona_order のIDが personas に存在しない場合は無視
    """
    theme_config = session.current_theme_config
    if not theme_config or not theme_config.persona_order:
        return personas

    ordered = [p for pid in theme_config.persona_order for p in personas if p.id == pid]
    return ordered if ordered else personas


@dataclass
class StrategyContext:
    """ストラテジー実行に必要な依存オブジェクトをまとめた構造体。"""
    session: SessionMemory
    agent_executor: Callable[[AgentInput], str]
    summarizer: Callable[[SessionMemory], str]


@dataclass
class StrategyResult:
    """ストラテジーの実行結果。"""
    summary: str
    messages: List[MessageHistory] = field(default_factory=list)


class ThemeStrategy(ABC):
    """テーマ内のエージェント連携パターンの基底クラス。

    サブクラスは run() を実装して、1テーマ分のディスカッションを実行する。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """ストラテジーの識別名。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """ストラテジーの説明（UI表示用）。"""
        ...

    @abstractmethod
    def run(self, ctx: StrategyContext) -> str:
        """1テーマ分のディスカッションを実行し、要約テキストを返す。

        Parameters
        ----------
        ctx : StrategyContext
            セッション状態、LLM実行関数、要約関数を含むコンテキスト。

        Returns
        -------
        str
            テーマ全体の要約テキスト。
        """
        ...
