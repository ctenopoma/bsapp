import random
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any, List
import os

from .session_manager import session_manager, SessionMemory
from .rag_manager import rag_manager
from .models import Persona, TaskModel, AgentInput, MessageHistory, ThemeSummary, FullSessionResult

# Temporary simple dictionary to hold job statuses
job_statuses: Dict[str, Dict[str, Any]] = {}

llm_ip = os.environ.get("LLM_IP", "127.0.0.1")
llm_port = os.environ.get("LLM_PORT", "11434")
llm_base_url = f"http://{llm_ip}:{llm_port}/v1"
llm_model = os.environ.get("LLM_MODEL", "llama3")
llm_api_key = os.environ.get("LLM_API_KEY", "dummy")

def create_llm() -> ChatOpenAI:
    return ChatOpenAI(
        temperature=0.7,
        model=llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key
    )


GLOBAL_LLM = create_llm()

# デフォルトの出力フォーマット指定
DEFAULT_OUTPUT_FORMAT = (
    "【発言者】{name}\n"
    "【主張】(1〜2文で主張を述べる)\n"
    "【根拠】(根拠や補足を1〜2文で)\n"
    "300字以内で記述してください。"
)


# -------------------------------------------------------------------
# ペルソナ選択関数 (差し替え可能)
# 将来的にはオーケストレーター型やルールベースに置き換える
# -------------------------------------------------------------------
def select_persona(personas: List[Persona], session: SessionMemory) -> Persona:
    """次に発言するペルソナをランダムに選ぶ。"""
    return random.choice(personas)


# -------------------------------------------------------------------
# AgentInput 組み立て
# -------------------------------------------------------------------
def build_agent_input(
    session: SessionMemory,
    persona: Persona,
    output_format: str = "",
) -> AgentInput:
    """セッション状態とペルソナからエージェントへの入力を構築する。"""
    
    # 割り当てるタスクをランダムに選択
    task_description = ""
    if session.tasks:
        assigned_task = random.choice(session.tasks)
        task_description = assigned_task.description

    # RAG取得 (ペルソナのrag_configに基づく)
    rag_context = ""
    if persona.rag_config.enabled and persona.rag_config.tag:
        rag_context = rag_manager.search_context(
            tag=persona.rag_config.tag,
            query=session.current_theme,
        )

    return AgentInput(
        persona=persona,
        task=task_description,
        query=session.current_theme,
        history=session.history[-5:],  # 直近5件
        rag_context=rag_context,
        output_format=output_format or DEFAULT_OUTPUT_FORMAT.format(name=persona.name),
    )


# -------------------------------------------------------------------
# エージェント実行
# -------------------------------------------------------------------
class AgentRunner:
    def __init__(self):
        self.llm = GLOBAL_LLM

    def _invoke_llm(self, prompt: str):
        try:
            return self.llm.invoke(prompt)
        except Exception:
            self.llm = create_llm()
            return self.llm.invoke(prompt)

    def run_agent(self, agent_input: AgentInput) -> str:
        """AgentInputを受け取りLLMに投げてレスポンスを返す。"""
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
            template="""
あなたは {role} です。
タスク: {task}
あなたの名前は {name} です。グループディスカッションに参加しています。

議題 (Query): {query}

{rag_section}

直近の会話履歴:
{history}

以下のフォーマットで発言してください:
{output_format}
""",
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

        response = self._invoke_llm(formatted_prompt)
        return response.content

    def _run_one_theme(self, session: SessionMemory) -> str:
        """現在のテーマを turns_per_theme ターン回して要約テキストを返す。"""
        active = session.active_personas
        if not active:
            raise ValueError(f"テーマ '{session.current_theme}' に有効なペルソナがありません")
        for _ in range(session.turns_per_theme):
            persona = select_persona(active, session)
            agent_input = build_agent_input(session, persona)
            message = self.run_agent(agent_input)

            # 履歴に追記
            import uuid as _uuid
            session.history.append(MessageHistory(
                id=_uuid.uuid4().hex,
                theme=session.current_theme,
                agent_name=persona.name,
                content=message,
                turn_order=session.turn_count_in_theme,
            ))
            session.turn_count_in_theme += 1

        return self._summarize_current_theme(session)

    def _summarize_current_theme(self, session: SessionMemory) -> str:
        """現在のテーマの履歴をまとめて要約テキストを返す。"""
        theme_history = [
            msg for msg in session.history if msg.theme == session.current_theme
        ]
        history_text = "\n".join(
            [f"{msg.agent_name}: {msg.content}" for msg in theme_history]
        )

        prompt_template = PromptTemplate(
            input_variables=["theme", "history"],
            template="""
テーマ「{theme}」に関するディスカッションを要約してください。
各ペルソナが主張したポイントを整理してまとめてください。

ディスカッション履歴:
{history}
""",
        )

        response = self._invoke_llm(
            prompt_template.format(theme=session.current_theme, history=history_text)
        )
        return response.content

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

            # テーマをひとつずつシーケンシャルに処理
            while not session.all_themes_done:
                summary_text = self._run_one_theme(session)
                session.advance_theme(summary_text)

            # 全要約を結合して最終レポートを生成
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
