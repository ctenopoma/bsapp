"""
workflow/patent/analyzer.py
=============================
特許分析ワークフロー。

★ ここを書き換えることで分析ロジックを変更できます ★
"""

from ...models import PatentAnalyzeRequest
from .prompt_builder import (
    PATENT_ANALYZE_TEMPLATE,
    DEFAULT_ANALYZE_SYSTEM_PROMPT,
    DEFAULT_ANALYZE_OUTPUT_FORMAT,
)

# tiktoken はオプション依存。インポートできない場合はトークンチェックをスキップ
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

# バックエンドのデフォルト上限 (0=無制限)
DEFAULT_MAX_PROMPT_TOKENS = 0


def count_tokens(text: str) -> int:
    """テキストのおおよそのトークン数を返す。
    tiktoken が使えない場合は文字数 ÷ 2 で近似する。
    """
    if _TIKTOKEN_AVAILABLE:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    # フォールバック: 日本語は文字≒トークン、英語は文字÷4 の混合近似
    return max(1, len(text) // 2)


def analyze_company(request: PatentAnalyzeRequest, llm, max_prompt_tokens: int = DEFAULT_MAX_PROMPT_TOKENS) -> str:
    """特許リストを分析してレポート文字列を返す。

    Parameters
    ----------
    request : PatentAnalyzeRequest
    llm : ChatOpenAI (or compatible)
    max_prompt_tokens : int
        0=無制限。プロンプトがこの値を超えるとTokenLimitExceededError を送出する。

    Raises
    ------
    TokenLimitExceededError
        プロンプトのトークン数が上限を超えた場合。
    """
    from fastapi import HTTPException

    system_prompt = request.system_prompt or DEFAULT_ANALYZE_SYSTEM_PROMPT
    output_format = request.output_format or DEFAULT_ANALYZE_OUTPUT_FORMAT.format(
        company=request.company
    )

    patents_text = "\n".join(
        f"{i}. {p.content}" + (f"  ({p.date})" if p.date else "")
        for i, p in enumerate(request.patents, 1)
    )

    prompt = PATENT_ANALYZE_TEMPLATE.format(
        system_prompt=system_prompt,
        company=request.company,
        count=len(request.patents),
        patents=patents_text,
        output_format=output_format,
    )

    # --- トークン数チェック ---
    # リクエスト側の上限 > 0 なら優先、次にサーバー設定、最後に引数デフォルト
    effective_limit = request.max_prompt_tokens if request.max_prompt_tokens > 0 else max_prompt_tokens
    if effective_limit > 0:
        token_count = count_tokens(prompt)
        if token_count > effective_limit:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"TOKEN_LIMIT_EXCEEDED: プロンプトのトークン数 ({token_count:,}) が"
                    f"上限 ({effective_limit:,}) を超えています。"
                    f"企業数・特許数を減らすか、圧縮モードを使用してください。"
                ),
            )

    # --- LLM 呼び出し ---
    try:
        response = llm.invoke(prompt)
    except Exception as e:
        err_msg = str(e).lower()
        # コンテキスト長超過エラーを統一メッセージに変換
        if any(kw in err_msg for kw in ("context_length_exceeded", "context length", "maximum context", "token", "too long", "reduce")):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"TOKEN_LIMIT_EXCEEDED: LLMのコンテキスト長を超えました。"
                    f"企業数・特許数を減らすか、圧縮モードを使用してください。"
                    f"（元のエラー: {str(e)[:200]}）"
                ),
            )
        raise

    return response.content
