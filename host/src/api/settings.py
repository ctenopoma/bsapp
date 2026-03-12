import urllib.request
import urllib.error
from fastapi import APIRouter
from ..models import AppSettings, HealthResponse
from ..app_settings import get_settings, update_settings, get_llm_config

router = APIRouter()


@router.get("/", response_model=AppSettings)
def get_app_settings():
    """現在のアプリ設定を返す。"""
    return get_settings()


@router.put("/", response_model=AppSettings)
def save_app_settings(settings: AppSettings):
    """アプリ設定を上書きする（settings.json に永続化）。"""
    return update_settings(settings)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """サーバー自身の稼働確認と、LLMへの疎通確認を返す。"""
    c = get_llm_config()
    url = f"http://{c.llm_ip}:{c.llm_port}/v1/models"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            llm_ok = resp.status == 200
            llm_error = None if llm_ok else f"HTTP {resp.status}"
    except Exception as e:
        llm_ok = False
        llm_error = str(e)

    return HealthResponse(
        llm="ok" if llm_ok else "error",
        llm_error=llm_error,
    )
