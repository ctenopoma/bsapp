"""
workflow/patent/stats/company_count.py
========================================
企業別出願件数の統計プロセッサ。
"""

from __future__ import annotations

import pandas as pd

from .base import BaseStatProcessor, StatResult, StatParams


class CompanyCountProcessor(BaseStatProcessor):
    processor_id = "company_count"
    title = "企業別出願件数"
    description = "企業ごとの出願件数を集計します。"
    param_schema = '{"companies": ["対象企業リスト(空=全企業)"]}'

    def process(self, rows: list[dict], settings: dict[str, str],
                params: StatParams | None = None) -> StatResult:
        company_col = settings.get("company_col", "出願人")
        filter_companies = set(params.companies) if params and params.companies else set()

        counts: dict[str, int] = {}
        for row in rows:
            company = (row.get(company_col) or "").strip()
            if not company:
                continue
            if filter_companies and company not in filter_companies:
                continue
            counts[company] = counts.get(company, 0) + 1

        if not counts:
            return StatResult(
                processor_id=self.processor_id,
                title=self.title,
                df=pd.DataFrame(),
                description="企業データが見つかりませんでした。",
            )

        df = pd.DataFrame(
            sorted(counts.items(), key=lambda x: x[1], reverse=True),
            columns=["企業名", "出願件数"],
        )
        df["割合(%)"] = (df["出願件数"] / df["出願件数"].sum() * 100).round(1)

        return StatResult(
            processor_id=self.processor_id,
            title=self.title,
            df=df,
            meta={"total_companies": len(counts), "total_patents": sum(counts.values())},
        )
