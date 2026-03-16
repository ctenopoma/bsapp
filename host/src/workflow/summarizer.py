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
    # input_variables はテンプレートから自動推論する。
    # カスタムテンプレートで {output_format} を省略してもエラーにならない。
    template_str = get_settings().summary_prompt_template
    prompt_template = PromptTemplate.from_template(template_str)

    output_format = (
        session.current_theme_config.output_format
        if session.current_theme_config
        else ""
    )
    format_kwargs = dict(
        theme=session.current_theme,
        history=history_text,
        output_format=output_format,
    )
    # テンプレートが使わない変数はここで除外し、不要なキーエラーを防ぐ
    used_vars = set(prompt_template.input_variables)
    response = llm.invoke(
        prompt_template.format(**{k: v for k, v in format_kwargs.items() if k in used_vars})
    )
    return response.content
