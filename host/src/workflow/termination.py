"""
termination.py
==============
ストラテジー共通の終了制御ユーティリティ。

JSON構造化評価の標準スキーマ:
    {
        "pass": bool,         # 合格/続行の判定
        "complete": bool,     # プロセス全体の完了判定（早期終了用）
        "feedback": str,      # 理由・フィードバック
        "next_action": str    # オプション: "revise" | "proceed" | "escalate"
    }

使い方:
    checker = TerminationChecker(config)

    eval_result = checker.parse_evaluation(llm_output)
    if checker.is_complete(eval_result):
        break  # 早期終了

    if not eval_result.get("pass", True):
        if checker.should_force_proceed():
            # リトライ上限到達 → 強制的に次フェーズへ
            ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .json_utils import parse_json_response

# テキスト内の終了タグパターン（JSON 評価と併用可能）
_COMPLETION_TAG_RE = re.compile(r"\[COMPLETE\]|\[APPROVED\]|\[DONE\]", re.IGNORECASE)


# デフォルトの評価結果（パース失敗時）: 合格扱いでループを止める
_DEFAULT_EVALUATION = {"pass": True, "complete": False, "feedback": "", "next_action": "proceed"}


@dataclass
class TerminationChecker:
    """ストラテジーのループ終了を判定するヘルパー。

    Parameters
    ----------
    config : dict
        strategy_config 辞書。以下のキーを参照:
        - max_retry_per_phase : int (default: 3)
            同一フェーズ内のリトライ上限。
    """
    config: dict = field(default_factory=dict)
    retry_count: int = field(default=0, init=False)

    @property
    def max_retry(self) -> int:
        return int(self.config.get("max_retry_per_phase", 3))

    def parse_evaluation(self, output: str) -> dict[str, Any]:
        """LLM出力からJSON評価結果をパースする。

        パース失敗時は {"pass": True, "complete": False} を返してループを止める。
        """
        result = parse_json_response(output, fallback=None)
        if result is None or not isinstance(result, dict):
            return dict(_DEFAULT_EVALUATION)

        # 標準フィールドを正規化
        normalized = {
            "pass": bool(result.get("pass", True)),
            "complete": bool(result.get("complete", False)),
            "feedback": str(result.get("feedback", "")),
            "next_action": str(result.get("next_action", "proceed")),
        }
        return normalized

    def is_complete(self, eval_result: dict) -> bool:
        """プロセス全体の完了判定。"""
        return eval_result.get("complete", False)

    def increment_retry(self) -> None:
        """リトライカウンタを1増やす。"""
        self.retry_count += 1

    def should_force_proceed(self) -> bool:
        """リトライ上限に達したかどうかを判定する。

        呼び出し側で increment_retry() を先に呼ぶこと。
        """
        return self.retry_count >= self.max_retry

    def reset_retry(self) -> None:
        """リトライカウンタをリセットする。"""
        self.retry_count = 0

    @staticmethod
    def has_completion_tag(output: str) -> bool:
        """LLM出力テキストに終了タグ ([COMPLETE], [APPROVED], [DONE]) が含まれるか判定する。

        JSON 評価方式と併用可能。シンプルなストラテジーではこちらだけで終了判定できる。
        """
        return bool(_COMPLETION_TAG_RE.search(output))
