"""
api/patent.py
==============
特許調査 API エンドポイント。

エンドポイント:
  POST /api/patent/analyze  - 1企業分の特許を分析してレポートを返す
  POST /api/patent/summary  - 全企業レポートを総括して返す
"""

from fastapi import APIRouter
from langchain_openai import ChatOpenAI

from ..models import (
    PatentAnalyzeRequest,
    PatentAnalyzeResponse,
    PatentSummaryRequest,
    PatentSummaryResponse,
)
from ..app_settings import get_llm_config
from ..workflow.patent import analyze_company, summarize_all

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
    """1企業分の特許リストを分析してレポートを返す。"""
    llm = _create_llm()
    report = analyze_company(request, llm)
    return PatentAnalyzeResponse(company=request.company, report=report)


@router.post("/summary", response_model=PatentSummaryResponse)
def summary(request: PatentSummaryRequest) -> PatentSummaryResponse:
    """全企業レポートを読んで総括レポートを返す。"""
    llm = _create_llm()
    text = summarize_all(request, llm)
    return PatentSummaryResponse(summary=text)
