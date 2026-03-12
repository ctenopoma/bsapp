"""
persona_selector.py
====================
次に発言するペルソナを選ぶロジック。

★ ここを書き換えることで発言順序を自由に制御できます ★

カスタマイズ例:
  - ラウンドロビン: personas[session.turn_count_in_theme % len(personas)]
  - 役割ベース: 最初はリーダー役、その後は他のペルソナを交互に
  - LLMによるオーケストレーター: LLMが「次は誰が発言すべきか」を判断
"""

import random
from typing import List

from ..models import Persona
from ..session_manager import SessionMemory


def select_persona(personas: List[Persona], session: SessionMemory) -> Persona:
    """次に発言するペルソナを返す。

    Parameters
    ----------
    personas : List[Persona]
        現在のテーマで有効なペルソナ一覧。
    session : SessionMemory
        現在のセッション状態 (turn_count_in_theme などを参照可)。

    Returns
    -------
    Persona
        次に発言させるペルソナ。
    """
    # -----------------------------------------------------------------
    # デフォルト: ランダム選択
    # -----------------------------------------------------------------
    return random.choice(personas)

    # -----------------------------------------------------------------
    # カスタマイズ例1: ラウンドロビン (コメントアウト解除して使用)
    # -----------------------------------------------------------------
    # idx = session.turn_count_in_theme % len(personas)
    # return personas[idx]

    # -----------------------------------------------------------------
    # カスタマイズ例2: 特定ロールを優先 (コメントアウト解除して使用)
    # -----------------------------------------------------------------
    # leaders = [p for p in personas if "リーダー" in p.role]
    # if leaders and session.turn_count_in_theme == 0:
    #     return leaders[0]
    # return random.choice(personas)
