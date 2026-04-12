"""
workflow/patent/chunked_analyzer.py
=====================================
チャンク分割Reduceによる特許分析。

動作:
  1. Map  : 全特許を chunk_size 件ずつのバッチに分割し、各チャンクを個別LLM呼び出しで分析
  2. Reduce: 全中間レポートをまとめて最終LLM呼び出しで統合レポートを生成

メリット:
  - LLMのコンテキスト長を超えた大量特許でも分析可能
  - チャンクは独立しているため将来的に並列化しやすい
"""

from fastapi import HTTPException

from ...models import PatentChunkedAnalyzeRequest, PatentChunkedAnalyzeResponse
from .analyzer import count_tokens
from .prompt_builder import (
    CHUNK_ANALYZE_TEMPLATE,
    CHUNK_REDUCE_TEMPLATE,
    DEFAULT_ANALYZE_SYSTEM_PROMPT,
    DEFAULT_ANALYZE_OUTPUT_FORMAT,
)


def analyze_chunked(
    request: PatentChunkedAnalyzeRequest,
    llm,
    max_prompt_tokens: int = 0,
    chunk_analyze_prompt: str = "",
    chunk_reduce_prompt: str = "",
) -> PatentChunkedAnalyzeResponse:
    """チャンク分割Reduceで特許リストを分析する。

    Parameters
    ----------
    request : PatentChunkedAnalyzeRequest
    llm : ChatOpenAI (or compatible)
    max_prompt_tokens : int
        個々のプロンプトのトークン上限 (0=無制限)
    chunk_analyze_prompt : str
        Mapフェーズ用カスタムプロンプト (空=デフォルト)
    chunk_reduce_prompt : str
        Reduceフェーズ用カスタムプロンプト (空=デフォルト)

    Returns
    -------
    PatentChunkedAnalyzeResponse
    """
    system_prompt = request.system_prompt or DEFAULT_ANALYZE_SYSTEM_PROMPT
    output_format = request.output_format or DEFAULT_ANALYZE_OUTPUT_FORMAT.format(
        company=request.company
    )

    chunk_size = max(1, request.chunk_size)
    patents = request.patents

    # チャンク分割
    chunks = [patents[i:i + chunk_size] for i in range(0, len(patents), chunk_size)]
    total_chunks = len(chunks)

    effective_limit = request.max_prompt_tokens if request.max_prompt_tokens > 0 else max_prompt_tokens

    # --- Map フェーズ ---
    intermediate_reports: list[str] = []
    map_template = chunk_analyze_prompt if chunk_analyze_prompt.strip() else CHUNK_ANALYZE_TEMPLATE

    for chunk_no, chunk in enumerate(chunks, 1):
        patents_text = "\n".join(
            f"{i}. {p.content}" + (f"  ({p.date})" if p.date else "")
            for i, p in enumerate(chunk, 1)
        )
        prompt = map_template.format(
            system_prompt=system_prompt,
            company=request.company,
            chunk_no=chunk_no,
            total_chunks=total_chunks,
            count=len(chunk),
            patents=patents_text,
        )

        _check_token_limit(prompt, effective_limit, phase=f"Map チャンク {chunk_no}/{total_chunks}")

        try:
            resp = llm.invoke(prompt)
        except Exception as e:
            _reraise_token_error(e, phase=f"Map チャンク {chunk_no}/{total_chunks}")
        intermediate_reports.append(resp.content.strip())

    # --- Reduce フェーズ ---
    intermediate_text = "\n\n---\n\n".join(
        f"### チャンク {i}\n{r}" for i, r in enumerate(intermediate_reports, 1)
    )
    reduce_template = chunk_reduce_prompt if chunk_reduce_prompt.strip() else CHUNK_REDUCE_TEMPLATE
    reduce_prompt = reduce_template.format(
        system_prompt=system_prompt,
        company=request.company,
        chunk_count=total_chunks,
        intermediate_reports=intermediate_text,
        output_format=output_format,
    )

    _check_token_limit(reduce_prompt, effective_limit, phase="Reduce")

    try:
        reduce_resp = llm.invoke(reduce_prompt)
    except Exception as e:
        _reraise_token_error(e, phase="Reduce")

    return PatentChunkedAnalyzeResponse(
        company=request.company,
        report=reduce_resp.content.strip(),
        chunk_count=total_chunks,
        intermediate_reports=intermediate_reports,
    )


def _check_token_limit(prompt: str, limit: int, phase: str) -> None:
    if limit <= 0:
        return
    token_count = count_tokens(prompt)
    if token_count > limit:
        raise HTTPException(
            status_code=422,
            detail=(
                f"TOKEN_LIMIT_EXCEEDED: {phase} のプロンプトのトークン数 ({token_count:,}) が"
                f"上限 ({limit:,}) を超えています。"
                f"チャンクサイズを小さくするか、上限を見直してください。"
            ),
        )


def _reraise_token_error(e: Exception, phase: str) -> None:
    err_msg = str(e).lower()
    if any(kw in err_msg for kw in ("context_length_exceeded", "context length", "maximum context", "token", "too long", "reduce")):
        raise HTTPException(
            status_code=422,
            detail=(
                f"TOKEN_LIMIT_EXCEEDED: {phase} でLLMのコンテキスト長を超えました。"
                f"チャンクサイズを小さくしてください。"
                f"（元のエラー: {str(e)[:200]}）"
            ),
        )
    raise e
