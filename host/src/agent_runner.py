from langchain_openai import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from langchain_core.prompts import PromptTemplate
from typing import Dict, Any
import os

from .session_manager import session_manager
from .rag_manager import rag_manager

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

    def start_turn_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
            
            # Simple Turn-Robing: determine next persona based on turn count
            if not session.personas:
                raise ValueError("No personas available")
                
            current_persona = session.personas[session.turn_count_in_theme % len(session.personas)]
            current_theme = session.themes[session.current_theme_index] if session.themes else ""
            
            # 1. Fetch RAG Context (Optional, checking if there is a tag named after the theme)
            # In a real app we might pass a specific tag. Let's assume we search Qdrant for the theme.
            rag_context = rag_manager.search_context(tag=current_theme, query=current_theme)
            
            # 2. Prepare History Summary if exists
            # For simplicity in this mock, we just use the last few messages directly
            recent_history = "\n".join([f"{msg.agent_name}: {msg.content}" for msg in session.history[-5:]])
            
            # 3. Create Prompt
            prompt_template = """
            You are {role}. Your task is: {task}.
            Your name is {name}. You are participating in a group discussion.
            
            Current Theme: {theme}
            
            Recent Discussion Context (RAG):
            {rag_context}
            
            Recent Conversation History:
            {history}
            
            Based on the context and history, provide your next statement in the discussion.
            Keep it under 300 words. Speak only as {name}.
            """
            
            prompt = PromptTemplate(
                input_variables=["role", "task", "name", "theme", "rag_context", "history"],
                template=prompt_template
            )
            
            formatted_prompt = prompt.format(
                role=current_persona.role,
                task=current_persona.task,
                name=current_persona.name,
                theme=current_theme,
                rag_context=rag_context,
                history=recent_history
            )
            
            # 4. Generate Response
            response = self.llm.invoke(formatted_prompt)
            
            # Update session state
            session.turn_count_in_theme += 1
            is_theme_end = session.turn_count_in_theme >= 5  # According to spec: "loop 5人発言するまで"
            
            job_statuses[job_id] = {
                "status": "completed",
                "agent_name": current_persona.name,
                "message": response.content,
                "is_theme_end": is_theme_end
            }
            
        except Exception as e:
            job_statuses[job_id] = {
                "status": "error",
                "error_msg": str(e)
            }

    def summarize_background(self, session_id: str, job_id: str):
        try:
            job_statuses[job_id] = {"status": "processing"}
            session = session_manager.get_session(session_id)
            if not session:
                raise ValueError("Session not found")
                
            current_theme = session.themes[session.current_theme_index] if session.themes else ""
            
            all_history = "\n".join([f"{msg.agent_name}: {msg.content}" for msg in session.history])
            
            prompt_template = """
            Please summarize the following discussion about the theme '{theme}'.
            Identify the key points raised by each persona.
            
            Discussion History:
            {history}
            """
            
            prompt = PromptTemplate(
                input_variables=["theme", "history"],
                template=prompt_template
            )
            
            formatted_prompt = prompt.format(
                theme=current_theme,
                history=all_history
            )
            
            response = self.llm.invoke(formatted_prompt)
            
            # Move to next theme
            session.current_theme_index += 1
            session.turn_count_in_theme = 0
            
            job_statuses[job_id] = {
                "status": "completed",
                "summary_text": response.content
            }
        except Exception as e:
            job_statuses[job_id] = {
                "status": "error",
                "error_msg": str(e)
            }

agent_runner = AgentRunner()
