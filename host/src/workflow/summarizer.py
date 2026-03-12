"""
summarizer.py
==============
テーマ要約を生成するロジック。

★ ここを書き換えることで要約のスタイルやプロンプトを変更できます ★

変更できること:
  - 要約のプロンプト (SUMMARY_PROMPT_TEMPLATE を変更)
  - 要約に含める発言の絞り込み (全発言 → 特定ペルソナのみ など)
  - 要約結果のフォーマット後処理
"""

from langchain_core.prompts import PromptTemplate

from ..session_manager import SessionMemory
from ..app_settings import get_settings


def summarize_theme(session: SessionMemory, llm) -> str:
    """現在のテーマの会話履歴をまとめて要約テキストを返す。

    Parameters
    ----------
    session : SessionMemory
        現在のセッション状態。current_theme のメッセージが対象。
    llm : ChatOpenAI (or compatible)
        LLMクライアント。invoke(prompt) -> response.content を持つこと。

    Returns
    -------
    str
        LLMが生成した要約テキスト。
    """
    # ------------------------------------------------------------------
    # 現在のテーマに属する発言を収集
    # ------------------------------------------------------------------
    theme_history = [
        msg for msg in session.history if msg.theme == session.current_theme
    ]
    history_text = "\n".join(
        [f"{msg.agent_name}: {msg.content}" for msg in theme_history]
    )

    # ------------------------------------------------------------------
    # プロンプト組み立て & LLM呼び出し
    # ------------------------------------------------------------------
    prompt_template = PromptTemplate(
        input_variables=["theme", "history", "output_format"],
        template=get_settings().summary_prompt_template,
    )
    response = llm.invoke(
        prompt_template.format(theme=session.current_theme, history=history_text, output_format=session.current_theme_config.output_format) # type: ignore
    )
    return response.content
