"""
workflow/patent/summarizer.py
================================
全企業レポートを横断した総括レポートの生成ワークフロー。

★ ここを書き換えることで総括ロジックを変更できます ★
"""

from ...models import PatentSummaryRequest
from .prompt_builder import PATENT_SUMMARY_TEMPLATE, DEFAULT_SUMMARY_SYSTEM_PROMPT


def summarize_all(request: PatentSummaryRequest, llm) -> str:
    """全企業のレポートを受け取り、総括レポート文字列を返す。

    Parameters
    ----------
    request : PatentSummaryRequest
        全企業レポートのリストとシステムプロンプト。
    llm : ChatOpenAI (or compatible)
        LLMクライアント。

    Returns
    -------
    str
        LLMが生成した総括レポート。
    """
    system_prompt = request.system_prompt or DEFAULT_SUMMARY_SYSTEM_PROMPT

    reports_text = "\n\n---\n\n".join(
        f"### {r.company}\n{r.report}" for r in request.company_reports
    )

    prompt = PATENT_SUMMARY_TEMPLATE.format(
        system_prompt=system_prompt,
        reports=reports_text,
    )

    response = llm.invoke(prompt)
    return response.content
