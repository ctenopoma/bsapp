"""
workflow パッケージ
=====================
エージェント議論の各ステップを独立したモジュールに分離しています。
各ファイルを書き換えることで、議論の進め方を自由にカスタマイズできます。

モジュール一覧:
- persona_selector.py    : 次に発言するペルソナの選び方
- prompt_builder.py      : LLMへのプロンプトテンプレート
- input_builder.py       : AgentInput (エージェントへの入力) の組み立て
- history_compressor.py  : 会話履歴のトークン圧縮
- summarizer.py          : テーマ要約の生成
- turn_runner.py         : 1テーマ分のターン実行ループ (ストラテジーディスパッチャー)
- template_resolver.py   : 事前情報内のテンプレート変数解決
- strategies/            : テーマ内ストラテジー (シーケンシャル, 並列, ラウンドロビン等)
- orchestrator.py        : マクロフロー・ディスパッチャー (テーマ間の進行制御)
- flows/                 : マクロワークフロー (ウォーターフォール, ステージゲート等)
"""

from .persona_selector import select_persona
from .input_builder import build_agent_input
from .prompt_builder import DEFAULT_OUTPUT_FORMAT, AGENT_PROMPT_TEMPLATE, SUMMARY_PROMPT_TEMPLATE
from .summarizer import summarize_theme
from .turn_runner import run_one_theme
from .orchestrator import run_full_session
from .strategies import STRATEGY_MAP, get_strategy

__all__ = [
    "select_persona",
    "build_agent_input",
    "DEFAULT_OUTPUT_FORMAT",
    "AGENT_PROMPT_TEMPLATE",
    "SUMMARY_PROMPT_TEMPLATE",
    "summarize_theme",
    "run_one_theme",
    "run_full_session",
    "STRATEGY_MAP",
    "get_strategy",
]
