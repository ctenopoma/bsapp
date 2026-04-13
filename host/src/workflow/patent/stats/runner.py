"""
workflow/patent/stats/runner.py
================================
複数の統計プロセッサを実行して結果をまとめる。

フロー:
  1. (任意) LLMにパラメータを生成させる（param_prompt が設定されている場合）
  2. パラメータを使ってプロセッサを実行
  3. 結果をマークダウン表/変数辞書に変換
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .base import StatResult, StatParams
from .registry import REGISTRY, get_processor

logger = logging.getLogger("bsapp.stats")


@dataclass
class ProcessorRunConfig:
    """1プロセッサ分の実行設定。"""
    processor_id: str
    param_prompt: str = ""   # 空=LLMなし（全データ機械処理）
    variable_name: str = ""  # 最終プロンプト変数名（空=processor_id使用）
    ipc_col: str = ""


def run_stats(
    rows: list[dict],
    processor_ids: list[str],
    settings: dict[str, str],
    params_map: dict[str, StatParams] | None = None,
) -> list[StatResult]:
    """
    指定されたプロセッサIDリストを実行し、StatResult のリストを返す。

    Args:
        rows: CSVの行データリスト
        processor_ids: 実行するプロセッサIDのリスト（空=全プロセッサ実行）
        settings: 列名設定など
        params_map: processor_id → StatParams のマッピング（Noneまたは未設定=パラメータなし）

    Returns:
        StatResult のリスト（実行順）
    """
    targets = processor_ids if processor_ids else list(REGISTRY.keys())
    results: list[StatResult] = []

    for pid in targets:
        processor = get_processor(pid)
        if processor is None:
            continue
        proc_settings = dict(settings)
        try:
            params = params_map.get(pid) if params_map else None
            result = processor.process(rows, proc_settings, params=params)
            results.append(result)
        except Exception as e:
            logger.warning(f"Stats processor '{pid}' failed: {e}")

    return results


def run_stats_with_configs(
    rows: list[dict],
    configs: list[ProcessorRunConfig],
    settings: dict[str, str],
    llm: Any | None = None,
    discussion_context: str = "",
) -> list[StatResult]:
    """
    ProcessorRunConfig リストに基づいて実行する（LLMパラメータ生成付き）。

    各configのparam_promptが空でない場合、LLMにdiscussion_contextを渡して
    StatParamsをJSON形式で生成させ、それを統計処理に渡す。

    Args:
        rows: CSVの行データリスト
        configs: プロセッサ実行設定リスト
        settings: 列名設定
        llm: LangChainのChatOpenAIインスタンス（param_promptがある場合に必要）
        discussion_context: LLMに渡す前テーマの議論内容

    Returns:
        StatResult のリスト
    """
    results: list[StatResult] = []

    for cfg in configs:
        processor = get_processor(cfg.processor_id)
        if processor is None:
            logger.warning(f"Unknown processor: {cfg.processor_id}")
            continue

        proc_settings = dict(settings)
        if cfg.ipc_col:
            proc_settings["ipc_col"] = cfg.ipc_col

        params: StatParams | None = None
        if cfg.param_prompt and llm is not None:
            params = _generate_params_with_llm(
                llm=llm,
                processor=processor,
                param_prompt=cfg.param_prompt,
                discussion_context=discussion_context,
                rows=rows,
                settings=proc_settings,
            )

        try:
            result = processor.process(rows, proc_settings, params=params)
            # variable_nameが指定されていれば、後で変数置換できるようにprocessor_idを上書き
            if cfg.variable_name:
                result = StatResult(
                    processor_id=cfg.variable_name,
                    title=result.title,
                    df=result.df,
                    description=result.description,
                    meta=result.meta,
                )
            results.append(result)
        except Exception as e:
            logger.warning(f"Stats processor '{cfg.processor_id}' failed: {e}")

    return results


def _generate_params_with_llm(
    llm: Any,
    processor: Any,
    param_prompt: str,
    discussion_context: str,
    rows: list[dict],
    settings: dict[str, str],
) -> StatParams:
    """LLMにパラメータを生成させてStatParamsとして返す。"""
    company_col = settings.get("company_col", "出願人")
    all_companies = sorted({(r.get(company_col) or "").strip() for r in rows if (r.get(company_col) or "").strip()})
    companies_hint = "、".join(all_companies[:30])
    if len(all_companies) > 30:
        companies_hint += f"... (全{len(all_companies)}社)"

    prompt = f"""{param_prompt}

## 分析対象の統計処理
統計ID: {processor.processor_id}
統計名: {processor.title}
パラメータスキーマ: {processor.param_schema}

## CSVに含まれる企業一覧（参考）
{companies_hint}

## 前テーマまでの議論内容
{discussion_context or "（議論なし）"}

## 指示
上記の情報を踏まえて、この統計処理に渡す最適なパラメータをJSONで出力してください。
スキーマに従い、不要なキーは省略してください。JSONのみを出力すること。

```json
"""
    try:
        raw = llm.invoke(prompt).content
        return StatParams.from_llm_json(raw)
    except Exception as e:
        logger.warning(f"LLM param generation failed for '{processor.processor_id}': {e}")
        return StatParams()


def results_to_markdown(results: list[StatResult]) -> str:
    """複数の StatResult をまとめてマークダウン文字列に変換する。"""
    return "\n\n".join(r.to_markdown() for r in results if not r.df.empty)


def results_to_variables(results: list[StatResult]) -> dict[str, str]:
    """
    StatResult のリストをプロンプト変数辞書に変換する。
    キー: processor_id, 値: マークダウンテキスト
    """
    return {r.processor_id: r.to_text() for r in results}
