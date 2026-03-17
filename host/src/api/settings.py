import logging
import urllib.request
import urllib.error
from fastapi import APIRouter, HTTPException
from ..models import AppSettings, HealthResponse
from ..app_settings import get_settings, update_settings, get_llm_config, get_max_history_tokens_limit

logger = logging.getLogger("bsapp.settings")

router = APIRouter()


def _proxy_status(url: str) -> str:
    """URLがプロキシ経由になるか判定して文字列で返す。"""
    from urllib.parse import urlparse
    host = urlparse(url).hostname or url
    try:
        bypassed = urllib.request.proxy_bypass(host)
    except Exception:
        bypassed = False
    if bypassed:
        return "BYPASS (OK)"
    proxies = urllib.request.getproxies()
    proxy_url = proxies.get("http") or proxies.get("https") or "不明"
    return f"VIA PROXY ({proxy_url}) ← NO_PROXY に {host} を追加が必要"


@router.get("/", response_model=AppSettings)
def get_app_settings():
    """現在のアプリ設定を返す。"""
    return get_settings()


@router.put("/", response_model=AppSettings)
def save_app_settings(settings: AppSettings):
    """アプリ設定を上書きする（settings.json に永続化）。"""
    limit = get_max_history_tokens_limit()
    if limit > 0 and settings.max_history_tokens > limit:
        raise HTTPException(
            status_code=422,
            detail=(
                f"max_history_tokens ({settings.max_history_tokens}) が"
                f"モデルの上限 ({limit}) を超えています。"
                f"{limit} 以下の値を設定してください（0 = サーバー上限で自動制限）。"
            ),
        )
    return update_settings(settings)


@router.get("/health", response_model=HealthResponse)
def health_check():
    """サーバー自身の稼働確認と、LLMへの疎通確認を返す。"""
    c = get_llm_config()
    url = f"http://{c.llm_ip}:{c.llm_port}/v1/models"
    proxy = _proxy_status(url)

    logger.info(f"[Health→LLM] GET {url}")
    logger.info(f"  proxy: {proxy}")
    logger.info(
        f"  # 手動確認 (ホストから実行):\n"
        f"  curl -v --noproxy '*' {url} \\\n"
        f"    -H 'Authorization: Bearer {c.llm_api_key}'"
    )

    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {c.llm_api_key}"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            llm_ok = resp.status == 200
            llm_error = None if llm_ok else f"HTTP {resp.status}"
            logger.info(f"[LLM→Health] {resp.status}  {'OK' if llm_ok else 'ERROR'}")
    except Exception as e:
        llm_ok = False
        llm_error = str(e)
        logger.error(f"[LLM ERROR] GET {url}")
        logger.error(f"  {type(e).__name__}: {e}")
        logger.error(f"  proxy: {proxy}")

    return HealthResponse(
        llm="ok" if llm_ok else "error",
        llm_error=llm_error,
    )
