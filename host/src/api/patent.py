"""
api/patent.py
==============
特許調査 API エンドポイント。

エンドポイント:
  POST /api/patent/analyze        - 特許を分析してレポートを返す（トークン上限チェック付き）
  POST /api/patent/compress       - 特許リストをLLMで圧縮して返す
  POST /api/patent/summary        - 全企業レポートを総括して返す（後方互換で残す）
  POST /api/patent/stats          - 統計処理を実行してテーブルまたはLLM整理結果を返す
  GET  /api/patent/stats/processors - 利用可能な統計プロセッサ一覧を返す
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
    PatentStatsRequest,
    PatentStatsResponse,
    StatTableResult,
    StatProcessorInfo,
)
from ..app_settings import get_llm_config, get_settings
from ..workflow.patent import analyze_company, analyze_chunked, compress_patents, summarize_all
from ..workflow.patent.stats import run_stats, list_processors
from ..workflow.patent.stats.runner import results_to_markdown

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


@router.get("/stats/processors", response_model=list[StatProcessorInfo])
def get_stat_processors() -> list[StatProcessorInfo]:
    """利用可能な統計プロセッサの一覧を返す。"""
    return [StatProcessorInfo(**p) for p in list_processors()]


@router.post("/stats", response_model=PatentStatsResponse)
def run_patent_stats(request: PatentStatsRequest) -> PatentStatsResponse:
    """
    特許CSVデータに対して統計処理を実行する。

    display_mode="table": 各統計をマークダウン表形式で返す
    display_mode="llm":   統計結果をLLMに整理させて自然言語サマリーを返す
    """
    app_settings = get_settings()

    # 列名設定（リクエストに指定がなければAppSettingsのデフォルト値を使用）
    col_settings: dict[str, str] = {
        "company_col": request.company_col or app_settings.patent_company_column,
        "date_col": request.date_col or app_settings.patent_date_column,
        "content_col": request.content_col or app_settings.patent_content_column,
    }
    if request.ipc_col:
        col_settings["ipc_col"] = request.ipc_col

    results = run_stats(
        rows=request.rows,
        processor_ids=request.processor_ids,
        settings=col_settings,
    )

    tables = [
        StatTableResult(
            processor_id=r.processor_id,
            title=r.title,
            markdown=r.to_markdown(),
            is_empty=r.df.empty,
        )
        for r in results
    ]
    combined_markdown = results_to_markdown(results)

    if request.display_mode == "llm" and request.llm_prompt and combined_markdown:
        llm = _create_llm()
        # 統計結果を変数として展開してLLMに渡す
        from ..workflow.patent.stats.runner import results_to_variables
        variables = results_to_variables(results)
        prompt = request.llm_prompt
        for var_name, var_value in variables.items():
            prompt = prompt.replace(f"{{{{{var_name}}}}}", var_value)
        # 未置換の変数は統計全体テキストで補完
        prompt = prompt.replace("{{stats_all}}", combined_markdown)
        llm_result = llm.invoke(prompt).content
        return PatentStatsResponse(
            display_mode="llm",
            tables=tables,
            llm_result=llm_result,
            combined_markdown=combined_markdown,
        )

    return PatentStatsResponse(
        display_mode="table",
        tables=tables,
        combined_markdown=combined_markdown,
    )
