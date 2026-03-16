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
import socket
import json as _json
import urllib.request
import urllib.error
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

# ---- 特許調査テスト用 ----
PATENT_CSV_PATH = ""   # test_report() で読み込む CSV ファイルのパス (絶対パス or host/ からの相対パス)
PATENT_MAX_COMPANIES = 3  # 分析する上位企業数 (件数降順)

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
    PatentAnalyzeRequest, PatentAnalyzeResponse, PatentSummaryRequest,
)
from src.models import PatentItem
from src.session_manager import SessionMemory, SessionManager
from src.workflow.persona_selector import select_persona
from src.workflow.input_builder import build_agent_input
from src.workflow.turn_runner import run_one_theme
from src.workflow.summarizer import summarize_theme
from src.workflow.patent import analyze_company, summarize_all
from src.app_settings import get_settings, get_llm_config
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


def _apply_no_proxy() -> None:
    """
    .env 読み込み後に呼ぶ。
    LLM / Embedding / Rerank / Qdrant の各ホストを NO_PROXY / no_proxy に追加する。
    main.py の _setup_no_proxy() と同等のロジック。
    """
    from urllib.parse import urlparse

    def _host_from_url(url: str) -> str:
        try:
            return urlparse(url).hostname or ""
        except Exception:
            return ""

    new_hosts: set[str] = {
        "localhost", "127.0.0.1",
        os.environ.get("LLM_IP", "127.0.0.1"),
        os.environ.get("EMBEDDING_IP", "127.0.0.1"),
        os.environ.get("RERANK_IP", "127.0.0.1"),
        _host_from_url(os.environ.get("QDRANT_URL", "http://localhost:6333")),
    }
    new_hosts.discard("")
    existing_raw = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    existing = {h.strip() for h in existing_raw.split(",") if h.strip()}
    merged = ",".join(sorted(existing | new_hosts))
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def _diagnose_connection_error(host: str, port: int, error: Exception) -> None:
    """
    接続エラーの原因をステップごとに分析して出力する。
    1. プロキシ環境変数の確認
    2. DNS 解決テスト
    3. TCP 接続テスト
    4. エラー種別ごとのヒント表示
    """
    print("\n  --- 接続エラー分析 ---")

    # 1. プロキシ環境変数
    http_proxy  = os.environ.get("HTTP_PROXY")  or os.environ.get("http_proxy")  or ""
    https_proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
    no_proxy    = os.environ.get("NO_PROXY")    or os.environ.get("no_proxy")    or ""
    print(f"  HTTP_PROXY  : {http_proxy  or '(未設定)'}")
    print(f"  HTTPS_PROXY : {https_proxy or '(未設定)'}")
    print(f"  NO_PROXY    : {no_proxy    or '(未設定)'}")
    if (http_proxy or https_proxy):
        no_proxy_hosts = {h.strip() for h in no_proxy.split(",") if h.strip()}
        if host not in no_proxy_hosts:
            print(f"  ⚠ プロキシが設定されているが '{host}' が NO_PROXY に含まれていません")
        else:
            print(f"  ✓ '{host}' は NO_PROXY に登録されています")

    # 2. DNS 解決テスト
    print(f"\n  DNS 解決テスト: {host}")
    try:
        ip = socket.gethostbyname(host)
        print(f"  ✓ {host} → {ip}")
    except socket.gaierror as e:
        print(f"  ✗ DNS 解決失敗: {e}")
        print("    → LLM_IP をホスト名ではなく IP アドレスで指定するか、DNS を確認してください。")
        return

    # 3. TCP 接続テスト
    print(f"\n  TCP 接続テスト: {host}:{port}")
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"  ✓ TCP 接続成功")
    except ConnectionRefusedError:
        print(f"  ✗ 接続拒否 (Connection refused)")
        print(f"    → LLM サーバーが起動していないか、ポートが違います。")
        print(f"    → Ollama の場合: `ollama serve` で起動し、ポート {port} を確認してください。")
    except socket.timeout:
        print(f"  ✗ TCP タイムアウト")
        print(f"    → ファイアウォールやプロキシでブロックされている可能性があります。")
    except OSError as e:
        print(f"  ✗ TCP エラー: {e}")

    # 4. エラー種別ヒント
    err_str = str(error).lower()
    print("\n  エラー種別ヒント:")
    if "proxy" in err_str or "tunnel" in err_str:
        print("  → プロキシ関連エラー。NO_PROXY に LLM_IP を追加してください。")
    elif "timed out" in err_str or "timeout" in err_str:
        print("  → タイムアウト。LLM サーバーの負荷が高いか、ネットワーク経路に問題があります。")
    elif "refused" in err_str:
        print("  → 接続拒否。LLM サーバーが起動していません。")
    elif "ssl" in err_str or "certificate" in err_str:
        print("  → SSL エラー。http:// で接続しているか確認してください。")
    elif "name or service not known" in err_str or "nodename nor servname" in err_str:
        print("  → ホスト名解決失敗。LLM_IP の設定値を確認してください。")
    else:
        print(f"  → {type(error).__name__}: {error}")


def get_llm():
    """USE_REAL_LLM に応じて LLM を返す。"""
    if USE_REAL_LLM:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_HOST_DIR, ".env"))
        _apply_no_proxy()

        c = get_llm_config()
        from langchain_openai import ChatOpenAI
        print(f"  [LLM] 実LLM使用: {c.llm_model} @ {c.llm_ip}:{c.llm_port}")
        return ChatOpenAI(
            temperature=c.llm_temperature,
            model=c.llm_model,
            base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
            api_key=c.llm_api_key,
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


def test_llm_health():
    """
    ⑦ LLM ヘルスチェック (/v1/models への疎通確認)。
    本番の /api/settings/health と同等の確認をスクリプト単体で実行する。

    確認内容:
      - LLM エンドポイントに HTTP 200 が返るか
      - レスポンスに設定モデルが含まれているか
      - 失敗時は _diagnose_connection_error() で原因を分析
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HOST_DIR, ".env"))
    _apply_no_proxy()
    c = get_llm_config()

    url = f"http://{c.llm_ip}:{c.llm_port}/v1/models"
    print("\n" + "=" * 60)
    print("TEST ⑦ LLM ヘルスチェック")
    print("=" * 60)
    print(f"  接続先  : {url}")
    print(f"  モデル  : {c.llm_model}")
    print(f"  NO_PROXY: {os.environ.get('NO_PROXY', '(未設定)')}")

    try:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {c.llm_api_key}"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode()
            data = _json.loads(body)
            models = [m.get("id", "?") for m in data.get("data", [])]
            print(f"  HTTP ステータス  : {resp.status}")
            print(f"  利用可能モデル   : {models}")
            if c.llm_model in models:
                print(f"  ✓ 設定モデル '{c.llm_model}' を確認")
            else:
                print(f"  ⚠ 設定モデル '{c.llm_model}' が一覧にありません → .env の LLM_MODEL を確認")
        print("\n[OK] LLM ヘルスチェック成功")
        return True
    except Exception as e:
        print(f"\n  [FAIL] {type(e).__name__}: {e}")
        _diagnose_connection_error(c.llm_ip, int(c.llm_port), e)
        print("\n[FAIL] LLM ヘルスチェック失敗")
        return False


def test_llm_chat():
    """
    ⑧ LLM チャット疎通テスト。
    実際に LLM へ短いプロンプトを送信してレスポンスを確認する。
    ヘルスチェック (⑦) が成功してからこのテストを実行することを推奨。

    確認内容:
      - ChatOpenAI.invoke() が正常に返るか
      - レスポンス内容を表示
      - 失敗時は _diagnose_connection_error() で原因を分析
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HOST_DIR, ".env"))
    _apply_no_proxy()
    c = get_llm_config()

    print("\n" + "=" * 60)
    print("TEST ⑧ LLM チャット疎通テスト")
    print("=" * 60)
    print(f"  接続先  : http://{c.llm_ip}:{c.llm_port}/v1")
    print(f"  モデル  : {c.llm_model}")

    try:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            temperature=0,
            model=c.llm_model,
            base_url=f"http://{c.llm_ip}:{c.llm_port}/v1",
            api_key=c.llm_api_key,
        )
        prompt = "「テスト成功」とだけ答えてください。"
        print(f"  送信: '{prompt}'")
        response = llm.invoke(prompt)  # ← ブレイクポイントを置ける
        print(f"  受信: {response.content}")
        print("\n[OK] LLM チャット疎通テスト成功")
        return True
    except Exception as e:
        print(f"\n  [FAIL] {type(e).__name__}: {e}")
        _diagnose_connection_error(c.llm_ip, int(c.llm_port), e)
        print("\n[FAIL] LLM チャット疎通テスト失敗")
        return False


# ================================================================
# 特許調査テスト
# ================================================================

def test_report():
    """
    ⑨ 特許調査レポートの E2E テスト (CSV 読み込み)。
    PATENT_CSV_PATH の CSV を読み込み、settings.json の列名設定を使って
    企業ごとに analyze_company() → summarize_all() を実行する。

    USE_REAL_LLM = False の場合: LLM に渡るプロンプト全文を表示する。
    USE_REAL_LLM = True  の場合: 実際の LLM でレポートを生成する。

    設定フラグ (このファイルの先頭):
      PATENT_CSV_PATH      - 読み込む CSV ファイルのパス
      PATENT_MAX_COMPANIES - 分析する上位企業数 (件数降順)

    デバッグポイント:
      - CSV から正しく企業名・特許内容が取得できているか確認
      - analyze_company() に渡るプロンプトに企業名が含まれているか確認
      - summarize_all() に全企業が正しく渡されているか確認
    """
    import csv
    import io
    from pathlib import Path
    from collections import defaultdict

    print("\n" + "=" * 60)
    print("TEST ⑨ test_report (CSV → 企業別分析 → 総括)")
    print("=" * 60)

    # --- settings.json から列名を取得 ---
    cfg = get_settings()
    company_col = cfg.patent_company_column
    content_col = cfg.patent_content_column
    date_col    = cfg.patent_date_column
    print(f"  [settings.json] 企業列={company_col}  内容列={content_col}  日付列={date_col}")

    # --- CSV 読み込み ---
    csv_path = Path(PATENT_CSV_PATH) if PATENT_CSV_PATH else None
    if not csv_path or not csv_path.exists():
        print(f"\n  CSV ファイルが見つかりません: {PATENT_CSV_PATH!r}")
        print("  debug_test.py 先頭の PATENT_CSV_PATH にパスを設定してください。")
        print("\n[SKIP] test_report")
        return

    raw = csv_path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "utf-8", "shift-jis", "cp932"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        print("  文字コードの判別に失敗しました (UTF-8 / Shift-JIS を確認してください)。")
        print("\n[FAIL] test_report")
        return

    reader = csv.DictReader(io.StringIO(text))
    rows = [{k.strip(): v.strip() for k, v in row.items()} for row in reader]
    if not rows:
        print("  CSV にデータ行がありません。")
        print("\n[FAIL] test_report")
        return

    # --- 列名チェック ---
    available_cols = list(rows[0].keys())
    print(f"  読み込み行数 : {len(rows)}")
    print(f"  検出列名     : {available_cols}")

    missing = [c for c in (company_col, content_col) if c not in available_cols]
    if missing:
        print(f"\n  列名が見つかりません: {missing}")
        print("  settings.json の patent_*_column を CSV の列名に合わせて修正してください。")
        print("\n[FAIL] test_report")
        return

    # --- 企業ごとに集計 (件数降順) ---
    company_map: dict[str, list] = defaultdict(list)
    for row in rows:
        co = row.get(company_col, "").strip()
        if co:
            company_map[co].append(row)

    sorted_companies = sorted(company_map.items(), key=lambda x: -len(x[1]))
    print(f"  企業数       : {len(sorted_companies)}")
    print(f"  分析対象     : 上位 {PATENT_MAX_COMPANIES} 社")
    for co, co_rows in sorted_companies[:PATENT_MAX_COMPANIES]:
        print(f"    - {co} ({len(co_rows)}件)")

    # --- LLM 選択 ---
    # USE_REAL_LLM=False のときはプロンプト全文を出力するキャプチャ LLM を使う
    class _CaptureLLM:
        def __init__(self):
            self._n = 0
        def invoke(self, prompt: str) -> MockResponse:
            self._n += 1
            print(f"\n  ---- プロンプト全文 (call #{self._n}, {len(prompt)}文字) ----")
            print(prompt)
            print(f"  ---- プロンプト終了 ----")
            return MockResponse(f"[Mock #{self._n}] ダミー応答")

    llm = get_llm() if USE_REAL_LLM else _CaptureLLM()

    # --- 企業別分析 ---
    completed: list[PatentAnalyzeResponse] = []
    for company, co_rows in sorted_companies[:PATENT_MAX_COMPANIES]:  # ← ブレイクポイントを置ける
        sorted_rows = sorted(co_rows, key=lambda r: r.get(date_col, ""), reverse=True)[:10]
        patents = [
            PatentItem(content=r.get(content_col, ""), date=r.get(date_col, ""))
            for r in sorted_rows
            if r.get(content_col, "").strip()
        ]
        if not patents:
            print(f"\n  [{company}] 内容列が空のためスキップ")
            continue

        print(f"\n  === [{company}] 特許{len(patents)}件を分析 ===")
        req = PatentAnalyzeRequest(company=company, patents=patents, system_prompt="", output_format="")
        report = analyze_company(req, llm)
        print(f"  → 戻り値先頭: {report[:120].replace(chr(10), ' ')}")
        completed.append(PatentAnalyzeResponse(company=company, report=report))

    # --- 総括 ---
    if completed:
        print(f"\n  === 総括 ({len(completed)}社分) ===")
        summary_req = PatentSummaryRequest(company_reports=completed, system_prompt="")
        summary = summarize_all(summary_req, llm)  # ← ブレイクポイントを置ける
        print(f"  → 戻り値先頭: {summary[:120].replace(chr(10), ' ')}")

    print("\n[OK] test_report")


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

    # ------------------------------------------------------------------
    # LLM 接続確認 (まずここで疎通を確認してから下のテストを実行すると効率的)
    # ------------------------------------------------------------------
    test_llm_health()   # ⑦ /v1/models への HTTP 疎通 + モデル一覧確認
    test_llm_chat()     # ⑧ 実際にプロンプトを送って応答を確認

    # ------------------------------------------------------------------
    # ワークフロー テスト (実行するテストをコメントアウトで選べます)
    # ------------------------------------------------------------------
    # test_persona_selector()
    # test_input_builder()
    # test_single_agent_call()
    # test_turn_runner()
    # test_summarizer()
    # test_full_workflow()

    # ------------------------------------------------------------------
    # 特許調査テスト (PATENT_CSV_PATH を設定してから実行)
    # ------------------------------------------------------------------
    test_report()  # ⑨ CSV読み込み → 企業別分析 → 総括 (プロンプト全文確認)

    print("\n" + "=" * 60)
    print("全テスト完了!")
    print("=" * 60)
