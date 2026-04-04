import sys
import logging

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
sys.path.append('d:/work_space/bsapp/host')

from src.models import Persona
from src.session_manager import SessionMemory
from src.workflow.input_builder import build_agent_input

persona = Persona(id='p1', name='Tester', role='Tester')
persona.rag_config.enabled = True
persona.rag_config.tag = 'test_tag'
persona.rag_config.rag_type = 'dummy_http'

session = SessionMemory(session_id='s1', themes=['Test Theme'], personas=[persona])
session.start_theme('Test Theme')

try:
    print('Running build_agent_input...')
    result = build_agent_input(session, persona)
    print('Result rag_context length:', len(result.rag_context))
except Exception as e:
    print(f'Error: {e}')
