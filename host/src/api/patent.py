"""
api/patent.py
==============
特許調査 API エンドポイント。

エンドポイント:
  POST /api/patent/analyze   - 特許を分析してレポートを返す（トークン上限チェック付き）
  POST /api/patent/compress  - 特許リストをLLMで圧縮して返す
  POST /api/patent/summary   - 全企業レポートを総括して返す（後方互換で残す）
"""

from fastapi import APIRouter
from langchain_openai import ChatOpenAI

from ..models import (
    PatentAnalyzeRequest,
    PatentAnalyzeResponse,
    PatentChunkedAnalyzeRequest,
    PatentChunkedAnalyzeResponse,
    PatentCompressRequest,
    PatentCompressResponse,
    PatentSummaryRequest,
    PatentSummaryResponse,
)
from ..app_settings import get_llm_config, get_settings
from ..workflow.patent import analyze_company, analyze_chunked, compress_patents, summarize_all

router = APIRouter()


def _create_llm() -> ChatOpenAI:
    c = get_llm_config()
    return ChatOpenAI(
        temperature=c.llm_temperature,
        model=c.llm_model,
        base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
        api_key=c.llm_api_key,
    )


@router.post("/analyze", response_model=PatentAnalyzeResponse)
def analyze(request: PatentAnalyzeRequest) -> PatentAnalyzeResponse:
    """特許リストを分析してレポートを返す。トークン上限チェック付き。"""
    llm = _create_llm()
    settings = get_settings()
    max_tokens = settings.patent_max_prompt_tokens
    report = analyze_company(request, llm, max_prompt_tokens=max_tokens)
    return PatentAnalyzeResponse(company=request.company, report=report)


@router.post("/analyze_chunked", response_model=PatentChunkedAnalyzeResponse)
def analyze_chunked_endpoint(request: PatentChunkedAnalyzeRequest) -> PatentChunkedAnalyzeResponse:
    """チャンク分割Reduceで特許リストを分析する。大量特許でもコンテキスト長を超えずに処理可能。"""
    llm = _create_llm()
    settings = get_settings()
    return analyze_chunked(
        request,
        llm,
        max_prompt_tokens=settings.patent_max_prompt_tokens,
        chunk_analyze_prompt=settings.patent_chunk_analyze_prompt,
        chunk_reduce_prompt=settings.patent_chunk_reduce_prompt,
    )


@router.post("/compress", response_model=PatentCompressResponse)
def compress(request: PatentCompressRequest) -> PatentCompressResponse:
    """特許リストをLLMで圧縮して返す。"""
    llm = _create_llm()
    settings = get_settings()
    # 圧縮プロンプトが未設定の場合はサーバー設定を使用
    if not request.compress_prompt:
        if request.mode == "per_patent":
            request = request.model_copy(
                update={"compress_prompt": settings.patent_compress_per_patent_prompt}
            )
        elif request.mode == "per_company":
            request = request.model_copy(
                update={"compress_prompt": settings.patent_compress_per_company_prompt}
            )
    return compress_patents(request, llm)


@router.post("/summary", response_model=PatentSummaryResponse)
def summary(request: PatentSummaryRequest) -> PatentSummaryResponse:
    """全企業レポートを読んで総括レポートを返す。"""
    llm = _create_llm()
    text = summarize_all(request, llm)
    return PatentSummaryResponse(summary=text)
