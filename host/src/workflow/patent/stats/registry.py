"""
workflow/patent/stats/registry.py
===================================
統計プロセッサのレジストリ。

新しい統計プロセッサを追加する手順:
1. BaseStatProcessor を継承したクラスを新しいファイルに作成
2. このファイルの REGISTRY dict に登録する
"""

from __future__ import annotations

from .base import BaseStatProcessor
from .company_count import CompanyCountProcessor
from .yearly_count import YearlyCountProcessor
from .ipc_distribution import IpcDistributionProcessor

# -------------------------------------------------------------------
# プロセッサ登録テーブル
# ここに追加するだけで新しい統計が利用可能になる
# -------------------------------------------------------------------
REGISTRY: dict[str, BaseStatProcessor] = {
    CompanyCountProcessor.processor_id: CompanyCountProcessor(),
    YearlyCountProcessor.processor_id: YearlyCountProcessor(),
    IpcDistributionProcessor.processor_id: IpcDistributionProcessor(),
}


def get_processor(processor_id: str) -> BaseStatProcessor | None:
    """IDでプロセッサを取得する。存在しない場合は None を返す。"""
    return REGISTRY.get(processor_id)


def list_processors() -> list[dict]:
    """利用可能なプロセッサの一覧を返す（API用）。"""
    return [
        {
            "id": p.processor_id,
            "title": p.title,
            "description": p.description,
        }
        for p in REGISTRY.values()
    ]
