"""
persona_selector.py
====================
次に発言するペルソナを選ぶロジック。

★ PERSONA_SELECTION_STRATEGY を変更するだけで選択方法を切り替えられます ★

対応ストラテジー:
  - PersonaStrategy.RANDOM      : ランダム選択 (デフォルト)
  - PersonaStrategy.ROUND_ROBIN : ターン順に全ペルソナを均等に巡回
  - PersonaStrategy.ROLE_FIRST  : 役割キーワードを持つペルソナを最初に優先、以降はラウンドロビン

新しいストラテジーを追加する手順:
  1. PersonaStrategy に新しい値を追加
  2. 対応する _select_xxx 関数を実装
  3. _STRATEGY_MAP に登録
"""

import random
from enum import Enum
from typing import Callable, List

from ..models import Persona
from ..session_manager import SessionMemory

# ------------------------------------------------------------------
# ★ ここを変更してストラテジーを切り替える ★
# ------------------------------------------------------------------
PERSONA_SELECTION_STRATEGY = "round_robin"
# ------------------------------------------------------------------


class PersonaStrategy(str, Enum):
    RANDOM      = "random"
    ROUND_ROBIN = "round_robin"
    ROLE_FIRST  = "role_first"


# ------------------------------------------------------------------
# ストラテジー実装
# ------------------------------------------------------------------

def _select_random(personas: List[Persona], session: SessionMemory) -> Persona:
    """完全ランダム選択。"""
    return random.choice(personas)


def _select_round_robin(personas: List[Persona], session: SessionMemory) -> Persona:
    """全ペルソナを順番に巡回する。テーマが変わると先頭に戻る。"""
    idx = session.turn_count_in_theme % len(personas)
    return personas[idx]


def _select_role_first(personas: List[Persona], session: SessionMemory) -> Persona:
    """最初のターンだけ「リーダー」ロールを優先し、以降はラウンドロビン。

    ロールに ROLE_FIRST_KEYWORD が含まれるペルソナが存在しない場合は
    ラウンドロビンにフォールバックする。
    """
    ROLE_FIRST_KEYWORD = "リーダー"

    if session.turn_count_in_theme == 0:
        leaders = [p for p in personas if ROLE_FIRST_KEYWORD in p.role]
        if leaders:
            return leaders[0]

    # リーダー以降はラウンドロビン (前回と同じペルソナを避けるためオフセット調整)
    candidates = [p for p in personas if p.id != session.last_persona_id] or personas
    idx = session.turn_count_in_theme % len(candidates)
    return candidates[idx]


# ------------------------------------------------------------------
# ストラテジーマップ (新しいストラテジーはここに追加)
# ------------------------------------------------------------------
_STRATEGY_MAP: dict[str, Callable[[List[Persona], SessionMemory], Persona]] = {
    PersonaStrategy.RANDOM:      _select_random,
    PersonaStrategy.ROUND_ROBIN: _select_round_robin,
    PersonaStrategy.ROLE_FIRST:  _select_role_first,
}


# ------------------------------------------------------------------
# 公開インターフェース
# ------------------------------------------------------------------

def select_persona(personas: List[Persona], session: SessionMemory) -> Persona:
    """次に発言するペルソナを返す。

    PERSONA_SELECTION_STRATEGY の値に従って選択方法を切り替える。

    Parameters
    ----------
    personas : List[Persona]
        現在のテーマで有効なペルソナ一覧。
    session : SessionMemory
        現在のセッション状態。

    Returns
    -------
    Persona
        次に発言させるペルソナ。
    """
    strategy_fn = _STRATEGY_MAP.get(PERSONA_SELECTION_STRATEGY)
    if strategy_fn is None:
        raise ValueError(
            f"未知の PERSONA_SELECTION_STRATEGY: '{PERSONA_SELECTION_STRATEGY}'. "
            f"有効な値: {list(_STRATEGY_MAP.keys())}"
        )

    chosen = strategy_fn(personas, session)
    session.last_persona_id = chosen.id
    return chosen
