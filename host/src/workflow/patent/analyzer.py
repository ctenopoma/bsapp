"""
workflow/patent/analyzer.py
=============================
1企業分の特許分析ワークフロー。

★ ここを書き換えることで分析ロジックを変更できます ★

変更できること:
  - 特許テキストの整形方法
  - プロンプトの組み立て方法
  - LLM呼び出しのパラメータ
"""

from ...models import PatentAnalyzeRequest
from .prompt_builder import (
    PATENT_ANALYZE_TEMPLATE,
    DEFAULT_ANALYZE_SYSTEM_PROMPT,
    DEFAULT_ANALYZE_OUTPUT_FORMAT,
)


def analyze_company(request: PatentAnalyzeRequest, llm) -> str:
    """1企業の特許リストを分析してレポート文字列を返す。

    Parameters
    ----------
    request : PatentAnalyzeRequest
        企業名・特許リスト・システムプロンプト・出力フォーマット。
    llm : ChatOpenAI (or compatible)
        LLMクライアント。

    Returns
    -------
    str
        LLMが生成した分析レポート。
    """
    system_prompt = request.system_prompt or DEFAULT_ANALYZE_SYSTEM_PROMPT
    output_format = request.output_format or DEFAULT_ANALYZE_OUTPUT_FORMAT.format(
        company=request.company
    )

    # 特許リストをテキスト化
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

    response = llm.invoke(prompt)
    return response.content
