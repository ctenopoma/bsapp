import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any

from .session_manager import session_manager, SessionMemory
from .models import MessageHistory, ThemeSummary, FullSessionResult
from .workflow import (
    select_persona,
    build_agent_input,
    run_one_theme,
    summarize_theme,
    AGENT_PROMPT_TEMPLATE,
)

# Temporary simple dictionary to hold job statuses
job_statuses: Dict[str, Dict[str, Any]] = {}

llm_ip = os.environ.get("LLM_IP", "127.0.0.1")
llm_port = os.environ.get("LLM_PORT", "11434")
llm_base_url = f"http://{llm_ip}:{llm_port}/v1"
llm_model = os.environ.get("LLM_MODEL", "llama3")
llm_api_key = os.environ.get("LLM_API_KEY", "dummy")

GLOBAL_LLM = ChatOpenAI(
    temperature=0.7,
    model=llm_model,
    base_url=llm_base_url,
    api_key=llm_api_key
)


class AgentRunner:
    def __init__(self):
        self.llm = GLOBAL_LLM

    def run_agent(self, agent_input) -> str:
        """AgentInputを受け取りLLMに投げてレスポンスを返す。

        プロンプトを変更する場合は workflow/prompt_builder.py の
        AGENT_PROMPT_TEMPLATE を編集してください。
        """
        recent_history = "\n".join(
            [f"{msg.agent_name}: {msg.content}" for msg in agent_input.history]
        )

        rag_section = (
            f"参考情報 (RAG):\n{agent_input.rag_context}"
            if agent_input.rag_context
            else "参考情報 (RAG): なし"
        )

        prompt_template = PromptTemplate(
            input_variables=[
                "role", "task", "name", "query",
                "rag_section", "history", "output_format",
            ],
            template=AGENT_PROMPT_TEMPLATE,
        )

        formatted_prompt = prompt_template.format(
            role=agent_input.persona.role,
            task=agent_input.task,
            name=agent_input.persona.name,
            query=agent_input.query,
            rag_section=rag_section,
            history=recent_history,
            output_format=agent_input.output_format,
        )

        response = self.llm.invoke(formatted_prompt)
        return response.content

    def _run_one_theme(self, session: SessionMemory) -> str:
        """現在のテーマを実行して要約を返す。workflow/turn_runner.py に委譲。"""
        return run_one_theme(
            session=session,
            agent_executor=self.run_agent,
            summarizer=lambda s: summarize_theme(s, self.llm),
        )

    def _summarize_current_theme(self, session: SessionMemory) -> str:
        """現在のテーマを要約して返す。workflow/summarizer.py に委譲。"""
        return summarize_theme(session, self.llm)

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
            active = session.active_personas
            if not active:
                raise ValueError("No active personas for current theme")

            persona = select_persona(active, session)
            agent_input = build_agent_input(session, persona)
            message = self.run_agent(agent_input)

            session.turn_count_in_theme += 1
            is_theme_end = session.turn_count_in_theme >= session.turns_per_theme

            job_statuses[job_id] = {
                "status": "completed",
                "agent_name": persona.name,
                "message": message,
                "is_theme_end": is_theme_end,
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
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}


agent_runner = AgentRunner()
