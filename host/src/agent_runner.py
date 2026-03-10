import random
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any, List
import os

from .session_manager import session_manager, SessionMemory
from .rag_manager import rag_manager
from .models import Persona, AgentInput, MessageHistory

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
def build_agent_input(session: SessionMemory, persona: Persona) -> AgentInput:
    """セッション状態とペルソナからエージェントへの入力を構築する。"""
    current_theme = session.themes[session.current_theme_index] if session.themes else ""

    # RAG取得 (ペルソナのrag_configに基づく)
    rag_context = ""
    if persona.rag_config.enabled and persona.rag_config.tag:
        rag_context = rag_manager.search_context(
            tag=persona.rag_config.tag,
            query=current_theme,
        )

    return AgentInput(
        persona=persona,
        task=persona.task,
        query=current_theme,
        history=session.history[-5:],  # 直近5件
        rag_context=rag_context,
    )


# -------------------------------------------------------------------
# エージェント実行
# -------------------------------------------------------------------
class AgentRunner:
    def __init__(self):
        self.llm = GLOBAL_LLM

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
            input_variables=["role", "task", "name", "query", "rag_section", "history"],
            template="""
あなたは {role} です。
タスク: {task}
あなたの名前は {name} です。グループディスカッションに参加しています。

議題 (Query): {query}

{rag_section}

直近の会話履歴:
{history}

上記を踏まえて、{name} として次の発言を行ってください。300字以内で簡潔に述べてください。
""",
        )

        formatted_prompt = prompt_template.format(
            role=agent_input.persona.role,
            task=agent_input.task,
            name=agent_input.persona.name,
            query=agent_input.query,
            rag_section=rag_section,
            history=recent_history,
        )

        response = self.llm.invoke(formatted_prompt)
        return response.content

    def start_turn_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            if not session.personas:
                raise ValueError("No personas available")

            # 1. ペルソナ選択 (切り替え可能な関数)
            persona = select_persona(session.personas, session)

            # 2. AgentInput 組み立て
            agent_input = build_agent_input(session, persona)

            # 3. LLM実行
            message = self.run_agent(agent_input)

            # 4. セッション状態更新
            session.turn_count_in_theme += 1
            is_theme_end = session.turn_count_in_theme >= 5

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

            current_theme = session.themes[session.current_theme_index] if session.themes else ""
            all_history = "\n".join(
                [f"{msg.agent_name}: {msg.content}" for msg in session.history]
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

            formatted_prompt = prompt_template.format(
                theme=current_theme,
                history=all_history,
            )

            response = self.llm.invoke(formatted_prompt)

            # 次のテーマへ進める
            session.current_theme_index += 1
            session.turn_count_in_theme = 0

            job_statuses[job_id] = {
                "status": "completed",
                "summary_text": response.content,
            }

        except Exception as e:
            job_statuses[job_id] = {"status": "error", "error_msg": str(e)}


agent_runner = AgentRunner()
