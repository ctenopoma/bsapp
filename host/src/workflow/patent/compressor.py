"""
workflow/patent/compressor.py
================================
特許リストをLLMで圧縮してトークン数を削減する。

モード:
  per_patent  - 特許1件ずつを1〜2文に要約
  per_company - 企業ごとの特許リストを統合して数文にまとめる
"""

from ...models import PatentCompressRequest, PatentCompressResponse, PatentItem
from .prompt_builder import (
    COMPRESS_PER_PATENT_TEMPLATE,
    COMPRESS_PER_COMPANY_TEMPLATE,
)


def compress_patents(request: PatentCompressRequest, llm) -> PatentCompressResponse:
    """特許リストをLLMで圧縮して返す。

    Parameters
    ----------
    request : PatentCompressRequest
    llm : ChatOpenAI (or compatible)

    Returns
    -------
    PatentCompressResponse
    """
    original_count = len(request.patents)

    if request.mode == "per_patent":
        compressed = _compress_per_patent(request.patents, request.compress_prompt, llm)
    elif request.mode == "per_company":
        compressed = _compress_per_company(
            request.patents, request.company, request.compress_prompt, llm
        )
    else:
        # 不明なモードはそのまま返す
        compressed = request.patents

    return PatentCompressResponse(
        patents=compressed,
        original_count=original_count,
        compressed_count=len(compressed),
    )


def _compress_per_patent(
    patents: list[PatentItem], custom_prompt: str, llm
) -> list[PatentItem]:
    """特許1件ずつを要約する。"""
    result = []
    for p in patents:
        template = custom_prompt if custom_prompt.strip() else COMPRESS_PER_PATENT_TEMPLATE
        prompt = template.format(patent=p.content)
        try:
            resp = llm.invoke(prompt)
            summary = resp.content.strip()
        except Exception:
            summary = p.content  # 失敗時はそのまま
        result.append(PatentItem(content=summary, date=p.date))
    return result


def _compress_per_company(
    patents: list[PatentItem], company: str, custom_prompt: str, llm
) -> list[PatentItem]:
    """企業ごとの特許をまとめて1エントリに統合する。"""
    if not patents:
        return []

    patents_text = "\n".join(
        f"{i}. {p.content}" + (f" ({p.date})" if p.date else "")
        for i, p in enumerate(patents, 1)
    )

    template = custom_prompt if custom_prompt.strip() else COMPRESS_PER_COMPANY_TEMPLATE
    prompt = template.format(company=company or "対象企業", patents=patents_text)

    try:
        resp = llm.invoke(prompt)
        summary = resp.content.strip()
    except Exception:
        summary = patents_text  # 失敗時はそのまま

    # 企業まとめは1エントリとして返す（dateは最新のものを使用）
    latest_date = max((p.date for p in patents if p.date), default="")
    return [PatentItem(content=summary, date=latest_date)]
