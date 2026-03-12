#!/usr/bin/env python3
"""
debug_report.py
================
特許調査ワークフローのデバッグ用テストスクリプト。

使い方:
    cd host
    python debug_report.py

特徴:
  - 完全同期実行 → VSCode/PyCharm でブレイクポイントが効く
  - MockLLM でオフライン動作 → LLM サーバー不要
  - USE_REAL_LLM = True で実際の LLM を使用 (.env が必要)
  - 各テストは独立して呼び出せる → 特定ステップだけデバッグ可能

デバッグ手順:
  1. 確認したいテスト関数にブレイクポイントを置く
  2. debug_report.py をデバッガで実行
  3. ステップ実行でワークフローの動きを追う
"""

import sys
import os
from unittest.mock import MagicMock

# ----------------------------------------------------------------
# パス設定: host/ をルートとして src パッケージをインポートできるようにする
# ----------------------------------------------------------------
_HOST_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOST_DIR not in sys.path:
    sys.path.insert(0, _HOST_DIR)

# ----------------------------------------------------------------
# rag_manager / qdrant をモック化: インポート時の接続エラーを回避
# ----------------------------------------------------------------
_mock_rag = MagicMock()
_mock_rag.search_context.return_value = ""

_mock_rag_module = MagicMock()
_mock_rag_module.rag_manager = _mock_rag

sys.modules["src.rag_manager"] = _mock_rag_module
sys.modules.setdefault("qdrant_client", MagicMock())
sys.modules.setdefault("qdrant_client.models", MagicMock())

# ----------------------------------------------------------------
# 設定フラグ
# ----------------------------------------------------------------
USE_REAL_LLM = False   # True にすると .env の LLM を使用

# ----------------------------------------------------------------
# src パッケージのインポート
# ----------------------------------------------------------------
from src.models import PatentItem, PatentAnalyzeRequest, PatentSummaryRequest, PatentAnalyzeResponse
from src.app_settings import get_llm_config
from src.workflow.patent.analyzer import analyze_company
from src.workflow.patent.summarizer import summarize_all
from src.workflow.patent.prompt_builder import (
    DEFAULT_ANALYZE_SYSTEM_PROMPT,
    DEFAULT_ANALYZE_OUTPUT_FORMAT,
    DEFAULT_SUMMARY_SYSTEM_PROMPT,
)


# ================================================================
# テスト用フィクスチャ
# ================================================================

SAMPLE_PATENTS_A = [
    PatentItem(content="深層学習を用いた画像認識システム", date="2024-03-15"),
    PatentItem(content="自然言語処理による文書分類装置", date="2024-02-10"),
    PatentItem(content="強化学習を用いたロボット制御方法", date="2024-01-20"),
    PatentItem(content="マルチモーダル学習のための特徴融合手法", date="2023-12-05"),
    PatentItem(content="エッジコンピューティング向け軽量AIモデル", date="2023-11-18"),
    PatentItem(content="グラフニューラルネットワークによる異常検知", date="2023-10-30"),
    PatentItem(content="トランスフォーマーモデルの圧縮技術", date="2023-09-14"),
    PatentItem(content="連合学習を用いたプライバシー保護AI", date="2023-08-22"),
    PatentItem(content="ゼロショット学習による新規カテゴリ認識", date="2023-07-11"),
    PatentItem(content="説明可能AIのための可視化手法", date="2023-06-03"),
]

SAMPLE_PATENTS_B = [
    PatentItem(content="量子コンピュータ向け最適化アルゴリズム", date="2024-03-20"),
    PatentItem(content="バイオインフォマティクスへの機械学習応用", date="2024-02-28"),
    PatentItem(content="半導体プロセス制御のためのAI予測モデル", date="2024-01-15"),
    PatentItem(content="材料探索のための生成AIシステム", date="2023-12-20"),
    PatentItem(content="エネルギー消費予測のためのニューラルネットワーク", date="2023-11-08"),
]


# ================================================================
# モック LLM
# ================================================================

class MockResponse:
    """ChatOpenAI.invoke() のレスポンスをシミュレート。"""
    def __init__(self, content: str):
        self.content = content


class MockLLM:
    """ChatOpenAI 互換のモック LLM。"""
    def __init__(self):
        self._call_count = 0

    def invoke(self, prompt: str) -> MockResponse:
        self._call_count += 1
        preview = str(prompt)[:80].replace("\n", " ")
        content = (
            f"## テスト企業 分析レポート\n\n"
            f"### 主な技術領域\n- AI・機械学習\n- データ処理\n- 最適化\n\n"
            f"### 研究開発の方向性\nこの企業はAI分野に注力しています。\n\n"
            f"### 注目特許\n特許1: [MockLLM #{self._call_count}] プロンプト: {preview}..."
        )
        print(f"    → MockLLM.invoke() #{self._call_count} (prompt {len(str(prompt))}文字)")
        return MockResponse(content)


def get_llm():
    """USE_REAL_LLM に応じて LLM を返す。"""
    if USE_REAL_LLM:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(_HOST_DIR, ".env"))
        c = get_llm_config()
        no_proxy_hosts = {"localhost", "127.0.0.1", c.llm_ip}
        existing = {h.strip() for h in os.environ.get("NO_PROXY", "").split(",") if h.strip()}
        os.environ["NO_PROXY"] = ",".join(sorted(existing | no_proxy_hosts))
        os.environ["no_proxy"] = os.environ["NO_PROXY"]

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


# ================================================================
# テストケース
# ================================================================

def test_analyzer():
    """
    ① 1企業分析のテスト。
    workflow/patent/analyzer.py の analyze_company() を検証する。

    デバッグポイント:
      - LLM に渡るプロンプトの内容を確認
      - 特許リストのテキスト整形を確認
      - 出力レポートの内容を確認
    """
    print("\n" + "=" * 60)
    print("TEST ① analyze_company (1企業分析)")
    print("=" * 60)

    llm = get_llm()
    request = PatentAnalyzeRequest(
        company="サンプル技術株式会社",
        patents=SAMPLE_PATENTS_A,
        system_prompt=DEFAULT_ANALYZE_SYSTEM_PROMPT,
        output_format=DEFAULT_ANALYZE_OUTPUT_FORMAT.format(company="サンプル技術株式会社"),
    )

    print(f"  企業名: {request.company}")
    print(f"  特許件数: {len(request.patents)}")
    print(f"  最初の特許: {request.patents[0].content} ({request.patents[0].date})")

    report = analyze_company(request, llm)  # ← ブレイクポイントを置ける

    print(f"\n  --- レポート ---")
    print(report)
    print("\n[OK] analyze_company")
    return report


def test_analyzer_default_prompts():
    """
    ② デフォルトプロンプト (空文字) でのフォールバック確認。
    system_prompt・output_format を空にしてデフォルト値が使われることを確認する。

    デバッグポイント:
      - DEFAULT_ANALYZE_SYSTEM_PROMPT が自動補完されるか
      - DEFAULT_ANALYZE_OUTPUT_FORMAT が自動補完されるか
    """
    print("\n" + "=" * 60)
    print("TEST ② analyze_company (デフォルトプロンプト)")
    print("=" * 60)

    llm = get_llm()
    request = PatentAnalyzeRequest(
        company="フォールバックテスト株式会社",
        patents=SAMPLE_PATENTS_B,
        system_prompt="",   # ← 空 → デフォルト値が使われる
        output_format="",   # ← 空 → デフォルト値が使われる
    )

    print(f"  企業名: {request.company}")
    print(f"  特許件数: {len(request.patents)}")
    print("  system_prompt: '' (デフォルト使用)")
    print("  output_format: '' (デフォルト使用)")

    report = analyze_company(request, llm)  # ← ブレイクポイントを置ける

    print(f"\n  --- レポート ---")
    print(report)
    print("\n[OK] analyze_company (デフォルトプロンプト)")
    return report


def test_summarizer():
    """
    ③ 総括レポートのテスト。
    workflow/patent/summarizer.py の summarize_all() を検証する。

    デバッグポイント:
      - 全企業レポートをまとめたプロンプトの内容を確認
      - 総括レポートの構成を確認
    """
    print("\n" + "=" * 60)
    print("TEST ③ summarize_all (総括)")
    print("=" * 60)

    llm = get_llm()

    # テスト用のダミーレポート
    company_reports = [
        PatentAnalyzeResponse(
            company="サンプル技術株式会社",
            report="## サンプル技術株式会社\n\n### 主な技術領域\n- 深層学習\n- 画像認識\n\n### 方向性\nAI研究をリード。",
        ),
        PatentAnalyzeResponse(
            company="テスト工業株式会社",
            report="## テスト工業株式会社\n\n### 主な技術領域\n- 量子計算\n- バイオインフォマティクス\n\n### 方向性\n先端素材とAIの融合。",
        ),
    ]

    request = PatentSummaryRequest(
        company_reports=company_reports,
        system_prompt=DEFAULT_SUMMARY_SYSTEM_PROMPT,
    )

    print(f"  企業数: {len(request.company_reports)}")
    for r in request.company_reports:
        print(f"    - {r.company}")

    summary = summarize_all(request, llm)  # ← ブレイクポイントを置ける

    print(f"\n  --- 総括レポート ---")
    print(summary)
    print("\n[OK] summarize_all")
    return summary


def test_full_workflow():
    """
    ④ フルワークフロー (企業別分析 → 総括) のテスト。
    analyze_company() を複数社で実行し、summarize_all() まで一気通貫で検証する。

    デバッグポイント:
      - 各企業のレポートが正しく生成されるか
      - 全企業完了後に総括が走るか
      - PatentAnalyzeResponse のリストが正しく受け渡されるか
    """
    print("\n" + "=" * 60)
    print("TEST ④ full workflow (企業別分析 → 総括)")
    print("=" * 60)

    llm = get_llm()

    companies = [
        ("サンプル技術株式会社", SAMPLE_PATENTS_A),
        ("テスト工業株式会社", SAMPLE_PATENTS_B),
    ]

    completed_reports: list[PatentAnalyzeResponse] = []

    # --- 企業別分析ループ ---
    for company, patents in companies:
        print(f"\n  [{company}] 分析中...")

        request = PatentAnalyzeRequest(
            company=company,
            patents=patents,
            system_prompt=DEFAULT_ANALYZE_SYSTEM_PROMPT,
            output_format=DEFAULT_ANALYZE_OUTPUT_FORMAT.format(company=company),
        )

        report_text = analyze_company(request, llm)  # ← ブレイクポイントを置ける

        print(f"  レポート (先頭100文字): {report_text[:100].replace(chr(10), ' ')}...")

        completed_reports.append(PatentAnalyzeResponse(company=company, report=report_text))

    print(f"\n  全企業完了 ({len(completed_reports)}社)")

    # --- 総括 ---
    print("\n  総括生成中...")
    summary_request = PatentSummaryRequest(
        company_reports=completed_reports,
        system_prompt=DEFAULT_SUMMARY_SYSTEM_PROMPT,
    )

    summary = summarize_all(summary_request, llm)  # ← ブレイクポイントを置ける

    print(f"\n  --- 総括レポート ---")
    print(summary)

    print("\n[OK] full_workflow")


def test_csv_column_mapping():
    """
    ⑤ CSV列名マッピングの確認。
    AppSettings の patent_* 列名設定がデフォルト値で初期化されているか確認する。

    デバッグポイント:
      - get_settings() の patent_* フィールドを確認
    """
    print("\n" + "=" * 60)
    print("TEST ⑤ AppSettings 列名設定確認")
    print("=" * 60)

    from src.app_settings import get_settings
    settings = get_settings()  # ← ブレイクポイントを置ける

    print(f"  patent_company_column : {settings.patent_company_column!r}")
    print(f"  patent_content_column : {settings.patent_content_column!r}")
    print(f"  patent_date_column    : {settings.patent_date_column!r}")
    print(f"  max_history_tokens    : {settings.max_history_tokens}")
    print(f"  recent_history_count  : {settings.recent_history_count}")

    assert settings.patent_company_column, "patent_company_column が空"
    assert settings.patent_content_column, "patent_content_column が空"
    assert settings.patent_date_column, "patent_date_column が空"

    print("\n[OK] AppSettings 列名設定確認")


# ================================================================
# エントリポイント
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BSapp 特許調査ワークフロー デバッグテスト")
    print(f"USE_REAL_LLM = {USE_REAL_LLM}")
    print("=" * 60)

    # ← ここにブレイクポイントを置いてステップ実行できます

    # 実行するテストをコメントアウトで選べます
    # test_analyzer()
    # test_analyzer_default_prompts()
    # test_summarizer()
    test_full_workflow()
    # test_csv_column_mapping()

    print("\n" + "=" * 60)
    print("全テスト完了!")
    print("=" * 60)
