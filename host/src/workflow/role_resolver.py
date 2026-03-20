"""
role_resolver.py
================
strategy_config 内の role_map / slot_prompts を使って、ペルソナに役割とスタンスを割り当てるユーティリティ。

各ストラテジーは固有の役割名（generator, critic, manager, worker, judge 等）を持つ。
role_map はペルソナIDと役割名のマッピングで、インデックス指定のフォールバックとして機能する。

slot_prompts はストラテジの役割ごとにスタンス（立場・ミッション）プロンプトを定義する。
テーマ × 役割 の組み合わせで異なる指示を与えることができる。

解決優先順 (role_map):
  1. role_map に該当役割のペルソナIDがあればそれを使用
  2. フォールバック: 従来のインデックス指定 (xxx_index)
  3. デフォルトインデックス

使い方:
    from ..role_resolver import resolve_role, resolve_role_group, resolve_stance_prompt

    # 単一の役割を解決
    generator = resolve_role(
        "generator", active, config,
        fallback_index_key="generator_index", default_index=0,
    )

    # 複数ペルソナが担う役割を解決（worker 等）
    workers = resolve_role_group(
        "worker", active, config,
        exclude_ids={manager.id},
    )

    # 役割に対応するスタンスプロンプトを取得
    stance = resolve_stance_prompt("generator", config)
"""

from __future__ import annotations

from typing import List, Optional, Set

from ..models import Persona


def resolve_role(
    role_name: str,
    personas: List[Persona],
    config: dict,
    fallback_index_key: str,
    default_index: int = 0,
) -> Persona:
    """role_map → index → デフォルト の優先順で単一の役割を解決する。

    Parameters
    ----------
    role_name : str
        解決したい役割名（例: "generator", "manager", "judge"）。
    personas : list[Persona]
        アクティブなペルソナリスト。
    config : dict
        strategy_config 辞書。role_map やインデックス設定を含む。
    fallback_index_key : str
        role_map にヒットしない場合に参照するインデックスキー（例: "generator_index"）。
    default_index : int
        fallback_index_key も未設定の場合のデフォルトインデックス。

    Returns
    -------
    Persona
        解決されたペルソナ。
    """
    if not personas:
        raise ValueError("ペルソナリストが空です")

    role_map: dict = config.get("role_map", {})

    # 1a. role_map のキーが役割名の場合（role → persona_id | persona_id[]）
    if role_name in role_map:
        val = role_map[role_name]
        if isinstance(val, list):
            for pid in val:
                match = _find_by_id(personas, str(pid))
                if match is not None:
                    return match
        else:
            match = _find_by_id(personas, str(val))
            if match is not None:
                return match

    # 1b. role_map のキーがペルソナIDの場合（persona_id → role）— 後方互換
    for pid, role in role_map.items():
        if role == role_name:
            match = _find_by_id(personas, pid)
            if match is not None:
                return match

    # 2. フォールバック: インデックス指定
    raw_index = config.get(fallback_index_key)
    if raw_index is not None:
        idx = int(raw_index)
        if idx < 0:
            idx = len(personas) + idx  # 負のインデックス対応（-1 = 最後）
        idx = max(0, min(idx, len(personas) - 1))
        return personas[idx]

    # 3. デフォルトインデックス
    idx = default_index
    if idx < 0:
        idx = len(personas) + idx
    idx = max(0, min(idx, len(personas) - 1))
    return personas[idx]


def resolve_role_group(
    role_name: str,
    personas: List[Persona],
    config: dict,
    exclude_ids: Optional[Set[str]] = None,
) -> List[Persona]:
    """role_map から特定の役割を持つ全ペルソナを取得する。

    role_map に該当がなければ、exclude_ids に含まれないペルソナ全員を返す。

    Parameters
    ----------
    role_name : str
        解決したい役割名（例: "worker", "debater"）。
    personas : list[Persona]
        アクティブなペルソナリスト。
    config : dict
        strategy_config 辞書。
    exclude_ids : set[str] | None
        除外するペルソナIDのセット（role_map に該当がない場合のフォールバック用）。

    Returns
    -------
    list[Persona]
        該当するペルソナのリスト。
    """
    role_map: dict = config.get("role_map", {})
    exclude = exclude_ids or set()

    # role_map のキーが役割名の場合（role → persona_id | persona_id[]）
    if role_name in role_map:
        val = role_map[role_name]
        if isinstance(val, list):
            result = [_find_by_id(personas, str(pid)) for pid in val]
            result = [p for p in result if p is not None]
            if result:
                return result
        else:
            match = _find_by_id(personas, str(val))
            if match is not None:
                return [match]

    # role_map のキーがペルソナIDの場合（persona_id → role）— 後方互換
    matched_ids = [pid for pid, role in role_map.items() if role == role_name]

    if matched_ids:
        result = []
        for pid in matched_ids:
            p = _find_by_id(personas, pid)
            if p is not None:
                result.append(p)
        return result if result else [p for p in personas if p.id not in exclude]

    # role_map に該当なし → exclude_ids 以外の全員
    return [p for p in personas if p.id not in exclude]


def resolve_stance_prompt(role_name: str, config: dict) -> str:
    """strategy_config.slot_prompts から役割に対応するスタンスプロンプトを取得する。

    Parameters
    ----------
    role_name : str
        役割名（例: "generator", "critic", "manager"）。
    config : dict
        strategy_config 辞書。slot_prompts を含む場合がある。

    Returns
    -------
    str
        スタンスプロンプト文字列。未設定の場合は空文字列。

    slot_prompts の構造例::

        {
            "generator": {
                "stance_prompt": "技術的メリットに基づいて推進する立場で主張してください"
            },
            "critic": {
                "stance_prompt": "倫理的リスクの観点から問題点を指摘してください"
            }
        }
    """
    slot_prompts: dict = config.get("slot_prompts", {})
    slot = slot_prompts.get(role_name, {})
    if isinstance(slot, dict):
        return str(slot.get("stance_prompt", ""))
    # 文字列が直接入っている場合も受け付ける
    if isinstance(slot, str):
        return slot
    return ""


def build_flow_role_config(
    theme_flow_role_map: dict,
    flow_config: dict,
) -> dict:
    """テーマ固有の flow_role_map と flow_config._role_defaults をマージした config を構築する。

    テーマの flow_role_map を優先し、未指定の役割は _role_defaults からフォールバックする。
    """
    defaults: dict = flow_config.get("_role_defaults", {})
    merged = {**defaults, **(theme_flow_role_map or {})}
    if not merged:
        return {}
    return {"role_map": merged}


def _find_by_id(personas: List[Persona], persona_id: str) -> Optional[Persona]:
    """ペルソナIDで検索。"""
    for p in personas:
        if p.id == persona_id:
            return p
    return None
