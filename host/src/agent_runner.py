import logging
import time
import urllib.request
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any

from .session_manager import session_manager, SessionMemory
from .models import MessageHistory, ThemeSummary, FullSessionResult
from .app_settings import get_settings, get_llm_config
import uuid as _uuid
from .workflow import (
    select_persona,
    build_agent_input,
    run_one_theme,
    summarize_theme,
)

logger = logging.getLogger("bsapp.llm")

# Temporary simple dictionary to hold job statuses
job_statuses: Dict[str, Dict[str, Any]] = {}


def _proxy_status(url: str) -> str:
    """URLがプロキシ経由になるか判定して文字列で返す。"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or url
    try:
        bypassed = urllib.request.proxy_bypass(host)
    except Exception:
        bypassed = False
    if bypassed:
        return "BYPASS (OK)"
    proxies = urllib.request.getproxies()
    proxy_url = proxies.get("http") or proxies.get("https") or "不明"
    return f"VIA PROXY ({proxy_url}) ← NO_PROXY に {host} を追加が必要"


def create_llm() -> ChatOpenAI:
    c = get_llm_config()
    return ChatOpenAI(
        temperature=c.llm_temperature,
        model=c.llm_model,
        base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
        api_key=c.llm_api_key,
    )


class AgentRunner:
    def run_agent(self, agent_input) -> str:
        """AgentInputを受け取りLLMに投げてレスポンスを返す。

        プロンプトは app_settings.get_settings().agent_prompt_template を使用。
        設定画面から変更可能。
        """
        recent_history = "\n".join(
            [f"{msg.agent_name}: {msg.content}" for msg in agent_input.history]
        )

        rag_section = (
            f"参考情報 (RAG):\n{agent_input.rag_context}"
            if agent_input.rag_context
            else "参考情報 (RAG): なし"
        )

        pre_info_section = (
            f"事前情報:\n{agent_input.pre_info}"
            if agent_input.pre_info
            else "事前情報: なし"
        )

        prompt_template = PromptTemplate(
            input_variables=[
                "role", "task", "name", "query",
                "pre_info_section", "rag_section", "history", "previous_summaries", "output_format",
            ],
            template=get_settings().agent_prompt_template,
        )

        formatted_prompt = prompt_template.format(
            role=agent_input.persona.role,
            task=agent_input.task,
            name=agent_input.persona.name,
            query=agent_input.query,
            pre_info_section=pre_info_section,
            rag_section=rag_section,
            history=recent_history,
            previous_summaries=agent_input.previous_summaries,
            output_format=agent_input.output_format,
        )

        response = self._invoke_llm(formatted_prompt)
        return response.content

    def _invoke_llm(self, prompt: str):
        """常に最新の設定でLLMを生成して呼び出す。"""
        c = get_llm_config()
        base_url = f"http://{c.llm_ip}:{c.llm_port}/v1"
        endpoint = f"{base_url}/chat/completions"
        proxy = _proxy_status(endpoint)

        logger.info(f"[Host→LLM] POST {endpoint}")
        logger.info(f"  model={c.llm_model}  prompt_chars={len(prompt)}")
        logger.info(f"  proxy: {proxy}")
        logger.info(
            f"  # 手動確認 (ホストから実行):\n"
            f"  curl -v --noproxy '*' -X POST {endpoint} \\\n"
            f"    -H 'Content-Type: application/json' \\\n"
            f"    -H 'Authorization: Bearer {c.llm_api_key}' \\\n"
            f"    -d '{{\"model\":\"{c.llm_model}\","
            f"\"messages\":[{{\"role\":\"user\",\"content\":\"ping\"}}]}}'"
        )

        start = time.time()
        try:
            result = create_llm().invoke(prompt)
            elapsed_ms = (time.time() - start) * 1000
            logger.info(f"[LLM→Host] OK  ({elapsed_ms:.1f}ms)")
            return result
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            logger.error(f"[LLM ERROR] POST {endpoint}  ({elapsed_ms:.1f}ms)")
            logger.error(f"  {type(e).__name__}: {e}")
            logger.error(f"  proxy: {proxy}")
            logger.error(
                f"  # モデル一覧で疎通確認:\n"
                f"  curl -v --noproxy '*' {base_url}/models \\\n"
                f"    -H 'Authorization: Bearer {c.llm_api_key}'"
            )
            raise

    def _run_one_theme(self, session: SessionMemory) -> str:
        """現在のテーマを実行して要約を返す。workflow/turn_runner.py に委譲。"""
        return run_one_theme(
            session=session,
            agent_executor=self.run_agent,
            summarizer=lambda s: summarize_theme(s, create_llm()),
        )

    def _summarize_current_theme(self, session: SessionMemory) -> str:
        """現在のテーマを要約して返す。workflow/summarizer.py に委譲。"""
        return summarize_theme(session, create_llm())

    # -------------------------------------------------------------------
    # 全テーマをシーケンシャルに実行するメインエントリ
    # -------------------------------------------------------------------
    def run_full_session_background(self, session_id: str, job_id: str):
        """全テーマを順番に処理し、最終レポートを生成する。"""
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            if not session.personas:
                raise ValueError("No personas available")

            while not session.all_themes_done:
                summary_text = self._run_one_theme(session)
                session.advance_theme(summary_text)
                session.summary_memory += f"\n## {session.current_theme}\n{summary_text}"

            theme_summaries = [
                ThemeSummary(theme=s["theme"], summary=s["summary"])
                for s in session.summaries
            ]
            final_report = "\n\n".join(
                f"## {s.theme}\n{s.summary}" for s in theme_summaries
            )

            job_statuses[job_id] = {
                "status": "completed",
                "result": FullSessionResult(
                    theme_summaries=theme_summaries,
                    final_report=final_report,
                ).model_dump(),
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}

    # -------------------------------------------------------------------
    # 既存API互換 (ターン単位 / 要約単位)
    # -------------------------------------------------------------------
    def start_turn_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            if session.all_themes_done:
                job_statuses[job_id] = {
                    "status": "completed",
                    "all_themes_done": True,
                    "is_theme_end": True,
                }
                return

            active = session.active_personas
            if not active:
                raise ValueError("No active personas for current theme")

            persona = select_persona(active, session)
            agent_input = build_agent_input(session, persona)
            message = self.run_agent(agent_input)

            session.history.append(MessageHistory(
                id=_uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=persona.name,
                content=message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1
            is_theme_end = session.turn_count_in_theme >= session.turns_per_theme

            job_statuses[job_id] = {
                "status": "completed",
                "agent_name": persona.name,
                "message": message,
                "theme": session.current_theme,
                "is_theme_end": is_theme_end,
                "history_compressed": agent_input.history_compressed,
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}

    def summarize_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")

            summary_text = self._summarize_current_theme(session)
            session.advance_theme(summary_text)

            job_statuses[job_id] = {
                "status": "completed",
                "summary_text": summary_text,
                "all_themes_done": session.all_themes_done,
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}


agent_runner = AgentRunner()
