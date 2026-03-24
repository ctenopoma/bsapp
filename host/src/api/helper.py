"""
/api/helper — ペルソナ・タスク入力支援ヘルパーエンドポイント
"""

import json
import logging
import re
from fastapi import APIRouter

from ..models import HelperAskRequest, HelperAskResponse, FieldSuggestion
from ..helper_knowledge import get_system_prompt
from ..agent_runner import create_llm

logger = logging.getLogger("bsapp.helper")

router = APIRouter()

# 会話履歴として渡す最大文字数（日本語1文字≒1〜2トークン換算）
# system_prompt + current_input の分を除いた履歴予算として設定
_HISTORY_MAX_CHARS = 4000


def _trim_history(history: list, max_chars: int) -> list:
    """会話履歴を末尾（直近）から max_chars 文字以内に収めて返す。"""
    total = 0
    kept = []
    for msg in reversed(history):
        length = len(msg.content)
        if total + length > max_chars:
            break
        kept.append(msg)
        total += length
    if len(kept) < len(history):
        logger.info(
            "Helper history trimmed: %d → %d messages (%d chars)",
            len(history), len(kept), total,
        )
    return list(reversed(kept))


@router.post("/ask", response_model=HelperAskResponse)
async def helper_ask(req: HelperAskRequest) -> HelperAskResponse:
    """ヘルパーエージェントに質問する。"""

    system_prompt = get_system_prompt(req.context)

    # メッセージ列を構築
    messages = [{"role": "system", "content": system_prompt}]

    # 会話履歴を文字数上限でトリムしてから追加
    for msg in _trim_history(req.history, _HISTORY_MAX_CHARS):
        messages.append({"role": msg.role, "content": msg.content})

    # 現在の入力値がある場合はユーザーメッセージに添付
    user_content = req.question
    if req.current_input:
        user_content += f"\n\n[現在の入力値]\n{json.dumps(req.current_input, ensure_ascii=False, indent=2)}"

    messages.append({"role": "user", "content": user_content})

    # LLM呼び出し
    llm = create_llm()
    response = llm.invoke(messages)
    raw = response.content

    # レスポンスのパース (JSON形式を期待するが、フォールバックも用意)
    answer = raw
    suggestions = None

    try:
        # Markdownコードブロック (```json ... ``` 等) を除去してからパース
        stripped = re.sub(r'^```(?:json)?\s*', '', raw.strip())
        stripped = re.sub(r'\s*```$', '', stripped.strip())
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            answer = parsed.get("answer", raw)
            raw_suggestions = parsed.get("suggestions")
            if raw_suggestions and isinstance(raw_suggestions, list):
                suggestions = [
                    FieldSuggestion(
                        field=s.get("field", ""),
                        value=s.get("value", ""),
                        label=s.get("label", s.get("field", "")),
                    )
                    for s in raw_suggestions
                    if isinstance(s, dict) and s.get("field") and s.get("value")
                ]
    except (json.JSONDecodeError, TypeError):
        # JSONパース失敗時はそのままテキストを返す
        logger.info("Helper response is not JSON, returning as plain text")

    return HelperAskResponse(
        answer=answer,
        suggestions=suggestions if suggestions else None,
    )
