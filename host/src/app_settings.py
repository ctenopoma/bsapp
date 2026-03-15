"""
app_settings.py
================
アプリケーションのランタイム設定を管理するシングルトン。

【LLM接続情報】
  .env (LLM_IP / LLM_PORT / LLM_MODEL / LLM_API_KEY / LLM_TEMPERATURE) で管理。
  API経由での参照・変更は不可。サーバー側のみが使用する。

【公開設定 (AppSettings)】
  起動時に settings.json → .env の優先順位で初期化され、
  /api/settings エンドポイント経由で変更すると settings.json に永続化される。
"""

import os
import json
from dataclasses import dataclass
from pathlib import Path
from .models import AppSettings

# -------------------------------------------------------------------
# LLM接続情報 (内部専用・クライアントへ公開しない)
# -------------------------------------------------------------------
@dataclass
class _LLMConfig:
    llm_ip: str
    llm_port: str
    llm_model: str
    llm_api_key: str
    llm_temperature: float


_llm_config: _LLMConfig | None = None


def get_llm_config() -> _LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = _LLMConfig(
            llm_ip=os.environ.get("LLM_IP", "127.0.0.1"),
            llm_port=os.environ.get("LLM_PORT", "11434"),
            llm_model=os.environ.get("LLM_MODEL", "llama3"),
            llm_api_key=os.environ.get("LLM_API_KEY", "dummy"),
            llm_temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
        )
    return _llm_config


# -------------------------------------------------------------------
# 公開設定 (AppSettings)
# -------------------------------------------------------------------
_settings: AppSettings | None = None

# host/settings.json (このファイルの2階層上 = host/)
SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.json"


def get_settings() -> AppSettings:
    global _settings
    if _settings is None:
        # 循環インポートを避けるため、ここで遅延インポートする
        from .workflow.prompt_builder import (
            DEFAULT_OUTPUT_FORMAT,
            AGENT_PROMPT_TEMPLATE,
            SUMMARY_PROMPT_TEMPLATE,
        )
        defaults = AppSettings(
            turns_per_theme=int(os.environ.get("TURNS_PER_THEME", "5")),
            default_output_format=DEFAULT_OUTPUT_FORMAT,
            agent_prompt_template=AGENT_PROMPT_TEMPLATE,
            summary_prompt_template=SUMMARY_PROMPT_TEMPLATE,
        )
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                _settings = AppSettings(**{**defaults.model_dump(), **data})
            except Exception:
                _settings = defaults
        else:
            _settings = defaults
    return _settings


def update_settings(new_settings: AppSettings) -> AppSettings:
    global _settings
    _settings = new_settings
    SETTINGS_FILE.write_text(new_settings.model_dump_json(indent=2), encoding="utf-8")
    return _settings


def get_max_history_tokens_limit() -> int:
    """モデルの真の上限トークン数を返す (0=無制限)。

    .env の MAX_HISTORY_TOKENS_LIMIT で設定する。
    クライアントの max_history_tokens はこの値を超えられない。
    """
    return int(os.environ.get("MAX_HISTORY_TOKENS_LIMIT", "0"))
