#!/usr/bin/env python3
"""
debug_test.py
=============
ワークフローのデバッグ用テストスクリプト。

使い方:
    cd host
    python debug_test.py

特徴:
  - 完全同期実行 → VSCode/PyCharm でブレイクポイントが効く
  - MockLLM でオフライン動作 → LLM/Qdrant サーバー不要
  - USE_REAL_LLM = True で実際の LLM を使用 (.env が必要)
  - 各テストは独立して呼び出せる → 特定ステップだけデバッグ可能

デバッグ手順:
  1. 確認したいテスト関数にブレイクポイントを置く
  2. debug_test.py をデバッガで実行
  3. ステップ実行でワークフローの動きを追う
"""

import sys
import os
import uuid as _uuid
from unittest.mock import MagicMock

# ----------------------------------------------------------------
# パス設定: host/ をルートとして src パッケージをインポートできるようにする
# ----------------------------------------------------------------
_HOST_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOST_DIR not in sys.path:
    sys.path.insert(0, _HOST_DIR)

# ----------------------------------------------------------------
# 設定フラグ
# ----------------------------------------------------------------
USE_REAL_LLM = False   # True にすると .env の LLM を使用
TURNS_PER_THEME = 2    # 1テーマあたりのターン数 (デバッグ時は少なめに)

# ----------------------------------------------------------------
# rag_manager / qdrant をモック化: インポート時の接続エラーを回避
# ----------------------------------------------------------------
_mock_rag = MagicMock()
_mock_rag.search_context.return_value = ""   # RAG なし扱い

_mock_rag_module = MagicMock()
_mock_rag_module.rag_manager = _mock_rag

# src.rag_manager を差し替える (input_builder.py が "from ..rag_manager import rag_manager" するため)
sys.modules["src.rag_manager"] = _mock_rag_module
# qdrant_client 自体もモックしておく (念のため)
sys.modules.setdefault("qdrant_client", MagicMock())
sys.modules.setdefault("qdrant_client.models", MagicMock())

# ----------------------------------------------------------------
# src パッケージのインポート (上記モック設定の後に行う)
# ----------------------------------------------------------------
from src.models import (
    Persona, RagConfig, TaskModel, MessageHistory,
    ThemeConfig, SessionStartRequest, AgentInput,
)
from src.session_manager import SessionMemory, SessionManager
from src.workflow.persona_selector import select_persona
from src.workflow.input_builder import build_agent_input
from src.workflow.turn_runner import run_one_theme
from src.workflow.summarizer import summarize_theme
from src.app_settings import get_settings
from langchain_core.prompts import PromptTemplate


# ================================================================
# テスト用フィクスチャ
# ================================================================

def make_test_session(turns_per_theme: int = TURNS_PER_THEME) -> SessionMemory:
    """テスト用 SessionMemory を作成する。"""
    request = SessionStartRequest(
        themes=[
            ThemeConfig(theme="AIが社会に与える影響"),
            ThemeConfig(theme="AIの倫理的課題"),
        ],
        personas=[
            Persona(id="p1", name="楽観主義者", role="AIの可能性を信じる研究者"),
            Persona(id="p2", name="懐疑論者", role="AIのリスクを重視する倫理学者"),
            Persona(id="p3", name="中立者", role="バランス良く意見を統合するファシリテーター"),
        ],
        tasks=[
            TaskModel(id="t1", description="AIが雇用に与える影響を分析する"),
            TaskModel(id="t2", description="AIの安全性について考察する"),
        ],
        turns_per_theme=turns_per_theme,
        common_theme="2030年における技術と社会の関係",
        pre_info="本セッションは架空のシナリオに基づくデバッグ用ディスカッションです。",
    )
    manager = SessionManager()
    session_id = manager.start_session(request)
    return manager.get_session(session_id)


# ================================================================
# モック LLM
# ================================================================

class MockResponse:
    """ChatOpenAI.invoke() のレスポンスをシミュレート。"""
    def __init__(self, content: str):
        self.content = content


class MockLLM:
    """ChatOpenAI 互換のモック LLM。LLM サーバーなしで動作確認できる。"""
    def __init__(self):
        self._call_count = 0

    def invoke(self, prompt: str) -> MockResponse:
        self._call_count += 1
        preview = str(prompt)[:80].replace("\n", " ")
        content = f"[MockLLM #{self._call_count}] プロンプト受信: {preview}..."
        print(f"    → MockLLM.invoke() #{self._call_count} (prompt {len(str(prompt))}文字)")
        return MockResponse(content)


def mock_agent_executor(agent_input: AgentInput) -> str:
    """
    run_agent() の代替。LLM を呼ばずにダミー発言を返す。

    ← ここにブレイクポイントを置くと AgentInput の中身を確認できる
    """
    turn_num = len(agent_input.history) + 1
    return (
        f"【発言者】{agent_input.persona.name}\n"
        f"【主張】{agent_input.persona.role}の立場から「{agent_input.query}」について述べます。\n"
        f"【根拠】これはデバッグ用ダミー応答です（ターン #{turn_num}）。\n"
        f"タスク: {agent_input.task}"
    )


def build_real_agent_executor(llm):
    """実 LLM を使う agent_executor を返す (USE_REAL_LLM=True 用)。"""
    def real_agent_executor(agent_input: AgentInput) -> str:
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
            input_variables=["role", "task", "name", "query", "pre_info_section", "rag_section", "history", "previous_summaries", "output_format"],
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
        response = llm.invoke(formatted_prompt)
        return response.content
    return real_agent_executor


def get_llm():
    """USE_REAL_LLM に応じて LLM を返す。"""
    if USE_REAL_LLM:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_HOST_DIR, ".env"))
        from langchain_openai import ChatOpenAI
        llm_ip = os.environ.get("LLM_IP", "127.0.0.1")
        llm_port = os.environ.get("LLM_PORT", "11434")
        llm_model = os.environ.get("LLM_MODEL", "llama3")
        llm_api_key = os.environ.get("LLM_API_KEY", "dummy")
        print(f"  [LLM] 実LLM使用: {llm_model} @ {llm_ip}:{llm_port}")
        return ChatOpenAI(
            temperature=0.7,
            model=llm_model,
            base_url=f"http://{llm_ip}:{llm_port}/v1",
            api_key=llm_api_key,
        )
    else:
        print("  [LLM] MockLLM 使用")
        return MockLLM()


def get_agent_executor(llm):
    """USE_REAL_LLM に応じて agent_executor を返す。"""
    if USE_REAL_LLM:
        return build_real_agent_executor(llm)
    return mock_agent_executor


# ================================================================
# テストケース (各関数を独立してデバッグ実行できる)
# ================================================================

def test_persona_selector():
    """
    ① ペルソナ選択ロジックのテスト。
    workflow/persona_selector.py の select_persona() を検証する。

    デバッグポイント:
      - select_persona() の内部でどのペルソナが選ばれているか確認
    """
    print("\n" + "=" * 60)
    print("TEST ① persona_selector")
    print("=" * 60)

    session = make_test_session()
    active = session.active_personas
    print(f"  テーマ: {session.current_theme}")
    print(f"  アクティブペルソナ: {[p.name for p in active]}")

    print("\n  5回選択:")
    for i in range(5):
        chosen = select_persona(active, session)  # ← ブレイクポイントを置ける
        print(f"    [{i+1}] → {chosen.name}")

    print("\n[OK] persona_selector")


def test_input_builder():
    """
    ② AgentInput 組み立てのテスト。
    workflow/input_builder.py の build_agent_input() を検証する。

    デバッグポイント:
      - AgentInput の各フィールドの中身を確認
      - RAG コンテキストの有無を確認
    """
    print("\n" + "=" * 60)
    print("TEST ② input_builder")
    print("=" * 60)

    session = make_test_session()

    # 履歴を 2 件追加してから組み立てると history[-5:] の動きも確認できる
    session.history.append(MessageHistory(
        id=_uuid.uuid4().hex,
        theme=session.current_theme,
        agent_name="楽観主義者",
        content="AIは雇用を創出すると思います。",
        turn_order=0,
    ))

    persona = session.personas[1]  # 懐疑論者
    agent_input = build_agent_input(session, persona)  # ← ブレイクポイントを置ける

    print(f"  ペルソナ: {agent_input.persona.name} ({agent_input.persona.role})")
    print(f"  クエリ: {agent_input.query}")
    print(f"  タスク: {agent_input.task}")
    print(f"  履歴件数: {len(agent_input.history)}")
    print(f"  RAG: {'あり' if agent_input.rag_context else 'なし'}")
    print(f"  事前情報: {agent_input.pre_info[:80] if agent_input.pre_info else 'なし'}")
    print(f"  出力フォーマット (先頭80文字): {agent_input.output_format[:80]}")

    print("\n[OK] input_builder")


def test_single_agent_call():
    """
    ③ エージェント 1 回の発言テスト。
    agent_executor (run_agent の代替) を単体で実行する。

    デバッグポイント:
      - LLM に渡るプロンプトの内容を確認
      - 返ってくる発言テキストを確認
    """
    print("\n" + "=" * 60)
    print("TEST ③ single agent call")
    print("=" * 60)

    session = make_test_session()
    llm = get_llm()
    agent_executor = get_agent_executor(llm)

    persona = session.personas[0]
    agent_input = build_agent_input(session, persona)

    print(f"  ペルソナ: {persona.name}")
    print(f"  クエリ: {agent_input.query}")

    message = agent_executor(agent_input)  # ← ブレイクポイントを置ける

    print(f"\n  --- 発言内容 ---")
    print(f"  {message}")

    print("\n[OK] single agent call")


def test_turn_runner():
    """
    ④ ターン実行ループのテスト (1テーマ分)。
    workflow/turn_runner.py の run_one_theme() を検証する。

    デバッグポイント:
      - 各ターンで誰が選ばれているか
      - 発言内容が history に積まれているか
      - 要約がどう生成されるか
    """
    print("\n" + "=" * 60)
    print("TEST ④ turn_runner (1テーマ分)")
    print("=" * 60)

    session = make_test_session(turns_per_theme=3)
    llm = get_llm()
    agent_executor = get_agent_executor(llm)

    print(f"  テーマ: {session.current_theme}")
    print(f"  ターン数: {session.turns_per_theme}")

    def summarizer(s: SessionMemory) -> str:
        return summarize_theme(s, llm)  # ← ここにもブレイクポイント可

    summary = run_one_theme(  # ← ブレイクポイントを置ける
        session=session,
        agent_executor=agent_executor,
        summarizer=summarizer,
    )

    print(f"\n  --- 会話履歴 ({len(session.history)}件) ---")
    for msg in session.history:
        print(f"  [{msg.turn_order}] {msg.agent_name}: {msg.content[:80].replace(chr(10), ' ')}...")

    print(f"\n  --- 要約 ---")
    print(f"  {summary[:200]}")

    print("\n[OK] turn_runner")


def test_summarizer():
    """
    ⑤ 要約生成のテスト。
    workflow/summarizer.py の summarize_theme() を検証する。

    デバッグポイント:
      - 履歴からどんなプロンプトが作られるか
      - LLM の要約結果を確認
    """
    print("\n" + "=" * 60)
    print("TEST ⑤ summarizer")
    print("=" * 60)

    session = make_test_session()
    llm = get_llm()

    # ダミー履歴を追加
    dummy_statements = [
        ("楽観主義者", "AIは新しい雇用を生み出すので心配不要です。"),
        ("懐疑論者", "一方でホワイトカラーの仕事が失われるリスクも無視できません。"),
        ("中立者", "双方の意見を踏まえ、再教育プログラムが重要になるでしょう。"),
    ]
    for i, (name, content) in enumerate(dummy_statements):
        session.history.append(MessageHistory(
            id=_uuid.uuid4().hex,
            theme=session.current_theme,
            agent_name=name,
            content=content,
            turn_order=i,
        ))

    print(f"  テーマ: {session.current_theme}")
    print(f"  履歴件数: {len(session.history)}")

    summary = summarize_theme(session, llm)  # ← ブレイクポイントを置ける

    print(f"\n  --- 要約結果 ---")
    print(f"  {summary}")

    print("\n[OK] summarizer")


def test_full_workflow():
    """
    ⑥ フルワークフロー (全テーマ) のテスト。
    session.all_themes_done になるまで全テーマを順番に実行する。

    デバッグポイント:
      - テーマ切り替え (advance_theme) のタイミング
      - 全テーマ完了後の summaries の内容
    """
    print("\n" + "=" * 60)
    print("TEST ⑥ full workflow (全テーマ)")
    print("=" * 60)

    session = make_test_session(turns_per_theme=2)
    llm = get_llm()
    agent_executor = get_agent_executor(llm)

    theme_count = 0
    while not session.all_themes_done:  # ← ブレイクポイントを置ける (テーマループ)
        theme_count += 1
        current_theme = session.current_theme
        print(f"\n  --- テーマ {theme_count}: {current_theme} ---")

        summary = run_one_theme(
            session=session,
            agent_executor=agent_executor,
            summarizer=lambda s: summarize_theme(s, llm),
        )

        theme_history = [h for h in session.history if h.theme == current_theme]
        print(f"  発言数: {len(theme_history)}")
        print(f"  要約 (先頭100文字): {summary[:100].replace(chr(10), ' ')}...")

        session.advance_theme(summary)  # ← ブレイクポイントを置ける (テーマ進行)

    print(f"\n  === 全テーマ完了 ({theme_count} テーマ) ===")
    for s in session.summaries:
        print(f"\n  [{s['theme']}]")
        print(f"  {s['summary'][:120].replace(chr(10), ' ')}...")

    print("\n[OK] full_workflow")


# ================================================================
# エントリポイント
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BSapp ワークフロー デバッグテスト")
    print(f"USE_REAL_LLM = {USE_REAL_LLM}")
    print(f"TURNS_PER_THEME = {TURNS_PER_THEME}")
    print("=" * 60)

    # ← ここにブレイクポイントを置いてステップ実行できます

    # 実行するテストをコメントアウトで選べます
    # test_persona_selector()
    # test_input_builder()
    # test_single_agent_call()
    # test_turn_runner()
    # test_summarizer()
    test_full_workflow()

    print("\n" + "=" * 60)
    print("全テスト完了!")
    print("=" * 60)
