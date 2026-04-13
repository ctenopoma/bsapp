"""
workflow/patent/stats/yearly_count.py
=======================================
年別出願件数の統計プロセッサ。
"""

from __future__ import annotations

import re

import pandas as pd

from .base import BaseStatProcessor, StatResult, StatParams


class YearlyCountProcessor(BaseStatProcessor):
    processor_id = "yearly_count"
    title = "年別出願件数"
    description = "出願日から年を抽出し、年別の出願件数を集計します。"
    param_schema = '{"companies": ["対象企業リスト(空=全企業)"], "year_from": 開始年|null, "year_to": 終了年|null}'

    def process(self, rows: list[dict], settings: dict[str, str],
                params: StatParams | None = None) -> StatResult:
        date_col = settings.get("date_col", "出願日")
        company_col = settings.get("company_col", "出願人")

        # paramsによるフィルタリング
        filter_companies = set(params.companies) if params and params.companies else set()
        year_from = params.year_from if params else None
        year_to = params.year_to if params else None

        records: list[dict] = []
        for row in rows:
            date_str = (row.get(date_col) or "").strip()
            m = re.match(r"(\d{4})", date_str)
            if not m:
                continue
            year = m.group(1)
            company = (row.get(company_col) or "").strip()
            if filter_companies and company not in filter_companies:
                continue
            if year_from and int(year) < year_from:
                continue
            if year_to and int(year) > year_to:
                continue
            records.append({"year": year, "company": company})

        if not records:
            return StatResult(
                processor_id=self.processor_id,
                title=self.title,
                df=pd.DataFrame(),
                description="出願日データが見つかりませんでした。",
            )

        df_raw = pd.DataFrame(records)

        # 年別・企業別のピボット（企業が多い場合は上位10社のみ）
        companies = df_raw["company"].value_counts()
        top_companies = companies.head(10).index.tolist()
        df_filtered = df_raw[df_raw["company"].isin(top_companies)]

        pivot = (
            df_filtered.groupby(["year", "company"])
            .size()
            .unstack(fill_value=0)
            .sort_index()
        )
        pivot["合計"] = pivot.sum(axis=1)
        pivot = pivot.reset_index().rename(columns={"year": "年"})

        description = ""
        if len(companies) > 10:
            description = f"※ 企業数が多いため上位10社のみ表示（全{len(companies)}社）"

        return StatResult(
            processor_id=self.processor_id,
            title=self.title,
            df=pivot,
            description=description,
            meta={"total_records": len(records), "company_count": len(companies)},
        )
