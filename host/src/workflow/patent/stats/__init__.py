"""
workflow/patent/stats パッケージ
================================
特許データの統計処理モジュール。

各統計プロセッサは BaseStatProcessor を継承して実装し、
REGISTRY に登録することで自動的に利用可能になります。

モジュール一覧:
- base.py             : 基底クラスと共通型定義
- yearly_count.py     : 年別出願件数
- company_count.py    : 企業別出願件数
- ipc_distribution.py : IPC分類分布
- registry.py         : プロセッサ登録・管理
"""

from .registry import REGISTRY, get_processor, list_processors
from .runner import run_stats, run_stats_with_configs, ProcessorRunConfig
from .base import StatParams

__all__ = ["REGISTRY", "get_processor", "list_processors", "run_stats",
           "run_stats_with_configs", "ProcessorRunConfig", "StatParams"]
