"""
workflow/patent/stats/ipc_distribution.py
==========================================
IPC（国際特許分類）分布の統計プロセッサ。
"""

from __future__ import annotations

import re

import pandas as pd

from .base import BaseStatProcessor, StatResult, StatParams

# IPC分類は通常 "H01L 21/00" のような形式。大分類はアルファベット1文字+数字2桁
_IPC_SECTION_RE = re.compile(r"\b([A-H]\d{2}[A-Z]?)\b")


class IpcDistributionProcessor(BaseStatProcessor):
    processor_id = "ipc_distribution"
    title = "IPC分類分布"
    description = "IPC（国際特許分類）の大分類ごとの出願件数を集計します。IPC列が存在しない場合は処理をスキップします。"

    # IPC大分類（セクション）の名称
    IPC_SECTION_NAMES = {
        "A": "生活必需品",
        "B": "処理操作・運輸",
        "C": "化学・冶金",
        "D": "繊維・紙",
        "E": "固定構造物",
        "F": "機械工学・照明・加熱・武器・爆破",
        "G": "物理学",
        "H": "電気",
    }

    param_schema = '{"companies": ["対象企業リスト(空=全企業)"], "ipc_sections": ["対象IPCセクション(例:H,G)(空=全セクション)"]}'

    def process(self, rows: list[dict], settings: dict[str, str],
                params: StatParams | None = None) -> StatResult:
        filter_companies = set(params.companies) if params and params.companies else set()
        filter_sections = set(params.ipc_sections) if params and params.ipc_sections else set()
        # IPC列の候補を探す（設定か、よくある列名）
        ipc_col = settings.get("ipc_col", "")
        if not ipc_col:
            candidates = ["IPC", "ipc", "国際特許分類", "FI", "fi", "分類"]
            for c in candidates:
                if rows and c in rows[0]:
                    ipc_col = c
                    break

        if not ipc_col:
            return StatResult(
                processor_id=self.processor_id,
                title=self.title,
                df=pd.DataFrame(),
                description="IPC分類列が見つかりません。設定でipc_colを指定してください。",
            )

        # IPC値を解析
        section_counts: dict[str, int] = {}
        subclass_counts: dict[str, int] = {}
        company_col = settings.get("company_col", "出願人")

        for row in rows:
            company = (row.get(company_col) or "").strip()
            if filter_companies and company not in filter_companies:
                continue
            ipc_val = (row.get(ipc_col) or "").strip()
            if not ipc_val:
                continue
            # 複数のIPCが含まれる場合（セミコロンや改行区切り）
            for part in re.split(r"[;,\n\r]+", ipc_val):
                part = part.strip()
                # セクション（A-H）
                if part and part[0] in self.IPC_SECTION_NAMES:
                    section = part[0]
                    if filter_sections and section not in filter_sections:
                        continue
                    section_counts[section] = section_counts.get(section, 0) + 1
                # サブクラス（例: H01L）
                m = _IPC_SECTION_RE.match(part)
                if m:
                    subclass = m.group(1)
                    subclass_counts[subclass] = subclass_counts.get(subclass, 0) + 1

        if not section_counts:
            return StatResult(
                processor_id=self.processor_id,
                title=self.title,
                df=pd.DataFrame(),
                description=f"列「{ipc_col}」にIPC分類データが見つかりませんでした。",
            )

        # セクション別集計テーブル
        df = pd.DataFrame(
            [
                {
                    "セクション": f"{k}: {self.IPC_SECTION_NAMES.get(k, '')}",
                    "件数": v,
                    "割合(%)": round(v / sum(section_counts.values()) * 100, 1),
                }
                for k, v in sorted(section_counts.items(), key=lambda x: x[1], reverse=True)
            ]
        )

        # サブクラス上位10
        top_subclass = sorted(subclass_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        description = "上位サブクラス: " + ", ".join(f"{k}({v}件)" for k, v in top_subclass)

        return StatResult(
            processor_id=self.processor_id,
            title=self.title,
            df=df,
            description=description,
            meta={"ipc_col": ipc_col, "subclass_counts": subclass_counts},
        )
