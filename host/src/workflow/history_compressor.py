"""
history_compressor.py
======================
会話履歴のトークン数が上限を超えた場合に古い部分を要約圧縮するロジック。

★ ここを書き換えることで圧縮の挙動を変更できます ★

変更できること:
  - HISTORY_COMPRESS_PROMPT : 古い履歴を要約するプロンプト
  - estimate_tokens()        : トークン数の推定方法
  - compress_history()       : 圧縮の分割戦略
"""

import uuid
from typing import List, Optional

from langchain_core.prompts import PromptTemplate

from ..models import MessageHistory

# -------------------------------------------------------------------
# 古い履歴を圧縮するプロンプト
# -------------------------------------------------------------------
HISTORY_COMPRESS_PROMPT = """\
以下の会話記録を簡潔に要約してください。
各発言者の主要な主張やポイントを漏れなく保持してください。

会話記録:
{history}

要約 (各発言者の主張を箇条書きでまとめる):
"""


def estimate_tokens(text: str) -> int:
    """テキストのトークン数を簡易推定する。

    日本語は概ね 1トークン ≈ 2文字 として計算。
    """
    return max(1, len(text) // 2)


def history_to_text(history: List[MessageHistory]) -> str:
    return "\n".join(f"{msg.agent_name}: {msg.content}" for msg in history)


def compress_history(
    history: List[MessageHistory],
    recent_count: int,
    max_tokens: int,
    llm=None,
) -> List[MessageHistory]:
    """会話履歴が max_tokens を超える場合、古い部分を要約圧縮して返す。

    Parameters
    ----------
    history : List[MessageHistory]
        全会話履歴。
    recent_count : int
        圧縮せずそのまま保持する直近の会話数。
    max_tokens : int
        会話履歴の最大トークン数。0以下の場合は無制限 (圧縮しない)。
    llm : ChatOpenAI (or compatible), optional
        圧縮に使用するLLMクライアント。None の場合は内部で生成。

    Returns
    -------
    List[MessageHistory]
        必要に応じて圧縮された会話履歴。
    """
    # max_tokens=0 は無制限
    if max_tokens <= 0 or not history:
        return history

    full_text = history_to_text(history)
    if estimate_tokens(full_text) <= max_tokens:
        return history

    # 直近 recent_count 件は圧縮せず保持
    if recent_count > 0 and len(history) > recent_count:
        recent = list(history[-recent_count:])
        older = list(history[:-recent_count])
    else:
        # 全件が直近扱い → 圧縮不可、そのまま返す
        return history

    if not older:
        return recent

    # 古い部分が圧縮不要ならそのまま結合
    older_text = history_to_text(older)
    if estimate_tokens(older_text) == 0:
        return recent

    # LLMで古い部分を要約
    if llm is None:
        from ..app_settings import get_llm_config
        from langchain_openai import ChatOpenAI
        c = get_llm_config()
        llm = ChatOpenAI(
            temperature=0.3,
            model=c.llm_model,
            base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
            api_key=c.llm_api_key,
        )

    prompt = PromptTemplate(
        input_variables=["history"],
        template=HISTORY_COMPRESS_PROMPT,
    )
    response = llm.invoke(prompt.format(history=older_text))
    summary_text = response.content

    # 要約を MessageHistory の特殊エントリとして挿入
    summary_msg = MessageHistory(
        id=uuid.uuid4().hex,
        theme=older[0].theme,
        agent_name="[会話要約]",
        content=summary_text,
        turn_order=-1,
    )

    return [summary_msg] + recent
