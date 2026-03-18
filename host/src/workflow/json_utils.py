"""
json_utils.py
=============
LLM応答からJSON構造化出力をパース・バリデーション・フォールバックするユーティリティ。

Phase 3 の動的ルーティング / Map-Reduce / 動的エージェント生成など、
LLM にJSON出力を要求するストラテジーで共通利用する。

使い方:
    result = parse_json_response(llm_output, fallback={})
    # {"key": "value"} 形式でパース、失敗時は {} を返す
"""

import json
import re
from typing import Any


def parse_json_response(text: str, fallback: Any = None) -> Any:
    """LLM 応答テキストから最初の JSON オブジェクト/配列を取り出してパースする。

    対応形式:
    - 素の JSON: {"key": "value"}
    - コードブロック: ```json\\n{...}\\n```
    - 前後に説明文がある場合: "説明... \\n```json\\n{...}\\n```"

    Parameters
    ----------
    text : str
        LLM の生応答テキスト。
    fallback : Any, optional
        パース失敗時に返す値（デフォルト: None）。

    Returns
    -------
    Any
        パース成功時はデコードされた Python オブジェクト、失敗時は fallback。
    """
    try:
        # コードブロックのフェンスを除去
        cleaned = re.sub(r"```[a-z]*\n?", "", text)
        cleaned = re.sub(r"```", "", cleaned).strip()

        # 最初の { ... } または [ ... ] を取り出す（ネスト対応のため最外側を探す）
        for pattern in (r"\{.*\}", r"\[.*\]"):
            match = re.search(pattern, cleaned, re.DOTALL)
            if match:
                return json.loads(match.group())
    except Exception:
        pass

    return fallback
