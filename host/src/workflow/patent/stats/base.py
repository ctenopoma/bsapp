"""
workflow/patent/stats/base.py
==============================
統計プロセッサの基底クラスと共通型定義。

新しい統計を追加するには:
1. BaseStatProcessor を継承したクラスを作成
2. process() メソッドを実装（pandas DataFrame を返す）
3. registry.py の REGISTRY に登録
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StatResult:
    """統計処理の結果を保持する。"""
    processor_id: str          # 例: "yearly_count"
    title: str                 # 表示タイトル 例: "年別出願件数"
    df: pd.DataFrame           # 集計結果テーブル
    description: str = ""      # 補足説明（LLMへの文脈として使用可能）
    meta: dict[str, Any] = field(default_factory=dict)  # 追加メタデータ

    def to_markdown(self) -> str:
        """DataFrame をマークダウン表形式に変換する。"""
        if self.df.empty:
            return f"### {self.title}\n\n（データなし）\n"
        table = self.df.to_markdown(index=False)
        lines = [f"### {self.title}"]
        if self.description:
            lines.append(self.description)
        lines.append("")
        lines.append(table)
        return "\n".join(lines)

    def to_text(self) -> str:
        """プレーンテキスト形式（LLMへの変数注入用）。"""
        return self.to_markdown()


@dataclass
class StatParams:
    """LLMが生成した統計処理パラメータ。

    各プロセッサは自分が使うフィールドだけを参照する。
    LLMが生成しない場合はすべて None/空リストになる。
    """
    companies: list[str] = field(default_factory=list)  # 対象企業フィルター（空=全企業）
    year_from: int | None = None                        # 開始年（含む）
    year_to: int | None = None                          # 終了年（含む）
    ipc_sections: list[str] = field(default_factory=list)  # 対象IPCセクション（空=全セクション）
    extra: dict[str, Any] = field(default_factory=dict)    # プロセッサ固有の追加パラメータ

    @classmethod
    def from_llm_json(cls, raw: str) -> "StatParams":
        """LLMが出力したJSON文字列をパースしてStatParamsを返す。パース失敗時はデフォルト値。"""
        import json, re
        # コードブロック内JSONを抽出
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        text = m.group(1).strip() if m else raw.strip()
        # 先頭の { から } までを抽出（余分なテキストが混入しても対応）
        brace = re.search(r"\{[\s\S]*\}", text)
        if not brace:
            return cls()
        try:
            data = json.loads(brace.group(0))
        except Exception:
            return cls()
        return cls(
            companies=data.get("companies") or [],
            year_from=data.get("year_from"),
            year_to=data.get("year_to"),
            ipc_sections=data.get("ipc_sections") or [],
            extra={k: v for k, v in data.items() if k not in ("companies", "year_from", "year_to", "ipc_sections")},
        )


class BaseStatProcessor(ABC):
    """
    統計プロセッサの基底クラス。

    サブクラスは以下を定義すること:
    - processor_id (str): 一意のID（URLセーフな英数字+アンダースコア）
    - title (str): 表示タイトル
    - description (str): 統計の説明
    - param_schema (str): LLMへのパラメータ生成プロンプトに追加するJSON スキーマ説明
    """

    processor_id: str = ""
    title: str = ""
    description: str = ""
    param_schema: str = '{"companies": ["企業名リスト(空=全企業)"], "year_from": 開始年|null, "year_to": 終了年|null}'

    @abstractmethod
    def process(self, rows: list[dict], settings: dict[str, str],
                params: "StatParams | None" = None) -> StatResult:
        """
        CSVの行データを受け取り、統計結果を返す。

        Args:
            rows: CSVの行データのリスト（各行はcolumn名→値のdict）
            settings: 列名設定など {"company_col": "...", "date_col": "...", "content_col": "..."}
            params: LLMが生成したフィルターパラメータ（None=全データ対象）

        Returns:
            StatResult
        """
        ...
